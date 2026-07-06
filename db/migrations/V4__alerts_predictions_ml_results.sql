-- V4: alerts, predictions, ml_model_results
-- Completes the 7-table schema described in the paper (Section III-I).

-- ─── alerts ────────────────────────────────────────────────
CREATE TABLE alerts (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id         UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    triggering_metric  VARCHAR(20) NOT NULL
                       CHECK (triggering_metric IN ('latency','error_rate','availability')),
    severity           VARCHAR(10) NOT NULL
                       CHECK (severity IN ('low','medium','high','critical')),
    priority           VARCHAR(10)
                       CHECK (priority IN ('low','medium','high','critical')),
    message            TEXT NOT NULL,
    opened_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at          TIMESTAMPTZ,
    resolved_by        UUID REFERENCES users(id) ON DELETE SET NULL,
    metadata           JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_alerts_service_open
    ON alerts (service_id, opened_at DESC)
    WHERE closed_at IS NULL;

CREATE INDEX idx_alerts_priority_open
    ON alerts (priority, opened_at DESC)
    WHERE closed_at IS NULL;

-- ─── predictions ───────────────────────────────────────────
CREATE TABLE predictions (
    id             BIGSERIAL PRIMARY KEY,
    service_id     UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    module         VARCHAR(16) NOT NULL
                   CHECK (module IN ('traffic','failure','anomaly','health','alerts')),
    model_version  VARCHAR(64) NOT NULL,
    generated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    horizon_minutes INTEGER,           -- populated for traffic / failure
    value          JSONB NOT NULL,     -- module-specific payload
    confidence     NUMERIC(5, 4)
);

CREATE INDEX idx_predictions_service_module_time
    ON predictions (service_id, module, generated_at DESC);

-- ─── ml_model_results ──────────────────────────────────────
-- One row per completed training run. Used by the /admin/models endpoint
-- and by dashboards that surface model quality trends over time.
CREATE TABLE ml_model_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module          VARCHAR(16) NOT NULL
                    CHECK (module IN ('traffic','failure','anomaly','health','alerts')),
    model_version   VARCHAR(64) NOT NULL,
    algorithm       VARCHAR(64) NOT NULL,
    trained_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    training_rows   INTEGER,
    hyperparameters JSONB DEFAULT '{}'::jsonb,
    metrics         JSONB DEFAULT '{}'::jsonb,
    artifact_path   VARCHAR(512),
    is_active       BOOLEAN NOT NULL DEFAULT FALSE
);

-- Exactly one active model per module at a time.
CREATE UNIQUE INDEX idx_ml_model_active_per_module
    ON ml_model_results (module)
    WHERE is_active = TRUE;
