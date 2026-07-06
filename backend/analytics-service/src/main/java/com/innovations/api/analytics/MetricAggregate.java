package com.innovations.api.analytics;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;

/** Wire shape for /analytics/metrics/* responses. Matches OpenAPI. */
public record MetricAggregate(
        @JsonProperty("service_id") UUID serviceId,
        @JsonProperty("window_start") OffsetDateTime windowStart,
        @JsonProperty("window_end") OffsetDateTime windowEnd,
        @JsonProperty("window_size") String windowSize,
        @JsonProperty("request_count") int requestCount,
        BigDecimal rpm,
        @JsonProperty("response_time_mean") BigDecimal responseTimeMean,
        @JsonProperty("response_time_p95") BigDecimal responseTimeP95,
        @JsonProperty("response_time_p99") BigDecimal responseTimeP99,
        @JsonProperty("error_rate") BigDecimal errorRate,
        @JsonProperty("success_rate") BigDecimal successRate
) {}
