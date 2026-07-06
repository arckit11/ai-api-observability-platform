"""Train the Traffic Prediction module.

Target: RPM at horizon h ahead. Trained per-horizon models are keyed inside
the single joblib bundle by ``models["h_<minutes>"]`` for lookup at
inference.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from app.features import FEATURE_COLUMNS, build_feature_frame
from app.training import registry

HORIZONS_MIN = (15, 30, 60, 360)


def _make_targets(df: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    """For each horizon add ``target_<h>`` = rpm shifted -h minutes per service."""
    df = df.sort_values(["service_id", "window_start"]).reset_index(drop=True)
    for h in horizons:
        df[f"target_{h}"] = df.groupby("service_id")["rpm"].shift(-h)
    return df


def _chronological_split(df: pd.DataFrame, test_frac: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values("window_start").reset_index(drop=True)
    cut = int(len(df) * (1.0 - test_frac))
    return df.iloc[:cut], df.iloc[cut:]


def train(df: pd.DataFrame, model_dir: Path) -> dict:
    engineered = build_feature_frame(df)
    engineered = _make_targets(engineered, HORIZONS_MIN)

    # Drop rows with any NaN in features OR any target we're training.
    target_cols = [f"target_{h}" for h in HORIZONS_MIN]
    engineered = engineered.dropna(subset=FEATURE_COLUMNS + target_cols).reset_index(drop=True)
    if engineered.empty:
        raise RuntimeError(
            "No usable rows after feature engineering. Extend the history "
            "window (--days) so that lag_24h features are populated."
        )

    train_df, test_df = _chronological_split(engineered)
    X_train = train_df[FEATURE_COLUMNS].values
    X_test = test_df[FEATURE_COLUMNS].values

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    hyperparams = dict(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        tree_method="hist",
        n_jobs=-1,
        random_state=42,
    )

    models_by_horizon: dict[str, XGBRegressor] = {}
    metrics: dict[str, float] = {}
    for h in HORIZONS_MIN:
        y_train = train_df[f"target_{h}"].values
        y_test = test_df[f"target_{h}"].values

        model = XGBRegressor(**hyperparams)
        model.fit(X_train_s, y_train)
        y_pred = model.predict(X_test_s)

        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mape = float(mean_absolute_percentage_error(y_test, y_pred))
        metrics[f"rmse_h{h}"] = rmse
        metrics[f"mape_h{h}"] = mape
        models_by_horizon[f"h_{h}"] = model

    meta = registry.save(
        module="traffic",
        model=models_by_horizon,
        scaler=scaler,
        feature_cols=FEATURE_COLUMNS,
        metrics=metrics,
        hyperparams=hyperparams,
        training_rows=len(train_df),
        algorithm="xgboost.XGBRegressor (per-horizon)",
        model_dir=model_dir,
    )
    return {
        "model_version": meta["version"],
        "training_rows": meta["training_rows"],
        "metrics": metrics,
    }
