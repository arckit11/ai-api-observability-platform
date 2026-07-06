package com.innovations.api.events;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

/** Payload on the {@code predictions} topic — produced by the ML Service. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record PredictionPayload(
        @JsonProperty("service_id") UUID serviceId,
        @JsonProperty("module") String module,
        @JsonProperty("model_version") String modelVersion,
        @JsonProperty("generated_at") OffsetDateTime generatedAt,
        @JsonProperty("value") Map<String, Object> value,
        @JsonProperty("confidence") Double confidence
) {}
