-- V1: users & services (registry)
-- Both tables are foundational — everything else FKs into services.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── users ─────────────────────────────────────────────────
CREATE TABLE users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username       VARCHAR(64)  NOT NULL UNIQUE,
    email          VARCHAR(255) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(16)  NOT NULL DEFAULT 'VIEWER'
                   CHECK (role IN ('ADMIN', 'DEVELOPER', 'VIEWER')),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_role ON users(role) WHERE is_active = TRUE;

-- ─── services (API Registry) ───────────────────────────────
CREATE TABLE services (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              VARCHAR(100) NOT NULL,
    base_url          VARCHAR(512) NOT NULL,
    owner             VARCHAR(128),
    environment       VARCHAR(16)  NOT NULL
                      CHECK (environment IN ('production', 'staging', 'development')),
    description       VARCHAR(500),
    capture_telemetry BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by        UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (name, environment)
);

CREATE INDEX idx_services_environment ON services(environment);
CREATE INDEX idx_services_capture ON services(capture_telemetry) WHERE capture_telemetry = TRUE;

-- Helper: keep updated_at fresh on row updates. Applied to all tables that
-- carry the column.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_services_updated_at
    BEFORE UPDATE ON services
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
