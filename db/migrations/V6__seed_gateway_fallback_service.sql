-- V6: seed a fallback "gateway" service row for api-log rows attributed to
-- unmapped paths. Real path→service resolution lands in Phase 2 once the
-- Registry Service is queried live from the Gateway.
INSERT INTO services (id, name, base_url, owner, environment,
                      description, capture_telemetry)
VALUES (
    '00000000-0000-0000-0000-00000000feed',
    'gateway-unresolved',
    'http://gateway.internal',
    'platform',
    'development',
    'Fallback row for api-logs whose path did not map to a registered service.',
    TRUE
)
ON CONFLICT (id) DO NOTHING;
