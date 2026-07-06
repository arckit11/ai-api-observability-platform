package com.innovations.api.dashboard;

import java.time.OffsetDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * Thin client for the Analytics Service REST surface. Deliberately no
 * circuit breaker here — Analytics is co-located and reliable; the
 * expensive fallback machinery is reserved for the ML service.
 */
@Component
public class AnalyticsClient {

    private final RestClient client;

    public AnalyticsClient(@Value("${analytics.base-url:http://localhost:8084}") String baseUrl) {
        this.client = RestClient.builder().baseUrl(baseUrl).build();
    }

    public List<Map<String, Object>> latest() {
        return client.get()
                .uri("/analytics/metrics/latest")
                .retrieve()
                .body(new ParameterizedTypeReference<List<Map<String, Object>>>() {});
    }

    public List<Map<String, Object>> history(UUID serviceId, int hoursBack) {
        OffsetDateTime to = OffsetDateTime.now(java.time.ZoneOffset.UTC).truncatedTo(ChronoUnit.MINUTES);
        OffsetDateTime from = to.minusHours(hoursBack);
        return client.get()
                .uri(uri -> uri
                        .path("/analytics/metrics/history")
                        .queryParam("service_id", serviceId)
                        .queryParam("from", from.format(java.time.format.DateTimeFormatter.ISO_OFFSET_DATE_TIME))
                        .queryParam("to", to.format(java.time.format.DateTimeFormatter.ISO_OFFSET_DATE_TIME))
                        .queryParam("window", "1m")
                        .build())
                .retrieve()
                .body(new ParameterizedTypeReference<List<Map<String, Object>>>() {});
    }
}
