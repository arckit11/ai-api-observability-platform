package com.innovations.api.analytics;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/analytics")
public class AnalyticsController {

    private final MetricsRepository repo;

    public AnalyticsController(MetricsRepository repo) {
        this.repo = repo;
    }

    /**
     * Latest metric row per service. Cached in Redis for 30s so a fanout of
     * dashboard refreshes doesn't hammer Postgres. Cache key ignores the
     * optional service_id filter — the whole set fits in a small blob.
     */
    @GetMapping("/metrics/latest")
    @Cacheable(cacheNames = "metrics-latest", unless = "#result == null")
    public List<MetricAggregate> latest(@RequestParam(required = false) UUID serviceId) {
        List<MetricAggregate> rows = repo.latestPerService();
        return serviceId == null
                ? rows
                : rows.stream().filter(m -> m.serviceId().equals(serviceId)).toList();
    }

    @GetMapping("/metrics/history")
    public List<MetricAggregate> history(
            @RequestParam("service_id") UUID serviceId,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime from,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime to,
            @RequestParam(defaultValue = "1m") String window) {
        return repo.history(serviceId, from, to, window);
    }

    /** Open alerts (closed_at IS NULL) newest-first. */
    @GetMapping("/alerts")
    public List<java.util.Map<String, Object>> alerts(
            @RequestParam(defaultValue = "50") int limit) {
        return repo.openAlerts(Math.min(200, Math.max(1, limit)));
    }
}
