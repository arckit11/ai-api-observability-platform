# Architecture

Reference implementation of the platform described in the accompanying
research paper. This doc supplements the paper with the concrete artifacts
in this repo:
which service lives where, what topics carry what payloads, and where the
contracts sit.

## High-level flow

```
┌──────────────┐       ┌────────────────┐        ┌────────────────────┐
│    Client    │──────▶│  Gateway (8080)│──────▶ │  auth / registry / │
│ Applications │       │  Spring Cloud  │        │  analytics / ...    │
└──────────────┘       └───────┬────────┘        └────────────────────┘
                               │ api-logs (Kafka)
                               ▼
                        ┌──────────────────┐
                        │ Metrics Collector│──── writes ────▶ Postgres.api_logs
                        └──────────────────┘                       (dedup_key unique)
                               │ (raw rows)
                               ▼
                        ┌──────────────────┐
                        │ Analytics (8084) │──── metrics ────▶ Kafka `metrics`
                        └───────┬──────────┘                       │
                                │ history endpoint                 │
                                ▼                                  │
                        ┌──────────────────┐                       │
                        │ ML Service (8000)│◀──────────────────────┘
                        │  5 modules       │──── predictions ─▶ Kafka `predictions`
                        └───────┬──────────┘                       │
                                │                                  ▼
                                ▼                          ┌──────────────────┐
                        Dashboard (8085) ◀── Redis cache ── │ Dashboard cache  │
                        via circuit-breaker                 └──────────────────┘
```

## Service inventory

| Service | Directory | Port | Depends on |
|---|---|---|---|
| Gateway | `backend/gateway-service` | 8080 | Auth, Kafka |
| Auth | `backend/auth-service` | 8081 | Postgres |
| Registry | `backend/registry-service` | 8082 | Postgres |
| Metrics Collector | `backend/metrics-collector` | 8083 | Kafka, Postgres |
| Analytics | `backend/analytics-service` | 8084 | Postgres, Redis, Kafka |
| Dashboard | `backend/dashboard-service` | 8085 | Analytics, ML, Redis |
| ML Service | `ml-service/` | 8000 | Analytics (history), Kafka |

## Contracts

- **ML endpoints**: `docs/api-contracts/ml-service-openapi.yaml` — source of
  truth for the Python subsystem. Dashboard Service generates a typed REST
  client from this file.
- **Backend endpoints**: `docs/api-contracts/backend-openapi.yaml` — public
  surface exposed by the gateway.
- **Kafka events**: `docs/api-contracts/kafka-events.md` — envelope + per-topic
  payload schemas. Mirrored by `common-events` (Java) and pydantic models in
  the ML service.

## Kafka topics

| Topic | Partitions | Key | Producer | Consumer(s) |
|---|---|---|---|---|
| `api-logs` | 6 | service_id | Gateway | Metrics Collector |
| `api-logs-dlq` | 1 | — | Metrics Collector | manual |
| `metrics` | 3 | service_id | Analytics | Dashboard, ML |
| `alerts` | 3 | service_id | Analytics | Dashboard |
| `predictions` | 3 | service_id | ML | Dashboard |
| `service-health` | 1 | service_id | ML | Dashboard |

Partition counts are baseline defaults for local dev; production tuning
belongs in the ops runbook.

## Database

Seven tables, described in the paper §III-I:

| Table | Notes |
|---|---|
| `users` | ADMIN / DEVELOPER / VIEWER role check constraint |
| `services` | API Registry — `capture_telemetry` flag gates gateway logging |
| `api_logs` | `dedup_key` unique index for at-least-once Kafka delivery |
| `metrics` | Range-partitioned by `window_start` (monthly), default partition |
| `alerts` | Priority column populated post-hoc by ML |
| `predictions` | JSONB `value`, indexed by (service_id, module, generated_at) |
| `ml_model_results` | One row per training run, unique `is_active` per module |

Migrations are Flyway SQL under `db/migrations/`.

## Shared modules (Maven)

| Module | Purpose |
|---|---|
| `common-dto` | Request/response DTOs shared across services |
| `common-events` | Kafka envelope + payload records |
| `common-security` | JWT filter, RBAC helpers, `Role` enum |
| `common-utils` | Dedup-key hashing, time-window math |
| `common-exceptions` | RFC 7807 problem-detail builders |

Backend services declare shared modules as `compile` deps in their pom.
Version bumps flow through the parent POM's `dependencyManagement`.

## Resilience

- **Dashboard → ML**: Resilience4j circuit breaker (`ml-service` instance in
  `dashboard-service/application.yml`). On open circuit → serve the last
  cached prediction from Redis instead of failing the request.
- **Metrics Collector → api_logs**: `dedup_key` unique index makes at-least-once
  Kafka delivery safe; malformed events land in `api-logs-dlq` instead of
  poisoning the partition.
- **Analytics reads**: Redis-cached latest metrics per service with short TTL
  (30s) to absorb dashboard fan-out.

## Roadmap → files

| Phase | Adds |
|---|---|
| **0 (done)** | Infra, contracts, migrations, module skeletons |
| 1 | Gateway JWT filter, Kafka producer, Registry CRUD, Collector consumer |
| 2 | Analytics windowing job, Redis cache, synthetic-data generator |
| 3 | Real ML modules (XGBoost, Isolation Forest, Random Forest), training jobs |
| 4 | Dashboard aggregation + circuit-breaker wiring |
| 5 | Evaluation harness (RMSE, MAPE, precision, recall, latency) |

## Not in scope (v1)

Explicitly deferred to future work (paper §VIII):

- Online / incremental learning
- OpenTelemetry span integration
- Multi-tenant isolation
- Temporal Fusion Transformer for long-horizon traffic
- Root-cause localisation
