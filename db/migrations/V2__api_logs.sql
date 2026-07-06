-- V2: api_logs — raw request telemetry from the Gateway.
-- dedup_key + unique index absorb Kafka at-least-once duplicates.

CREATE TABLE api_logs (
    id                BIGSERIAL PRIMARY KEY,
    service_id        UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    endpoint          VARCHAR(512) NOT NULL,
    http_method       VARCHAR(10)  NOT NULL
                      CHECK (http_method IN ('GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS')),
    status_code       SMALLINT     NOT NULL,
    response_time_ms  INTEGER      NOT NULL CHECK (response_time_ms >= 0),
    user_agent        VARCHAR(512),
    client_ip         INET,
    user_id           UUID,
    request_bytes     INTEGER,
    response_bytes    INTEGER,
    request_timestamp TIMESTAMPTZ  NOT NULL,
    ingested_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    dedup_key         CHAR(64)     NOT NULL,   -- sha256 hex
    UNIQUE (dedup_key)
);

-- Query patterns:
--   1. Analytics computes windows: WHERE service_id = ? AND request_timestamp BETWEEN ? AND ?
--   2. Dashboards read recent logs per service.
CREATE INDEX idx_api_logs_service_time
    ON api_logs (service_id, request_timestamp DESC);

CREATE INDEX idx_api_logs_status
    ON api_logs (service_id, status_code, request_timestamp DESC);
