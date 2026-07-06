"""Feature engineering pipeline.

Turns raw per-minute metric snapshots into the feature matrix used across
all XGBoost / Random Forest / Isolation Forest models.
"""

from app.features.pipeline import (
    FEATURE_COLUMNS,
    build_feature_frame,
    engineer_row,
)

__all__ = ["FEATURE_COLUMNS", "build_feature_frame", "engineer_row"]
