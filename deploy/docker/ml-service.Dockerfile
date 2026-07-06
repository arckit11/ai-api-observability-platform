# ML Service (Python 3.11 + FastAPI).
# Build from repo root:
#   docker build -f deploy/docker/ml-service.Dockerfile -t iapi/ml-service:dev .

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for XGBoost / scikit-learn wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY ml-service/pyproject.toml ./pyproject.toml
RUN pip install --upgrade pip && pip install -e .

COPY ml-service/app ./app
COPY ml-service/tests ./tests

RUN mkdir -p /app/models
ENV ML_MODEL_DIR=/app/models

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
