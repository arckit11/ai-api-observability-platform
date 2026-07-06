"""FastAPI application entrypoint.

Routers for each module are wired here. Concrete inference and training
lives in ``app.modules.<name>``; this file is only composition and
cross-cutting concerns (health, logging, error handlers).
"""
from datetime import UTC, datetime

from fastapi import FastAPI

from app import __version__
from app.modules.alerts.router import router as alerts_router
from app.modules.anomaly.router import router as anomaly_router
from app.modules.failure.router import router as failure_router
from app.modules.health.router import router as health_router
from app.modules.traffic.router import router as traffic_router
from app.schemas import HealthStatus, ModuleName

app = FastAPI(
    title="ML Prediction Service",
    version=__version__,
    description=(
        "Predictive monitoring endpoints for the AI-Powered API Performance "
        "Analytics Platform. Contract: docs/api-contracts/ml-service-openapi.yaml"
    ),
)


@app.get("/healthz", response_model=HealthStatus, tags=["health"])
async def healthz() -> HealthStatus:
    return HealthStatus(status="ok", version=__version__)


@app.get("/readyz", response_model=HealthStatus, tags=["health"])
async def readyz() -> HealthStatus:
    # Phase 0 stub — real readiness checks (model files present, kafka reachable)
    # arrive with the module implementations.
    return HealthStatus(
        status="ok",
        version=__version__,
        models_loaded=[],
    )


app.include_router(traffic_router)
app.include_router(failure_router)
app.include_router(anomaly_router)
app.include_router(health_router)
app.include_router(alerts_router)


@app.get("/admin/models", tags=["admin"])
async def list_models() -> list[dict]:
    # Placeholder; real listing reads app.state.models registered by loaders.
    return []


@app.post("/admin/models/{module}/reload", tags=["admin"])
async def reload_model(module: ModuleName) -> dict:
    return {
        "module": module,
        "version": "0.0.0",
        "trained_at": datetime.now(UTC).isoformat(),
        "reloaded": True,
    }
