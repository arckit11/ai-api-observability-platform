"""Module 2 — failure prediction (XGBoost Classifier).

Phase 0 stub. Real model in Phase 3 optimises for recall (missed failures
are more costly than false alarms).
"""
from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas import FailurePredictionRequest, FailurePredictionResponse

router = APIRouter(prefix="/predict", tags=["failure"])


def _risk_level(p: float) -> str:
    if p >= 0.75:
        return "critical"
    if p >= 0.5:
        return "high"
    if p >= 0.25:
        return "medium"
    return "low"


@router.post("/failure", response_model=FailurePredictionResponse)
async def predict_failure(req: FailurePredictionRequest) -> FailurePredictionResponse:
    # Naive heuristic baseline until the real classifier ships: probability
    # scales with recent error rate + P99 latency breaches.
    recent = req.history[-30:]
    err = sum(s.error_rate for s in recent) / len(recent)
    p99_breaches = sum(1 for s in recent if s.response_time_p99 > 2000) / len(recent)
    probability = min(1.0, 0.5 * err + 0.5 * p99_breaches)

    return FailurePredictionResponse(
        service_id=req.service_id,
        failure_probability=probability,
        risk_level=_risk_level(probability),
        horizon_minutes=30,
        model_version="stub-0.0.0",
        generated_at=datetime.now(UTC),
    )
