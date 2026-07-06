"""Kafka producer for the ``predictions`` and ``service-health`` topics.

Envelope schema defined in ``docs/api-contracts/kafka-events.md``.
"""

from app.kafka.producer import get_producer, publish_prediction

__all__ = ["get_producer", "publish_prediction"]
