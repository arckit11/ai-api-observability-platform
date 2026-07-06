package com.innovations.api.events;

/**
 * Canonical Kafka topic names. Services must reference these constants
 * rather than string-literal topic names so a rename lands atomically.
 */
public final class Topics {
    public static final String API_LOGS = "api-logs";
    public static final String API_LOGS_DLQ = "api-logs-dlq";
    public static final String METRICS = "metrics";
    public static final String ALERTS = "alerts";
    public static final String PREDICTIONS = "predictions";
    public static final String SERVICE_HEALTH = "service-health";

    private Topics() {}
}
