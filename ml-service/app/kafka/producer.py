"""Lazy Kafka producer.

Configured from ``app.config.settings`` — if the bootstrap server is
unreachable at first-use time we log and swallow the error so predictions
still return to the caller. The Dashboard Service's circuit breaker + Redis
cache is the safety net for consumers.
"""
from __future__ import annotations

import atexit
import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from confluent_kafka import Producer

from app.config import settings

logger = logging.getLogger(__name__)

_PRODUCER: Producer | None = None
_LOCK = threading.Lock()


def get_producer() -> Producer:
    global _PRODUCER
    if _PRODUCER is not None:
        return _PRODUCER
    with _LOCK:
        if _PRODUCER is None:
            _PRODUCER = Producer(
                {
                    "bootstrap.servers": settings.kafka_bootstrap,
                    "client.id": settings.service_name,
                    "linger.ms": 20,
                    "acks": "all",
                    "compression.type": "lz4",
                }
            )
            atexit.register(_flush_on_exit)
    return _PRODUCER


def _flush_on_exit() -> None:
    if _PRODUCER is not None:
        try:
            _PRODUCER.flush(timeout=5.0)
        except Exception:
            pass


def _envelope(module: str, service_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": "prediction",
        "event_version": "1",
        "occurred_at": datetime.now(UTC).isoformat(),
        "producer": settings.service_name,
        "payload": {
            "service_id": service_id,
            "module": module,
            "model_version": payload.get("model_version"),
            "generated_at": payload.get("generated_at"),
            "value": {k: v for k, v in payload.items() if k not in {"generated_at", "model_version"}},
            "confidence": payload.get("confidence"),
        },
    }


def publish_prediction(module: str, service_id: str | UUID, payload: dict[str, Any]) -> None:
    """Fire-and-forget publish. Failures are logged, not raised."""
    try:
        p = get_producer()
        env = _envelope(module, str(service_id), payload)
        p.produce(
            topic=settings.topic_predictions,
            key=str(service_id).encode("utf-8"),
            value=json.dumps(env).encode("utf-8"),
        )
        p.poll(0)
    except Exception as e:
        logger.warning("Kafka publish failed for module=%s: %s", module, e)
