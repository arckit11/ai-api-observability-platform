-- V3: metrics — computed aggregates (RPM, latency, error rate) per window.
-- Partitioned by window_start (monthly) to keep range queries efficient at
-- 1-minute windows over long histories.

CREATE TABLE metrics (
    id                  BIGSERIAL,
    service_id          UUID        NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    window_start        TIMESTAMPTZ NOT NULL,
    window_end          TIMESTAMPTZ NOT NULL,
    window_size         VARCHAR(4)  NOT NULL CHECK (window_size IN ('1m','5m','1h')),
    request_count       INTEGER     NOT NULL DEFAULT 0,
    rpm                 NUMERIC(10, 2),
    response_time_mean  NUMERIC(10, 2),
    response_time_p95   NUMERIC(10, 2),
    response_time_p99   NUMERIC(10, 2),
    error_rate          NUMERIC(5, 4) CHECK (error_rate BETWEEN 0 AND 1),
    success_rate        NUMERIC(5, 4) CHECK (success_rate BETWEEN 0 AND 1),
    cpu_usage_pct       NUMERIC(5, 2),
    memory_usage_pct    NUMERIC(5, 2),
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, window_start),
    UNIQUE (service_id, window_size, window_start)
) PARTITION BY RANGE (window_start);

CREATE INDEX idx_metrics_service_window
    ON metrics (service_id, window_size, window_start DESC);

-- ─── Initial monthly partitions ──────────────────────────────
-- 3 months of forward partitions bootstrap the platform; a scheduled job
-- (documented in ops/) creates future partitions rolling forward.

CREATE TABLE metrics_2026_01 PARTITION OF metrics
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE metrics_2026_02 PARTITION OF metrics
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE TABLE metrics_2026_03 PARTITION OF metrics
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- Default partition catches any row outside the above ranges so writes never
-- fail — the ops job migrates data out of the default as new partitions
-- come online.
CREATE TABLE metrics_default PARTITION OF metrics DEFAULT;
