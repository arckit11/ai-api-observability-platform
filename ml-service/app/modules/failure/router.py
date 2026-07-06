"""Module 2 — failure prediction (XGBoost Classifier)."""
from datetime import UTC, datetime

from fastapi import APIRouter

from app.features import engineer_row
from app.kafka import publish_prediction
from app.schemas import FailurePredictionRequest, FailurePredictionResponse
from app.training import registry

router = APIRouter(prefix="/predict", tags=["failure"])


def _risk_level(p: float) -> str:
    if p >= 0.75:
        return "critical"
    if p >= 0.5:
        return "high"
    if p >= 0.25:
        return "medium"
    return "low"


def _heuristic_probability(history: list) -> float:
    """Baseline used only when the trained model isn't loaded yet."""
    recent = history[-30:]
    err = sum(s.error_rate for s in recent) / len(recent)
    p99_breaches = sum(1 for s in recent if s.response_time_p99 > 2000) / len(recent)
    return min(1.0, 0.5 * err + 0.5 * p99_breaches)


@router.post("/failure", response_model=FailurePredictionResponse)
async def predict_failure(req: FailurePredictionRequest) -> FailurePredictionResponse:
    bundle = registry.get("failure")

    if bundle is None:
        probability = _heuristic_probability(req.history)
        resp = FailurePredictionResponse(
            service_id=req.service_id,
            failure_probability=probability,
            risk_level=_risk_level(probability),
            horizon_minutes=30,
            model_version="stub-0.0.0",
            generated_at=datetime.now(UTC),
        )
        publish_prediction("failure", req.service_id, resp.model_dump(mode="json"))
        return resp

    history_dicts = [s.model_dump(mode="python") for s in req.history]
    for h in history_dicts:
        h["service_id"] = str(h["service_id"])
    row = engineer_row(history_dicts)
    X = bundle["scaler"].transform(row.values)
    probability = float(bundle["model"].predict_proba(X)[0, 1])

    # Best-effort per-feature contributions via feature importances.
    booster = bundle["model"]
    fmap = getattr(booster, "feature_importances_", None)
    contributions = []
    if fmap is not None:
        pairs = sorted(
            zip(bundle["feature_cols"], fmap.tolist(), strict=False),
            key=lambda x: -x[1],
        )[:5]
        contributions = [
            {"feature": name, "contribution": float(imp)} for name, imp in pairs
        ]

    resp = FailurePredictionResponse(
        service_id=req.service_id,
        failure_probability=probability,
        risk_level=_risk_level(probability),
        horizon_minutes=30,
        contributing_features=contributions,
        model_version=bundle["meta"]["version"],
        generated_at=datetime.now(UTC),
    )
    publish_prediction("failure", req.service_id, resp.model_dump(mode="json"))
    return resp
