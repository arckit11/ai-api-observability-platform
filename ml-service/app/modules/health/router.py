"""Module 4 — composite health score.

Paper §IV-E: H = 100 · (0.30·ê + 0.30·l̂ + 0.20·t̂ + 0.20·r̂). All four
inputs are normalised to [0, 1] with the convention that 1 = healthy.
Missing resource signals (cpu/memory) trigger renormalisation over the
available weights so a service without a host agent still produces a
score.
"""
from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas import (
    HealthComponents,
    HealthScoreRequest,
    HealthScoreResponse,
)

router = APIRouter(prefix="/score", tags=["score"])

WEIGHTS = {"error": 0.30, "latency": 0.30, "traffic": 0.20, "resource": 0.20}


def _status(score: float) -> str:
    if score >= 90:
        return "healthy"
    if score >= 70:
        return "warning"
    if score >= 50:
        return "degraded"
    return "critical"


@router.post("/health", response_model=HealthScoreResponse)
async def score_health(req: HealthScoreRequest) -> HealthScoreResponse:
    s = req.snapshot

    error_component = max(0.0, 1.0 - s.error_rate)                      # 1 = zero errors
    latency_component = max(0.0, 1.0 - min(1.0, s.response_time_p99 / 5000.0))
    traffic_component = req.traffic_stability if req.traffic_stability is not None else 0.5

    if s.cpu_usage_pct is None and s.memory_usage_pct is None:
        # Renormalise over the three available signals.
        active = ["error", "latency", "traffic"]
        total_w = sum(WEIGHTS[k] for k in active)
        weighted = (
            WEIGHTS["error"] * error_component
            + WEIGHTS["latency"] * latency_component
            + WEIGHTS["traffic"] * traffic_component
        ) / total_w
        resource_component = 0.0
    else:
        cpu = (s.cpu_usage_pct or 0.0) / 100.0
        mem = (s.memory_usage_pct or 0.0) / 100.0
        resource_component = max(0.0, 1.0 - max(cpu, mem))
        weighted = (
            WEIGHTS["error"] * error_component
            + WEIGHTS["latency"] * latency_component
            + WEIGHTS["traffic"] * traffic_component
            + WEIGHTS["resource"] * resource_component
        )

    score = 100.0 * weighted
    return HealthScoreResponse(
        service_id=req.service_id,
        score=score,
        status=_status(score),
        components=HealthComponents(
            error=error_component,
            latency=latency_component,
            traffic=traffic_component,
            resource=resource_component,
        ),
        generated_at=datetime.now(UTC),
    )
