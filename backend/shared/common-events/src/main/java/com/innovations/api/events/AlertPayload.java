package com.innovations.api.events;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.OffsetDateTime;
import java.util.UUID;

/** Payload on the {@code alerts} topic. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record AlertPayload(
        @JsonProperty("alert_id") UUID alertId,
        @JsonProperty("service_id") UUID serviceId,
        @JsonProperty("triggering_metric") String triggeringMetric,
        @JsonProperty("severity") String severity,
        @JsonProperty("message") String message,
        @JsonProperty("opened_at") OffsetDateTime openedAt,
        @JsonProperty("closed_at") OffsetDateTime closedAt,
        @JsonProperty("priority") String priority
) {}
