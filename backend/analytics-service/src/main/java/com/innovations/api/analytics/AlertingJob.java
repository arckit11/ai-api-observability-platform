package com.innovations.api.analytics;

import com.innovations.api.events.AlertPayload;
import com.innovations.api.events.EventEnvelope;
import com.innovations.api.events.Topics;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Cheap alerting rule. After each windowing pass, inspect the latest 1-min
 * metric row per service and open an alert when P99 or error rate crosses
 * a hard threshold. Alerts are also published to the ``alerts`` topic so
 * the Dashboard Service can subscribe and cache them.
 *
 * <p>Open alerts stay open until the next window comes back under
 * threshold, at which point we close them (set ``closed_at``).
 */
@Component
public class AlertingJob {

    private static final Logger log = LoggerFactory.getLogger(AlertingJob.class);
    private static final double P99_THRESHOLD_MS = 2000.0;
    private static final double ERROR_RATE_THRESHOLD = 0.10;

    private final JdbcTemplate jdbc;
    private final KafkaTemplate<String, Object> kafka;
    private final String alertsTopic;

    public AlertingJob(JdbcTemplate jdbc,
                       KafkaTemplate<String, Object> kafka,
                       @Value("${kafka.topics.alerts:" + Topics.ALERTS + "}") String alertsTopic) {
        this.jdbc = jdbc;
        this.kafka = kafka;
        this.alertsTopic = alertsTopic;
    }

    // Runs a couple of seconds after the aggregation cron so the latest
    // metric row is guaranteed to exist.
    @Scheduled(cron = "5 * * * * *")
    public void evaluate() {
        OffsetDateTime end = OffsetDateTime.now(ZoneOffset.UTC).truncatedTo(ChronoUnit.MINUTES);
        OffsetDateTime start = end.minusMinutes(1);

        // Iterate services with a 1-min metric row in this window.
        jdbc.query(
                """
                SELECT service_id,
                       response_time_p99::double precision AS p99,
                       error_rate::double precision AS err
                FROM metrics
                WHERE window_size = '1m' AND window_start = ?::timestamptz
                """,
                (rs, i) -> new Row(
                        UUID.fromString(rs.getString("service_id")),
                        rs.getDouble("p99"),
                        rs.getDouble("err")),
                start
        ).forEach(row -> evaluateService(row, start));

        // Close alerts whose service is now back under threshold.
        int closed = jdbc.update("""
                UPDATE alerts SET closed_at = NOW()
                WHERE closed_at IS NULL
                  AND service_id NOT IN (
                    SELECT service_id
                    FROM metrics
                    WHERE window_size = '1m' AND window_start = ?::timestamptz
                      AND (response_time_p99 > ? OR error_rate > ?)
                  )
                """, start, P99_THRESHOLD_MS, ERROR_RATE_THRESHOLD);
        if (closed > 0) log.info("Closed {} alerts (services recovered)", closed);
    }

    private void evaluateService(Row r, OffsetDateTime windowStart) {
        String trigger = null;
        String severity = null;
        String message = null;

        if (r.p99 > P99_THRESHOLD_MS) {
            trigger = "latency";
            severity = r.p99 > P99_THRESHOLD_MS * 2 ? "critical" : "high";
            message = "P99 latency %.0f ms exceeds threshold %.0f ms"
                    .formatted(r.p99, P99_THRESHOLD_MS);
        } else if (r.err > ERROR_RATE_THRESHOLD) {
            trigger = "error_rate";
            severity = r.err > ERROR_RATE_THRESHOLD * 2 ? "critical" : "high";
            message = "Error rate %.2f%% exceeds threshold %.0f%%"
                    .formatted(r.err * 100, ERROR_RATE_THRESHOLD * 100);
        }
        if (trigger == null) return;

        // Idempotent open: if we already have an open alert for this service
        // with the same trigger, don't spam another.
        Integer existing = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM alerts
                WHERE service_id = ? AND triggering_metric = ? AND closed_at IS NULL
                """,
                Integer.class, r.serviceId, trigger);
        if (existing != null && existing > 0) return;

        UUID alertId = UUID.randomUUID();
        jdbc.update("""
                INSERT INTO alerts (id, service_id, triggering_metric, severity, message, opened_at)
                VALUES (?, ?, ?, ?, ?, NOW())
                """, alertId, r.serviceId, trigger, severity, message);

        AlertPayload payload = new AlertPayload(
                alertId, r.serviceId, trigger, severity, message,
                windowStart, null, null);
        kafka.send(alertsTopic, r.serviceId.toString(),
                EventEnvelope.of("alert", "analytics-service", payload));
        log.info("Opened alert {} on {} (trigger={}, severity={})",
                alertId, r.serviceId, trigger, severity);
    }

    private record Row(UUID serviceId, double p99, double err) {}
}
