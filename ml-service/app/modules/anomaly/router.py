"""Module 3 — anomaly detection (Isolation Forest).

Isolation Forest scores each observation by the average path length
required to isolate it in random-split trees; shorter path = more
anomalous. We map ``model.score_samples`` (higher = normal) into [0, 1]
where 1 = most anomalous, so the response field name matches intuition.
"""
from datetime import UTC, datetime

from fastapi import APIRouter

from app.kafka import publish_prediction
from app.schemas import AnomalyRequest, AnomalyResponse
from app.training import registry

router = APIRouter(prefix="/predict", tags=["anomaly"])

DEFAULT_CONTAMINATION = 0.05
FEATURE_COLS_INFERENCE = [
    "request_count",
    "response_time_mean",
    "response_time_p95",
    "response_time_p99",
    "error_rate",
    "cpu_usage_pct",
    "memory_usage_pct",
]


def _score_to_zero_one(raw: float, floor: float, ceil: float) -> float:
    """Map isolation-forest score (higher=normal) into [0,1] anomaly-score."""
    if ceil <= floor:
        return 0.5
    normal = (raw - floor) / (ceil - floor)
    return float(max(0.0, min(1.0, 1.0 - normal)))


@router.post("/anomaly", response_model=AnomalyResponse)
async def detect_anomaly(req: AnomalyRequest) -> AnomalyResponse:
    bundle = registry.get("anomaly")
    s = req.snapshot

    if bundle is None:
        score = min(1.0, max(s.response_time_p99 / 5000.0, s.error_rate))
        resp = AnomalyResponse(
            service_id=req.service_id,
            anomaly_score=score,
            is_anomaly=score >= (1 - DEFAULT_CONTAMINATION),
            contamination=DEFAULT_CONTAMINATION,
            model_version="stub-0.0.0",
            generated_at=datetime.now(UTC),
        )
        publish_prediction("anomaly", req.service_id, resp.model_dump(mode="json"))
        return resp

    # Inference on a single snapshot uses only the always-available columns
    # (no lag features — those need history). We reindex the incoming row
    # against the model's feature_cols to keep the shape consistent.
    feature_cols = bundle["feature_cols"]
    values = []
    snapshot_map = {
        "request_count": s.request_count,
        "response_time_mean": s.response_time_mean,
        "response_time_p95": s.response_time_p95,
        "response_time_p99": s.response_time_p99,
        "error_rate": s.error_rate,
        "cpu_usage_pct": s.cpu_usage_pct or 0.0,
        "memory_usage_pct": s.memory_usage_pct or 0.0,
    }
    for col in feature_cols:
        values.append(float(snapshot_map.get(col, 0.0)))
    X = bundle["scaler"].transform([values])

    raw_score = float(bundle["model"].score_samples(X)[0])
    contamination = float(bundle["meta"]["hyperparams"].get("contamination", DEFAULT_CONTAMINATION))
    is_anom = bool(bundle["model"].predict(X)[0] == -1)

    # Rough calibration: use offset_ (decision threshold) as a soft floor
    # for normalisation. Ceiling defaults to 0 (score_samples upper bound).
    floor = float(getattr(bundle["model"], "offset_", -0.5))
    score01 = _score_to_zero_one(raw_score, floor=floor - 0.1, ceil=0.0)

    resp = AnomalyResponse(
        service_id=req.service_id,
        anomaly_score=score01,
        is_anomaly=is_anom,
        contamination=contamination,
        model_version=bundle["meta"]["version"],
        generated_at=datetime.now(UTC),
    )
    publish_prediction("anomaly", req.service_id, resp.model_dump(mode="json"))
    return resp
