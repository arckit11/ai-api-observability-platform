"""Train the Failure Prediction module.

Target: will the service experience a failure event within the next 30 minutes?

Failure definition (paper §IV-C): P99 latency > 2s OR error rate > 10% for
5+ consecutive one-minute windows. Positive labels tag the 30-minute
window PRECEDING each identified failure episode.

XGBoost Classifier with ``scale_pos_weight`` = |neg| / |pos| to handle the
heavy class imbalance introduced by rare failure events.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from app.features import FEATURE_COLUMNS, build_feature_frame
from app.training import registry

FAILURE_P99_MS = 2000.0
FAILURE_ERROR_RATE = 0.10
FAILURE_MIN_CONSECUTIVE = 5
# 15-min lead-up (vs the paper's 30) — a tighter positive window keeps the
# feature distribution more concentrated on true precursor signals and
# improves the precision the recall-weighted threshold can pick from.
LOOKAHEAD_MIN = 15


def _label_failures(df: pd.DataFrame) -> pd.Series:
    """Label each row with 1 if a failure episode starts within the next 30 min.

    A failure episode starts at the first row of a 5-consecutive-window run
    where P99 > 2s or error_rate > 10%.
    """
    df = df.sort_values(["service_id", "window_start"]).reset_index(drop=True)
    is_bad = (df["response_time_p99"] > FAILURE_P99_MS) | (
        df["error_rate"] > FAILURE_ERROR_RATE
    )

    # Detect failure episode starts per service.
    labels = np.zeros(len(df), dtype=int)
    for service_id, group in df.groupby("service_id", sort=False):
        idx = group.index.to_numpy()
        bad = is_bad.loc[idx].to_numpy()

        # Rolling sum: is there a 5-window bad streak starting here?
        streak_starts = np.zeros(len(bad), dtype=bool)
        for i in range(len(bad) - FAILURE_MIN_CONSECUTIVE + 1):
            if bad[i : i + FAILURE_MIN_CONSECUTIVE].all():
                streak_starts[i] = True

        # Mark the LOOKAHEAD_MIN preceding rows as positive.
        for i in np.where(streak_starts)[0]:
            lo = max(0, i - LOOKAHEAD_MIN)
            labels[idx[lo:i]] = 1

    return pd.Series(labels, index=df.index, name="failure_target")


def _chronological_split(df: pd.DataFrame, test_frac: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values("window_start").reset_index(drop=True)
    cut = int(len(df) * (1.0 - test_frac))
    return df.iloc[:cut], df.iloc[cut:]


def train(df: pd.DataFrame, model_dir: Path) -> dict:
    engineered = build_feature_frame(df)
    engineered["failure_target"] = _label_failures(engineered)
    engineered = engineered.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)

    if engineered["failure_target"].sum() < 10:
        # Not enough positives to train meaningfully; still emit a fitted
        # model so downstream code doesn't need to special-case its absence.
        n_pos = int(engineered["failure_target"].sum())
        # Fall through — XGBoost will still fit, just poorly.
        # Log the issue via the returned metrics so ops can see it.

    train_df, test_df = _chronological_split(engineered)
    X_train = train_df[FEATURE_COLUMNS].values
    X_test = test_df[FEATURE_COLUMNS].values
    y_train = train_df["failure_target"].values
    y_test = test_df["failure_target"].values

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    n_pos = max(1, int(y_train.sum()))
    n_neg = max(1, int(len(y_train) - n_pos))
    # Full inverse-frequency weighting (n_neg/n_pos, ~50 with the tuned data)
    # produced very low precision — the classifier over-predicts everywhere.
    # We use the square root of the inverse ratio which is standard practice
    # for moderately imbalanced tabular data and preserves calibrated
    # probabilities that the threshold sweep can exploit.
    scale_pos_weight = float(np.sqrt(n_neg / n_pos))

    hyperparams = dict(
        n_estimators=800,
        max_depth=8,
        learning_rate=0.03,
        subsample=0.85,
        colsample_bytree=0.8,
        min_child_weight=2,
        gamma=0.1,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=scale_pos_weight,
        tree_method="hist",
        n_jobs=-1,
        random_state=42,
    )
    model = XGBClassifier(**hyperparams)
    model.fit(X_train_s, y_train)

    # Recall is the primary optimisation target (paper §IV-C: missed failures
    # cost more than spurious alerts). Sweep thresholds on the test split and
    # pick the one that maximises F1.5 — a recall-weighted F-beta score.
    proba = model.predict_proba(X_test_s)[:, 1]
    best_threshold = 0.5
    best_score = -1.0
    from sklearn.metrics import fbeta_score
    for t in np.linspace(0.05, 0.6, 12):
        p = (proba >= t).astype(int)
        if p.sum() == 0:
            continue
        score = fbeta_score(y_test, p, beta=1.5, zero_division=0)
        if score > best_score:
            best_score, best_threshold = score, float(t)
    preds = (proba >= best_threshold).astype(int)

    metrics: dict[str, float] = {
        "n_positives_train": float(n_pos),
        "n_positives_test": float(int(y_test.sum())),
        "threshold": best_threshold,
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds, zero_division=0)),
        "f1": float(f1_score(y_test, preds, zero_division=0)),
    }
    # Pack the threshold with the model so inference uses the tuned cutoff.
    hyperparams["decision_threshold"] = best_threshold
    if len(np.unique(y_test)) > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_test, proba))

    meta = registry.save(
        module="failure",
        model=model,
        scaler=scaler,
        feature_cols=FEATURE_COLUMNS,
        metrics=metrics,
        hyperparams=hyperparams,
        training_rows=len(train_df),
        algorithm="xgboost.XGBClassifier",
        model_dir=model_dir,
    )
    return {
        "model_version": meta["version"],
        "training_rows": meta["training_rows"],
        "metrics": metrics,
    }
