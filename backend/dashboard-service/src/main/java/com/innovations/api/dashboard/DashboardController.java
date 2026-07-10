package com.innovations.api.dashboard;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Read-side aggregation for the dashboard UI. Every tile call fans out to
 * Analytics + ML; ML failures are caught by the circuit breaker inside
 * {@link MlClient} and cached fallbacks are returned instead of 5xxs.
 */
@RestController
@RequestMapping("/dashboard")
public class DashboardController {

    private final AnalyticsClient analytics;
    private final MlClient ml;

    public DashboardController(AnalyticsClient analytics, MlClient ml) {
        this.analytics = analytics;
        this.ml = ml;
    }

    /** Health tile — one card per service with metrics + composite health score. */
    @GetMapping("/health")
    public List<Map<String, Object>> health() {
        List<Map<String, Object>> latest = analytics.latest();
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> m : latest) {
            UUID sid = UUID.fromString((String) m.get("service_id"));
            Map<String, Object> snapshot = toSnapshot(m, sid);
            Map<String, Object> score = ml.healthScore(sid, snapshot);
            out.add(Map.of("service_id", sid, "metrics", m, "health", score));
        }
        return out;
    }

    /** Traffic tile — current vs forecast RPM at 15/60 min. */
    @GetMapping("/traffic")
    public List<Map<String, Object>> traffic(@RequestParam(defaultValue = "60") int horizonMinutes) {
        List<Map<String, Object>> latest = analytics.latest();
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> m : latest) {
            UUID sid = UUID.fromString((String) m.get("service_id"));
            List<Map<String, Object>> hist = toSnapshotList(analytics.history(sid, 26), sid);
            Map<String, Object> forecast = hist.size() >= 24
                    ? ml.traffic(sid, horizonMinutes, hist)
                    : Map.of("stale", true, "reason", "insufficient-history");
            out.add(Map.of("service_id", sid, "latest", m, "forecast", forecast));
        }
        return out;
    }

    /** Latency tile — mean / P95 / P99 aggregate per service. */
    @GetMapping("/latency")
    public List<Map<String, Object>> latency() {
        return analytics.latest().stream()
                .map(m -> Map.<String, Object>of(
                        "service_id", m.get("service_id"),
                        "mean", m.get("response_time_mean"),
                        "p95", m.get("response_time_p95"),
                        "p99", m.get("response_time_p99")))
                .toList();
    }

    /** Predictions tile — anomaly + failure + traffic in one page. */
    @GetMapping("/predictions")
    public List<Map<String, Object>> predictions() {
        List<Map<String, Object>> latest = analytics.latest();
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> m : latest) {
            UUID sid = UUID.fromString((String) m.get("service_id"));
            Map<String, Object> snapshot = toSnapshot(m, sid);
            Map<String, Object> anomaly = ml.anomaly(sid, snapshot);
            List<Map<String, Object>> hist = toSnapshotList(analytics.history(sid, 26), sid);
            Map<String, Object> failure = hist.size() >= 30
                    ? ml.failure(sid, hist)
                    : Map.of("stale", true, "reason", "insufficient-history");
            out.add(Map.of("service_id", sid, "anomaly", anomaly, "failure", failure));
        }
        return out;
    }

    /** Open alerts from Analytics, enriched with ML-assigned priority. */
    @GetMapping("/alerts")
    public List<Map<String, Object>> alerts() {
        List<Map<String, Object>> open = analytics.alerts();
        List<Map<String, Object>> out = new ArrayList<>();
        int hour = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC).getHour();
        for (Map<String, Object> a : open) {
            Map<String, Object> ctx = Map.of(
                    "service_id", String.valueOf(a.get("service_id")),
                    "triggering_metric", String.valueOf(a.get("triggering_metric")),
                    "hour_of_day", hour,
                    "alert_frequency_24h", 0,
                    "current_health_score", 60.0,
                    "failure_prediction_active", "critical".equals(a.get("severity")),
                    "service_is_payment_or_auth", false
            );
            Map<String, Object> priority = ml.prioritize(String.valueOf(a.get("id")), ctx);
            java.util.LinkedHashMap<String, Object> row = new java.util.LinkedHashMap<>(a);
            row.put("ml_priority", priority);
            out.add(row);
        }
        return out;
    }

    // ─── Adapters: metric-row → ML MetricSnapshot ──────────────────────
    private static Map<String, Object> toSnapshot(Map<String, Object> row, UUID sid) {
        return Map.of(
                "service_id", sid.toString(),
                "timestamp", row.get("window_start"),
                "request_count", row.getOrDefault("request_count", 0),
                "response_time_mean", row.getOrDefault("response_time_mean", 0),
                "response_time_p95", row.getOrDefault("response_time_p95", 0),
                "response_time_p99", row.getOrDefault("response_time_p99", 0),
                "error_rate", row.getOrDefault("error_rate", 0.0)
        );
    }

    private static List<Map<String, Object>> toSnapshotList(List<Map<String, Object>> rows, UUID sid) {
        return rows.stream().map(r -> toSnapshot(r, sid)).toList();
    }
}
