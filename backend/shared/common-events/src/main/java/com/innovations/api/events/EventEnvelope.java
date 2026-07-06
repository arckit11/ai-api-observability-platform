package com.innovations.api.events;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Common Kafka event envelope. Every event on every topic wraps its payload
 * in this record so consumers can rely on a uniform header regardless of
 * which service produced it. Schema documented in
 * {@code docs/api-contracts/kafka-events.md}.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record EventEnvelope<T>(
        @JsonProperty("event_id") UUID eventId,
        @JsonProperty("event_type") String eventType,
        @JsonProperty("event_version") String eventVersion,
        @JsonProperty("occurred_at") OffsetDateTime occurredAt,
        @JsonProperty("producer") String producer,
        @JsonProperty("trace_id") String traceId,
        @JsonProperty("payload") T payload
) {
    public static <T> EventEnvelope<T> of(String type, String producer, T payload) {
        return new EventEnvelope<>(
                UUID.randomUUID(),
                type,
                "1",
                OffsetDateTime.now(),
                producer,
                null,
                payload
        );
    }
}
