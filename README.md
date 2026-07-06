# AI-Powered API Performance Analytics Platform

An event-driven microservices platform for real-time API observability with
machine-learning-based predictive monitoring. Combines a Java / Spring Boot
backend pipeline with a Python / FastAPI ML subsystem that anticipates
degradation before it hits users — rather than reacting to threshold
breaches after the fact.

Reference implementation of the accompanying research paper (kept
locally, not included in this repo).

## Highlights

- **Contract-first**: OpenAPI + Kafka event schemas are the source of truth
  between the two subsystems. Both sides generate clients / stubs from the
  same specs.
- **Event-driven**: Every API request is captured by the gateway and
  streamed through Kafka. Downstream services never block the hot path.
- **Predictive, not reactive**: Five ML modules — traffic forecasting,
  failure prediction, anomaly detection, composite health scoring, and
  alert prioritization — are served as first-class REST endpoints, not
  add-ons.
- **Resilient by design**: Dedup keys absorb Kafka at-least-once
  duplicates, a dead-letter topic isolates poison pills, and a circuit
  breaker fronts the ML calls so dashboards degrade gracefully.

## Subsystems

| Subsystem | Language | Role |
|---|---|---|
| Backend | Java 21, Spring Boot 3 | Telemetry ingestion, aggregation, dashboard APIs |
| ML Service | Python 3.11, FastAPI | 5 predictive modules (traffic, failure, anomaly, health, alerts) |
| Shared libs | Maven multi-module | DTOs, Kafka events, JWT filters, RFC 7807 errors |

## Service inventory

| Service | Port | Responsibility |
|---|---|---|
| `gateway-service` | 8080 | Spring Cloud Gateway — JWT auth, RBAC, telemetry publish |
| `auth-service` | 8081 | Login, JWT issue / refresh |
| `registry-service` | 8082 | CRUD for monitored services |
| `metrics-collector` | 8083 | Kafka consumer → `api_logs` (dedup + DLQ) |
| `analytics-service` | 8084 | RPM, P95 / P99, error rate; historical metrics API |
| `dashboard-service` | 8085 | Aggregates Analytics + ML; circuit-breaker fallback |
| `ml-service` | 8000 | Five prediction endpoints |

## ML modules

| Path | Module | Algorithm |
|---|---|---|
| `POST /predict/traffic` | Traffic forecasting | XGBoost Regressor |
| `POST /predict/failure` | Failure prediction | XGBoost Classifier |
| `POST /predict/anomaly` | Anomaly detection | Isolation Forest |
| `POST /score/health` | Composite health score | Weighted linear combination |
| `POST /alerts/prioritize` | Alert prioritization | Random Forest |

Feature set (per Table II of the paper): request count, response time
mean / P95 / P99, error rate, CPU / memory usage, cyclical time encodings,
and engineered lag / rolling features.

## Repository layout

```
.
├── docker-compose.yml         # postgres, redis, kafka, kafka-ui
├── Makefile                   # up / down / psql / kafka-topics / ...
├── .env.example
├── db/migrations/             # Flyway SQL — 7 tables, partitioned metrics
├── docs/
│   ├── architecture.md
│   └── api-contracts/         # OpenAPI + Kafka event contracts
├── backend/                   # Maven multi-module (Java 21)
│   ├── shared/                # common-{dto,events,security,utils,exceptions}
│   ├── gateway-service/
│   ├── auth-service/
│   ├── registry-service/
│   ├── metrics-collector/
│   ├── analytics-service/
│   └── dashboard-service/
├── ml-service/                # FastAPI + XGBoost + scikit-learn
├── synthetic-data/            # simulator for bootstrap training data
└── deploy/
    ├── docker/                # per-service Dockerfiles
    └── k8s/                   # kustomize base + local / staging / prod overlays
```

## Quick start

```bash
cp .env.example .env
make up               # start postgres, redis, kafka, kafka-ui
make ps               # verify containers healthy
make kafka-topics     # should list api-logs, metrics, alerts, predictions, ...
```

- Kafka UI: <http://localhost:8090>
- ML Service (once running locally): <http://localhost:8000/docs>

## Data & event flow

```
Client ─▶ Gateway ─── api-logs ───▶ Metrics Collector ─▶ Postgres.api_logs
                          (Kafka)                             │
                                                              ▼
                                                       Analytics Service
                                                       │        │
                                        history endpoint        │ metrics topic
                                                       ▼        ▼
                                                   ML Service ─── predictions ─▶ Dashboard
                                                                                    ▲
                                                                              Redis cache
                                                                              (last-known
                                                                              fallback via
                                                                              circuit breaker)
```

## Roadmap

| Phase | Scope |
|---|---|
| **0 (done)** | Infra, contracts, DB schema, module skeletons |
| 1 | Auth + Gateway + Registry + Metrics Collector |
| 2 | Analytics Service + synthetic data generator |
| 3 | ML Service — real models (XGBoost, Isolation Forest, Random Forest) |
| 4 | Dashboard Service + circuit breaker + end-to-end wiring |
| 5 | Evaluation harness (RMSE / MAPE, precision / recall, latency) |

See `docs/architecture.md` for the full design.

## Tech stack

Java 21 · Spring Boot 3 · Spring Cloud Gateway · Spring Security + JWT ·
Apache Kafka · PostgreSQL 15 · Redis 7 · Python 3.11 · FastAPI ·
scikit-learn · XGBoost · joblib · Docker Compose · Kubernetes (kustomize).

## Authors

- **Ayushi Singh** — Backend Engineering (System architecture, Spring Boot, Kafka)
- **Arckit Arihant** — Machine Learning Engineering (Predictive models, FastAPI, anomaly detection)

## License

TBD.
