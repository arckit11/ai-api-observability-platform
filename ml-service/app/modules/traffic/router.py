"""Module 1 — traffic forecasting (XGBoost Regressor).

Phase 0 stub: returns a canned response matching the OpenAPI contract so
downstream integration (Dashboard Service, contract tests) can proceed
before the model is trained. The real predictor arrives in Phase 3.
"""
from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas import TrafficPredictionRequest, TrafficPredictionResponse

router = APIRouter(prefix="/predict", tags=["traffic"])


@router.post("/traffic", response_model=TrafficPredictionResponse)
async def predict_traffic(req: TrafficPredictionRequest) -> TrafficPredictionResponse:
    # Naive baseline: report the last observed RPM. Replaced in Phase 3 by an
    # XGBoost Regressor over lag / rolling / cyclical-time features.
    last = req.history[-1]
    predicted = float(last.request_count)
    return TrafficPredictionResponse(
        service_id=req.service_id,
        horizon_minutes=req.horizon_minutes,
        predicted_rpm=predicted,
        model_version="stub-0.0.0",
        generated_at=datetime.now(UTC),
    )
