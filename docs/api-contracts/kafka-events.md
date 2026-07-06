# Kafka Event Contracts

All events on the platform share a common envelope so consumers can rely on
a uniform header regardless of topic. The envelope is defined in the
`common-events` Maven module and mirrored in the ML service.

## Envelope

```json
{
  "event_id":     "uuid v4",
  "event_type":   "api-log | metric | alert | prediction | service-health",
  "event_version": "1",
  "occurred_at":   "ISO-8601 UTC",
  "producer":     "service-name",
  "trace_id":     "optional; propagated from gateway",
  "payload":       { ... topic-specific ... }
}
```

Producers set `event_id` deterministically (see per-topic dedup keys) so that
Kafka's at-least-once delivery can be handled with idempotent writes.

## Topics

| Topic | Partitions | Producer | Consumer(s) | Payload |
|---|---|---|---|---|
| `api-logs` | 6 | Gateway | Metrics Collector | `ApiLogPayload` |
| `api-logs-dlq` | 1 | Metrics Collector | — (manual triage) | Raw event + `error` |
| `metrics` | 3 | Analytics | Dashboard, ML | `MetricPayload` |
| `alerts` | 3 | Analytics | Dashboard | `AlertPayload` |
| `predictions` | 3 | ML Service | Dashboard | `PredictionPayload` |
| `service-health` | 1 | ML Service | Dashboard | `HealthPayload` |

### `api-logs` → `ApiLogPayload`

```json
{
  "service_id":     "uuid",
  "endpoint":       "/orders/{id}",
  "http_method":    "GET|POST|PUT|PATCH|DELETE",
  "status_code":     200,
  "response_time_ms": 143,
  "user_agent":     "...",
  "client_ip":      "203.0.113.10",
  "user_id":        "uuid | null",
  "request_bytes":   512,
  "response_bytes":  2048,
  "timestamp":      "ISO-8601 UTC",
  "dedup_key":      "sha256(service_id|endpoint|timestamp|status_code|user_id)"
}
```

Consumers MUST use `dedup_key` (unique index on `api_logs.dedup_key`) to
absorb duplicates. Malformed events are routed to `api-logs-dlq` with an
`error` field describing the validation failure — the consumer never fails
the whole partition on a single bad message.

### `metrics` → `MetricPayload`

```json
{
  "service_id":      "uuid",
  "window_start":    "ISO-8601 UTC",
  "window_end":      "ISO-8601 UTC",
  "window_size":     "1m | 5m | 1h",
  "request_count":    integer,
  "rpm":              number,
  "response_time_mean": number,
  "response_time_p95":  number,
  "response_time_p99":  number,
  "error_rate":       number,
  "success_rate":     number
}
```

### `alerts` → `AlertPayload`

```json
{
  "alert_id":         "uuid",
  "service_id":       "uuid",
  "triggering_metric": "latency | error_rate | availability",
  "severity":         "low | medium | high | critical",
  "message":          "P99 latency 2.4s exceeds threshold 2.0s",
  "opened_at":        "ISO-8601 UTC",
  "closed_at":        "ISO-8601 UTC | null",
  "priority":         "low | medium | high | critical | null"
}
```

Priority is populated once the alert has been enriched by the ML alert
prioritization module.

### `predictions` → `PredictionPayload`

```json
{
  "service_id":       "uuid",
  "module":           "traffic | failure | anomaly | health | alerts",
  "model_version":    "string",
  "generated_at":     "ISO-8601 UTC",
  "value":             "module-specific JSON",
  "confidence":        number
}
```

The Dashboard Service caches the latest prediction per (service_id, module)
in Redis and falls back to this cache when the ML Service circuit is open.

### `service-health` → `HealthPayload`

```json
{
  "service_id":       "uuid",
  "score":             number,
  "status":           "healthy | warning | degraded | critical",
  "components": {
    "error":   number,
    "latency": number,
    "traffic": number,
    "resource": number
  },
  "generated_at":     "ISO-8601 UTC"
}
```

## Ordering & partition keys

| Topic | Partition key | Reason |
|---|---|---|
| `api-logs` | `service_id` | preserves per-service order at the consumer |
| `metrics` | `service_id` | same |
| `alerts` | `service_id` | same |
| `predictions` | `service_id` | same |
| `service-health` | `service_id` | same |

## Versioning

Breaking payload changes bump `event_version`. Consumers ignore unknown
optional fields and reject unknown required fields to the DLQ.
