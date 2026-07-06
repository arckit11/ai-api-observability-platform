package com.innovations.api.events;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Payload on the {@code api-logs} Kafka topic. Produced by the Gateway on
 * every forwarded request, consumed by the Metrics Collector which writes
 * to the {@code api_logs} table.
 *
 * <p>{@code dedupKey} is a stable hash of the composite identity of the
 * request. The unique index on {@code api_logs.dedup_key} absorbs the
 * duplicates introduced by Kafka's at-least-once delivery.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ApiLogPayload(
        @JsonProperty("service_id") UUID serviceId,
        @JsonProperty("endpoint") String endpoint,
        @JsonProperty("http_method") String httpMethod,
        @JsonProperty("status_code") int statusCode,
        @JsonProperty("response_time_ms") int responseTimeMs,
        @JsonProperty("user_agent") String userAgent,
        @JsonProperty("client_ip") String clientIp,
        @JsonProperty("user_id") UUID userId,
        @JsonProperty("request_bytes") Integer requestBytes,
        @JsonProperty("response_bytes") Integer responseBytes,
        @JsonProperty("timestamp") OffsetDateTime timestamp,
        @JsonProperty("dedup_key") String dedupKey
) {}
