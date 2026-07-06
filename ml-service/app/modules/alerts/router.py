"""Module 5 — alert prioritization (Random Forest).

Phase 0 stub. Real classifier in Phase 3 trained on heuristically labelled
historical alerts (see paper §IV-F).
"""
from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas import AlertContext, AlertPrioritizeRequest, AlertPrioritizeResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _prioritize(ctx: AlertContext) -> tuple[str, str]:
    """Heuristic rules matching the labelling scheme in the paper.

    Real model replaces this with a Random Forest classifier that learned
    these + latent relationships from historical alerts.
    """
    if ctx.failure_prediction_active:
        return "critical", "Coincident failure prediction — auto-critical"
    if ctx.service_is_payment_or_auth:
        base = _base_priority(ctx)
        escalated = _escalate(base)
        return escalated, f"{base} escalated for payment/auth service"
    return _base_priority(ctx), "Base heuristic priority"


def _base_priority(ctx: AlertContext) -> str:
    if ctx.triggering_metric == "availability":
        return "high"
    if ctx.current_health_score is not None and ctx.current_health_score < 50:
        return "high"
    if ctx.alert_frequency_24h >= 10:
        return "medium"
    return "low"


def _escalate(level: str) -> str:
    order = ["low", "medium", "high", "critical"]
    idx = order.index(level)
    return order[min(idx + 1, len(order) - 1)]


@router.post("/prioritize", response_model=AlertPrioritizeResponse)
async def prioritize_alert(req: AlertPrioritizeRequest) -> AlertPrioritizeResponse:
    priority, rationale = _prioritize(req.context)
    return AlertPrioritizeResponse(
        alert_id=req.alert_id,
        priority=priority,
        confidence=None,
        rationale=rationale,
        model_version="stub-0.0.0",
        generated_at=datetime.now(UTC),
    )
