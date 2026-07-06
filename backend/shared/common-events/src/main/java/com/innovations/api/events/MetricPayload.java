package com.innovations.api.events;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;

/** Payload on the {@code metrics} topic. Produced by the Analytics Service. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record MetricPayload(
        @JsonProperty("service_id") UUID serviceId,
        @JsonProperty("window_start") OffsetDateTime windowStart,
        @JsonProperty("window_end") OffsetDateTime windowEnd,
        @JsonProperty("window_size") String windowSize,
        @JsonProperty("request_count") int requestCount,
        @JsonProperty("rpm") BigDecimal rpm,
        @JsonProperty("response_time_mean") BigDecimal responseTimeMean,
        @JsonProperty("response_time_p95") BigDecimal responseTimeP95,
        @JsonProperty("response_time_p99") BigDecimal responseTimeP99,
        @JsonProperty("error_rate") BigDecimal errorRate,
        @JsonProperty("success_rate") BigDecimal successRate
) {}
