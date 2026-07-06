"""Train the Anomaly Detection module.

Isolation Forest, unsupervised. Contamination is swept across [0.01, 0.10]
and the value maximising F1 against the synthetic ground-truth anomaly
labels is retained. The final model is refit on the full training set at
that contamination.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler

from app.features import FEATURE_COLUMNS, build_feature_frame
from app.training import registry

CONTAMINATION_GRID = (0.01, 0.02, 0.03, 0.05, 0.07, 0.10)


def _load_labels() -> pd.DataFrame | None:
    """Ground-truth anomaly labels from the synthetic-data generator.

    Written to ``synthetic-data/out/labels.csv`` when the generator runs.
    Returns None if unavailable — anomaly detection remains unsupervised
    (no threshold tuning), which is fine but produces less informative
    training metrics.
    """
    candidates = [
        Path("synthetic-data/out/labels.csv"),
        Path("../synthetic-data/out/labels.csv"),
    ]
    for p in candidates:
        if p.exists():
            df = pd.read_csv(p, parse_dates=["window_start"])
            df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
            df["service_id"] = df["service_id"].astype(str)
            return df
    return None


def train(df: pd.DataFrame, model_dir: Path) -> dict:
    engineered = build_feature_frame(df)
    engineered = engineered.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)

    X = engineered[FEATURE_COLUMNS].values
    scaler = StandardScaler()
    X_s = scaler.fit_transform(X)

    labels_df = _load_labels()
    y_true = None
    if labels_df is not None:
        joined = engineered.merge(
            labels_df[["service_id", "window_start", "is_anomaly"]],
            on=["service_id", "window_start"],
            how="left",
        )
        y_true = joined["is_anomaly"].fillna(False).astype(int).values

    hyperparams_base = dict(
        n_estimators=200,
        max_samples="auto",
        n_jobs=-1,
        random_state=42,
    )

    metrics: dict[str, float] = {}
    best_contamination = 0.05
    best_f1 = -1.0

    if y_true is not None and y_true.sum() > 0:
        for c in CONTAMINATION_GRID:
            m = IsolationForest(contamination=c, **hyperparams_base)
            m.fit(X_s)
            preds = (m.predict(X_s) == -1).astype(int)
            f1 = f1_score(y_true, preds, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_contamination = c

    hyperparams = {**hyperparams_base, "contamination": best_contamination}
    model = IsolationForest(**hyperparams)
    model.fit(X_s)

    if y_true is not None and y_true.sum() > 0:
        preds = (model.predict(X_s) == -1).astype(int)
        metrics["contamination"] = best_contamination
        metrics["precision"] = float(precision_score(y_true, preds, zero_division=0))
        metrics["recall"] = float(recall_score(y_true, preds, zero_division=0))
        metrics["f1"] = float(f1_score(y_true, preds, zero_division=0))
        metrics["n_injected"] = float(int(y_true.sum()))
    else:
        metrics["contamination"] = best_contamination
        metrics["n_injected"] = 0.0

    meta = registry.save(
        module="anomaly",
        model=model,
        scaler=scaler,
        feature_cols=FEATURE_COLUMNS,
        metrics=metrics,
        hyperparams=hyperparams,
        training_rows=len(engineered),
        algorithm="sklearn.ensemble.IsolationForest",
        model_dir=model_dir,
    )
    return {
        "model_version": meta["version"],
        "training_rows": meta["training_rows"],
        "metrics": metrics,
    }
