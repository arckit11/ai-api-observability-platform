"""Module 5 — alert prioritization (Random Forest)."""
from datetime import UTC, datetime

from fastapi import APIRouter

from app.kafka import publish_prediction
from app.modules.alerts.train import ALERT_FEATURES
from app.schemas import AlertContext, AlertPrioritizeRequest, AlertPrioritizeResponse
from app.training import registry

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _heuristic(ctx: AlertContext) -> tuple[str, str]:
    if ctx.failure_prediction_active:
        return "critical", "Coincident failure prediction — auto-critical"
    if ctx.service_is_payment_or_auth:
        base = _base_priority(ctx)
        order = ["low", "medium", "high", "critical"]
        idx = order.index(base)
        return order[min(idx + 1, len(order) - 1)], (
            f"{base} escalated for payment/auth service"
        )
    return _base_priority(ctx), "Base heuristic priority"


def _base_priority(ctx: AlertContext) -> str:
    if ctx.triggering_metric == "availability":
        return "high"
    if ctx.current_health_score is not None and ctx.current_health_score < 50:
        return "high"
    if ctx.alert_frequency_24h >= 10:
        return "medium"
    return "low"


def _context_to_row(ctx: AlertContext) -> list[float]:
    return [
        1.0 if ctx.triggering_metric == "latency" else 0.0,
        1.0 if ctx.triggering_metric == "error_rate" else 0.0,
        1.0 if ctx.triggering_metric == "availability" else 0.0,
        float(ctx.hour_of_day),
        float(ctx.alert_frequency_24h),
        float(ctx.current_health_score if ctx.current_health_score is not None else 75.0),
        1.0 if ctx.failure_prediction_active else 0.0,
        1.0 if ctx.service_is_payment_or_auth else 0.0,
    ]


@router.post("/prioritize", response_model=AlertPrioritizeResponse)
async def prioritize_alert(req: AlertPrioritizeRequest) -> AlertPrioritizeResponse:
    bundle = registry.get("alerts")

    if bundle is None:
        priority, rationale = _heuristic(req.context)
        resp = AlertPrioritizeResponse(
            alert_id=req.alert_id,
            priority=priority,
            confidence=None,
            rationale=rationale,
            model_version="stub-0.0.0",
            generated_at=datetime.now(UTC),
        )
        publish_prediction("alerts", req.context.service_id, resp.model_dump(mode="json"))
        return resp

    packaged = bundle["model"]
    clf = packaged["clf"]
    le = packaged["label_encoder"]

    x = [_context_to_row(req.context)]
    proba = clf.predict_proba(x)[0]
    pred_idx = int(proba.argmax())
    priority = str(le.inverse_transform([pred_idx])[0])
    confidence = float(proba[pred_idx])

    resp = AlertPrioritizeResponse(
        alert_id=req.alert_id,
        priority=priority,
        confidence=confidence,
        rationale=f"RF classification over {len(ALERT_FEATURES)} context features",
        model_version=bundle["meta"]["version"],
        generated_at=datetime.now(UTC),
    )
    publish_prediction("alerts", req.context.service_id, resp.model_dump(mode="json"))
    return resp
