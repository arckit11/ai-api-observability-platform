"""Filesystem-backed model registry.

Each module persists a single ``<module>.joblib`` bundle containing:
    {
        "model":         fitted sklearn / xgboost object,
        "scaler":        fitted StandardScaler or None,
        "feature_cols":  list[str] (column order at fit time),
        "meta": {
            "module":         "<name>",
            "version":        "<UTC timestamp>",
            "algorithm":      "xgboost.XGBRegressor" | ...,
            "trained_at":     ISO-8601 UTC,
            "training_rows":  int,
            "metrics":        dict[str, float],
            "hyperparams":    dict[str, Any],
        }
    }

Runtime code loads bundles lazily via :func:`get`; the router modules call
``get("traffic")`` etc. and cache the result.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

from app.config import settings


_LOCK = threading.RLock()
_CACHE: dict[str, dict] = {}


def _artifact_path(module: str, model_dir: Path | None = None) -> Path:
    d = model_dir or settings.model_dir
    return d / f"{module}.joblib"


def make_version() -> str:
    """UTC timestamp string, resolution: seconds. Stable and sortable."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def save(
    module: str,
    *,
    model: Any,
    scaler: Any | None,
    feature_cols: list[str],
    metrics: dict[str, float],
    hyperparams: dict[str, Any],
    training_rows: int,
    algorithm: str,
    model_dir: Path | None = None,
) -> dict:
    """Persist a trained bundle and return its metadata dict."""
    version = make_version()
    meta = {
        "module": module,
        "version": version,
        "algorithm": algorithm,
        "trained_at": datetime.now(UTC).isoformat(),
        "training_rows": training_rows,
        "metrics": metrics,
        "hyperparams": hyperparams,
    }
    bundle = {
        "model": model,
        "scaler": scaler,
        "feature_cols": list(feature_cols),
        "meta": meta,
    }
    path = _artifact_path(module, model_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)

    with _LOCK:
        _CACHE[module] = bundle
    return meta


def get(module: str, model_dir: Path | None = None) -> dict | None:
    """Load (or return cached) bundle for ``module``.

    Returns None if the artifact isn't on disk yet — routers should fall
    back to the Phase 0 stub behaviour and surface 503 to callers.
    """
    with _LOCK:
        if module in _CACHE:
            return _CACHE[module]

    path = _artifact_path(module, model_dir)
    if not path.exists():
        return None

    bundle = joblib.load(path)
    with _LOCK:
        _CACHE[module] = bundle
    return bundle


def reload(module: str, model_dir: Path | None = None) -> dict | None:
    """Force a re-read from disk. Used by the admin reload endpoint."""
    with _LOCK:
        _CACHE.pop(module, None)
    return get(module, model_dir)


def list_loaded() -> list[dict]:
    with _LOCK:
        return [dict(b["meta"]) for b in _CACHE.values()]
