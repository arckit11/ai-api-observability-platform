"""Smoke tests for the Phase 0 stub endpoints.

They exercise the OpenAPI contract shape without depending on trained
models. Once Phase 3 lands, replace with real prediction tests + fixtures.
"""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _snapshot(offset_minutes: int = 0) -> dict:
    return {
        "service_id": str(uuid4()),
        "timestamp": (datetime.now(UTC) - timedelta(minutes=offset_minutes)).isoformat(),
        "request_count": 100,
        "response_time_mean": 120.0,
        "response_time_p95": 200.0,
        "response_time_p99": 300.0,
        "error_rate": 0.01,
    }


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_score_health_returns_score_and_status():
    body = {
        "service_id": str(uuid4()),
        "snapshot": _snapshot(),
    }
    r = client.post("/score/health", json=body)
    assert r.status_code == 200
    j = r.json()
    assert 0 <= j["score"] <= 100
    assert j["status"] in {"healthy", "warning", "degraded", "critical"}
