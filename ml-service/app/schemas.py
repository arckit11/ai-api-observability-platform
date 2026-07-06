"""Pydantic models mirroring ``docs/api-contracts/ml-service-openapi.yaml``.

The OpenAPI spec is the source of truth; models here MUST match it. When the
spec changes, regenerate or update this module in the same commit.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Shared ─────────────────────────────────────────────────────
class ModuleName(str, Enum):
    TRAFFIC = "traffic"
    FAILURE = "failure"
    ANOMALY = "anomaly"
    HEALTH = "health"
    ALERTS = "alerts"


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded", "down"]
    models_loaded: list[ModuleName] = []
    version: str | None = None


class MetricSnapshot(BaseModel):
    service_id: UUID
    timestamp: datetime
    request_count: int = Field(ge=0)
    response_time_mean: float
    response_time_p95: float
    response_time_p99: float
    error_rate: float = Field(ge=0.0, le=1.0)
    cpu_usage_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    memory_usage_pct: float | None = Field(default=None, ge=0.0, le=100.0)


class ModelInfo(BaseModel):
    module: ModuleName
    version: str
    algorithm: str | None = None
    trained_at: datetime
    training_rows: int | None = None
    metrics: dict[str, float] = {}


# ─── Module 1: Traffic ──────────────────────────────────────────
class TrafficPredictionRequest(BaseModel):
    service_id: UUID
    horizon_minutes: Literal[15, 30, 60, 360]
    history: list[MetricSnapshot] = Field(min_length=24)


class ConfidenceInterval(BaseModel):
    lower: float
    upper: float


class TrafficPredictionResponse(BaseModel):
    service_id: UUID
    horizon_minutes: int
    predicted_rpm: float
    confidence_interval: ConfidenceInterval | None = None
    model_version: str
    generated_at: datetime


# ─── Module 2: Failure ──────────────────────────────────────────
class FailurePredictionRequest(BaseModel):
    service_id: UUID
    history: list[MetricSnapshot] = Field(min_length=30)


class FeatureContribution(BaseModel):
    feature: str
    contribution: float


class FailurePredictionResponse(BaseModel):
    service_id: UUID
    failure_probability: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high", "critical"]
    horizon_minutes: int = 30
    contributing_features: list[FeatureContribution] = []
    model_version: str
    generated_at: datetime


# ─── Module 3: Anomaly ──────────────────────────────────────────
class AnomalyRequest(BaseModel):
    service_id: UUID
    snapshot: MetricSnapshot


class AnomalyResponse(BaseModel):
    service_id: UUID
    anomaly_score: float = Field(ge=0.0, le=1.0)
    is_anomaly: bool
    contamination: float
    model_version: str
    generated_at: datetime


# ─── Module 4: Health Score ─────────────────────────────────────
class HealthScoreRequest(BaseModel):
    service_id: UUID
    snapshot: MetricSnapshot
    traffic_stability: float | None = None


class HealthComponents(BaseModel):
    error: float
    latency: float
    traffic: float
    resource: float


class HealthScoreResponse(BaseModel):
    service_id: UUID
    score: float = Field(ge=0.0, le=100.0)
    status: Literal["healthy", "warning", "degraded", "critical"]
    components: HealthComponents
    generated_at: datetime


# ─── Module 5: Alert Prioritization ─────────────────────────────
class AlertContext(BaseModel):
    service_id: UUID
    triggering_metric: Literal["latency", "error_rate", "availability"]
    hour_of_day: int = Field(ge=0, le=23)
    alert_frequency_24h: int = 0
    current_health_score: float | None = None
    failure_prediction_active: bool = False
    service_is_payment_or_auth: bool = False


class AlertPrioritizeRequest(BaseModel):
    alert_id: str
    context: AlertContext


class AlertPrioritizeResponse(BaseModel):
    alert_id: str
    priority: Literal["low", "medium", "high", "critical"]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None
    model_version: str
    generated_at: datetime
