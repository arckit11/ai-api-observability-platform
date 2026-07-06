"""Data-loading clients.

At Phase 3 the ML service reads training data directly from the platform
Postgres. Once the Analytics Service HTTP endpoint is wired in Phase 4, the
same interface will be served over HTTP with no change to callers.
"""

from app.clients.metrics import load_metrics, load_metrics_for_service

__all__ = ["load_metrics", "load_metrics_for_service"]
