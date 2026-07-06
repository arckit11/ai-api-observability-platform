"""Feature engineering — Table II of the paper.

Two entry points:

- ``build_feature_frame(df)`` — batch mode used at training time. Expects a
  chronologically ordered DataFrame of metric rows per service and returns
  the full engineered matrix with cyclical time encodings, lag features
  (1h / 6h / 24h) and rolling 15-minute means.

- ``engineer_row(history)`` — inference mode. Takes a list of
  ``MetricSnapshot`` covering the recent past (chronologically ordered) and
  returns a single-row DataFrame ready for ``model.predict``.

Both paths compute features identically so training-serving skew is
eliminated. Missing lag values (rows near the start of a service's
history) are dropped in batch mode; at inference time the caller must
supply enough history (at least 24h of one-minute snapshots) or fall
back to the anomaly / health-score modules that don't need lags.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# Column order MUST be stable; the scaler and model artifacts persist this
# order and inference relies on the DataFrame column order matching.
FEATURE_COLUMNS: list[str] = [
    "request_count",
    "response_time_mean",
    "response_time_p95",
    "response_time_p99",
    "error_rate",
    "cpu_usage_pct",
    "memory_usage_pct",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "rpm_lag_1h",
    "rpm_lag_6h",
    "rpm_lag_24h",
    "rpm_rolling_15m",
]


@dataclass
class FeatureSpec:
    """Static description of engineered features — for docs and validation."""

    lag_minutes: tuple[int, ...] = (60, 360, 1440)   # 1h, 6h, 24h
    rolling_window_minutes: int = 15
    cyclical: tuple[str, ...] = ("hour_of_day", "day_of_week")

    def required_history_minutes(self) -> int:
        return max(self.lag_minutes) + self.rolling_window_minutes


SPEC = FeatureSpec()


def _add_cyclical_time(df: pd.DataFrame, ts_col: str = "window_start") -> pd.DataFrame:
    ts = pd.to_datetime(df[ts_col], utc=True)
    hour = ts.dt.hour.astype(float)
    dow = ts.dt.dayofweek.astype(float)
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)
    return df


def _add_lag_features(df: pd.DataFrame, rpm_col: str = "rpm") -> pd.DataFrame:
    df["rpm_lag_1h"] = df[rpm_col].shift(60)
    df["rpm_lag_6h"] = df[rpm_col].shift(360)
    df["rpm_lag_24h"] = df[rpm_col].shift(1440)
    df["rpm_rolling_15m"] = df[rpm_col].rolling(15, min_periods=1).mean()
    return df


def _ensure_resource_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Missing CPU / memory (paper §VII-B) — impute with 0. XGBoost / Isolation
    # Forest tolerate a constant column and the model degrades gracefully as
    # described in the paper.
    for col in ("cpu_usage_pct", "memory_usage_pct"):
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = df[col].fillna(0.0)
    return df


def build_feature_frame(
    df: pd.DataFrame,
    group_col: str = "service_id",
    rpm_col: str = "rpm",
    ts_col: str = "window_start",
) -> pd.DataFrame:
    """Batch feature engineering.

    ``df`` should carry raw metric columns from the ``metrics`` table plus
    ``service_id`` and ``window_start``. Returns a new DataFrame that keeps
    the original identifiers and adds the FEATURE_COLUMNS listed above.
    """
    if df.empty:
        return df

    df = df.sort_values([group_col, ts_col]).reset_index(drop=True)
    df = _ensure_resource_columns(df)

    # Cyclical encodings are stateless, applied on the whole frame.
    df = _add_cyclical_time(df, ts_col=ts_col)

    # Lag / rolling features are per-service. Compute on grouped Series so we
    # never lose the ``service_id`` column across pandas versions.
    grouped = df.groupby(group_col, sort=False)[rpm_col]
    df["rpm_lag_1h"] = grouped.shift(60)
    df["rpm_lag_6h"] = grouped.shift(360)
    df["rpm_lag_24h"] = grouped.shift(1440)
    df["rpm_rolling_15m"] = grouped.transform(
        lambda s: s.rolling(15, min_periods=1).mean()
    )
    return df


def engineer_row(history: list[dict], group_col: str = "service_id") -> pd.DataFrame:
    """Inference-time feature engineering for a single service's latest window.

    ``history`` is a list of MetricSnapshot-shaped dicts (chronologically
    ordered). The last row's features are returned as a one-row DataFrame
    with the columns in FEATURE_COLUMNS.
    """
    if len(history) < SPEC.required_history_minutes():
        raise ValueError(
            f"engineer_row needs at least {SPEC.required_history_minutes()} "
            f"minutes of history, got {len(history)}"
        )

    df = pd.DataFrame(history)
    if "rpm" not in df.columns:
        # For inference, the ML service receives MetricSnapshot which does not
        # carry the rpm aggregate; derive it from request_count (RPM per 1-min
        # window == request_count).
        df["rpm"] = df["request_count"].astype(float)
    if "window_start" not in df.columns:
        df["window_start"] = df["timestamp"]
    if group_col not in df.columns:
        df[group_col] = df.get("service_id", "unknown")

    engineered = build_feature_frame(df, group_col=group_col)
    latest = engineered.iloc[[-1]][FEATURE_COLUMNS].copy()
    if latest.isna().any().any():
        # Should not happen given the length guard above, but fail loudly if
        # so — silent NaNs are the fastest way to poison training/serving.
        raise ValueError(
            "engineer_row produced NaN feature values; supply more history"
        )
    return latest
