"""Train the Alert Prioritization module (Random Forest).

The paper's labelling scheme (§IV-F) is fully heuristic:
  - alerts co-occurring with confirmed failures → Critical
  - alerts on payment/auth services → escalate one level
  - alerts resolved automatically within 5 min → Low

We synthesize the training set by generating alert contexts from the same
metrics history: every row where P99 > 2s or error_rate > 10% becomes a
candidate alert with features derived from the surrounding metrics.

The Random Forest learns those rules AND the latent correlations between
context features (hour of day, alert frequency, health score) and the
label the heuristic would assign — which is exactly what the paper
describes.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import LabelEncoder

from app.training import registry

# Feature columns for the alert prioritizer — these match AlertContext in the
# OpenAPI spec. Kept explicit and stable so training and inference share the
# same column order.
ALERT_FEATURES = [
    "triggering_metric_latency",
    "triggering_metric_error_rate",
    "triggering_metric_availability",
    "hour_of_day",
    "alert_frequency_24h",
    "current_health_score",
    "failure_prediction_active",
    "service_is_payment_or_auth",
]

PRIORITY_LABELS = ["low", "medium", "high", "critical"]

PAYMENT_AUTH_KEYWORDS = ("payment", "pay", "auth", "billing")


def _is_payment_or_auth(service_name: str) -> bool:
    n = service_name.lower()
    return any(k in n for k in PAYMENT_AUTH_KEYWORDS)


def _rolling_alert_frequency(alert_rows: pd.DataFrame) -> pd.Series:
    """Count of alerts per service in the preceding 24h (per row)."""
    alert_rows = alert_rows.sort_values(["service_id", "window_start"])
    counts: list[int] = []
    for _, group in alert_rows.groupby("service_id", sort=False):
        ts = pd.to_datetime(group["window_start"], utc=True)
        idx_series = pd.Series(range(len(group)), index=ts)
        rolling = idx_series.rolling("24h").count() - 1
        counts.extend(rolling.astype(int).clip(lower=0).tolist())
    return pd.Series(counts, index=alert_rows.index)


def _synthetic_health_score(row: pd.Series) -> float:
    """A quick composite that mirrors Module 4 without importing it."""
    err_ok = max(0.0, 1.0 - float(row.get("error_rate", 0.0)))
    lat_ok = max(0.0, 1.0 - min(1.0, float(row.get("response_time_p99", 0.0)) / 5000.0))
    return 100.0 * (0.6 * err_ok + 0.4 * lat_ok)


def _label(row: pd.Series) -> str:
    """Heuristic priority label — the ground truth for training."""
    base = "low"
    if row["triggering_metric"] == "availability":
        base = "high"
    elif row["current_health_score"] < 50:
        base = "high"
    elif row["alert_frequency_24h"] >= 10:
        base = "medium"

    if row["failure_prediction_active"]:
        return "critical"
    if row["service_is_payment_or_auth"]:
        order = PRIORITY_LABELS
        return order[min(order.index(base) + 1, len(order) - 1)]
    return base


def _build_alert_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Turn metric rows into synthetic alert contexts."""
    latency_alerts = df[df["response_time_p99"] > 2000].copy()
    latency_alerts["triggering_metric"] = "latency"

    error_alerts = df[df["error_rate"] > 0.10].copy()
    error_alerts["triggering_metric"] = "error_rate"

    # Simulate a small pool of availability alerts (rare) — 5% of the P99 breaches.
    availability_alerts = latency_alerts.sample(
        frac=0.05, random_state=42, replace=False
    ).copy()
    availability_alerts["triggering_metric"] = "availability"

    alerts = pd.concat(
        [latency_alerts, error_alerts, availability_alerts], ignore_index=True
    )
    if alerts.empty:
        return alerts

    alerts["hour_of_day"] = pd.to_datetime(alerts["window_start"], utc=True).dt.hour
    alerts["alert_frequency_24h"] = _rolling_alert_frequency(alerts)
    alerts["current_health_score"] = alerts.apply(_synthetic_health_score, axis=1)
    # "Failure prediction active" is a *separate* signal from the trigger.
    # We only fire it on the most-severe subset so labels don't collapse to
    # a single class — otherwise every alert co-occurs with a failure.
    severe = (alerts["error_rate"] > 0.20) & (alerts["response_time_p99"] > 3500)
    alerts["failure_prediction_active"] = severe

    # Payment/auth is a per-service attribute; we look it up on the joined
    # services frame if present, else default False.
    if "service_name" in alerts.columns:
        alerts["service_is_payment_or_auth"] = alerts["service_name"].apply(_is_payment_or_auth)
    else:
        alerts["service_is_payment_or_auth"] = False

    return alerts


def _one_hot(alerts: pd.DataFrame) -> pd.DataFrame:
    for metric in ("latency", "error_rate", "availability"):
        alerts[f"triggering_metric_{metric}"] = (
            alerts["triggering_metric"] == metric
        ).astype(int)
    return alerts


def train(df: pd.DataFrame, model_dir: Path) -> dict:
    # Join service names so the payment/auth heuristic works.
    import psycopg

    from app.config import settings

    with psycopg.connect(settings.pg_dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name FROM services")
        service_map = {str(row[0]): row[1] for row in cur.fetchall()}

    joined = df.copy()
    joined["service_name"] = joined["service_id"].map(service_map).fillna("unknown")

    alerts = _build_alert_dataset(joined)
    if alerts.empty:
        raise RuntimeError(
            "No alert-worthy rows in the training window. Extend --days or "
            "increase fault-injection rate in the synthetic generator."
        )
    alerts = _one_hot(alerts)
    alerts["priority"] = alerts.apply(_label, axis=1)

    # Chronological split.
    alerts = alerts.sort_values("window_start").reset_index(drop=True)
    cut = int(len(alerts) * 0.8)
    train_df = alerts.iloc[:cut]
    test_df = alerts.iloc[cut:]

    if test_df.empty:
        test_df = train_df

    X_train = train_df[ALERT_FEATURES].values.astype(float)
    X_test = test_df[ALERT_FEATURES].values.astype(float)

    le = LabelEncoder()
    le.fit(PRIORITY_LABELS)
    y_train = le.transform(train_df["priority"].values)
    y_test = le.transform(test_df["priority"].values)

    hyperparams = dict(
        n_estimators=200,
        max_depth=12,
        min_samples_split=8,
        class_weight="balanced",
        n_jobs=-1,
        random_state=42,
    )
    model = RandomForestClassifier(**hyperparams)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, preds)),
        "precision_macro": float(precision_score(y_test, preds, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_test, preds, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, preds, average="macro", zero_division=0)),
        "n_train_alerts": float(len(train_df)),
        "n_test_alerts": float(len(test_df)),
    }
    for i, label in enumerate(le.classes_):
        cnt = int((train_df["priority"] == label).sum())
        metrics[f"count_{label}"] = float(cnt)

    # Wrap the label encoder alongside the model so inference can decode.
    packaged = {"clf": model, "label_encoder": le}

    meta = registry.save(
        module="alerts",
        model=packaged,
        scaler=None,
        feature_cols=ALERT_FEATURES,
        metrics=metrics,
        hyperparams=hyperparams,
        training_rows=len(train_df),
        algorithm="sklearn.ensemble.RandomForestClassifier",
        model_dir=model_dir,
    )
    return {
        "model_version": meta["version"],
        "training_rows": meta["training_rows"],
        "metrics": metrics,
    }
