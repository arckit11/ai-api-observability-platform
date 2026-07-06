"""Module 3 — anomaly detection (Isolation Forest).

Phase 0 stub. Real detector in Phase 3 with contamination swept over
[0.01, 0.10] on synthetic anomaly-injected data.
"""
from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas import AnomalyRequest, AnomalyResponse

router = APIRouter(prefix="/predict", tags=["anomaly"])

DEFAULT_CONTAMINATION = 0.05


@router.post("/anomaly", response_model=AnomalyResponse)
async def detect_anomaly(req: AnomalyRequest) -> AnomalyResponse:
    # Naive baseline: flag high P99 or very high error rate.
    s = req.snapshot
    score = min(1.0, max(s.response_time_p99 / 5000.0, s.error_rate))
    return AnomalyResponse(
        service_id=req.service_id,
        anomaly_score=score,
        is_anomaly=score >= (1 - DEFAULT_CONTAMINATION),
        contamination=DEFAULT_CONTAMINATION,
        model_version="stub-0.0.0",
        generated_at=datetime.now(UTC),
    )
