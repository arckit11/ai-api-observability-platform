"""Module 2 — failure prediction (XGBoost Classifier)."""
from datetime import UTC, datetime

from fastapi import APIRouter

from app.features import engineer_row
from app.kafka import publish_prediction
from app.schemas import FailurePredictionRequest, FailurePredictionResponse
from app.training import registry

router = APIRouter(prefix="/predict", tags=["failure"])


def _risk_level(p: float, threshold: float = 0.5) -> str:
    """Risk buckets calibrated around the tuned decision threshold.

    The trained model chooses a recall-weighted threshold at fit time
    (persisted in hyperparams["decision_threshold"]). ``critical`` sits at
    the top decile above threshold, ``high`` above threshold, ``medium``
    just below (probability worth watching), ``low`` otherwise.
    """
    critical = min(0.95, threshold + (1.0 - threshold) * 0.5)
    medium = max(0.05, threshold * 0.6)
    if p >= critical:
        return "critical"
    if p >= threshold:
        return "high"
    if p >= medium:
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
    threshold = float(bundle["meta"]["hyperparams"].get("decision_threshold", 0.5))

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
        risk_level=_risk_level(probability, threshold=threshold),
        horizon_minutes=30,
        contributing_features=contributions,
        model_version=bundle["meta"]["version"],
        generated_at=datetime.now(UTC),
    )
    publish_prediction("failure", req.service_id, resp.model_dump(mode="json"))
    return resp
