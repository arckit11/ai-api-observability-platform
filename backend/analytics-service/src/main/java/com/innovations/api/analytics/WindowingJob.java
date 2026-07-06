package com.innovations.api.analytics;

import com.innovations.api.events.EventEnvelope;
import com.innovations.api.events.MetricPayload;
import com.innovations.api.events.Topics;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Runs every minute: closes the most-recently-completed one-minute window,
 * aggregates api-log rows into it, and fans the results out to the
 * {@code metrics} Kafka topic.
 */
@Component
public class WindowingJob {

    private static final Logger log = LoggerFactory.getLogger(WindowingJob.class);

    private final MetricsRepository repo;
    private final KafkaTemplate<String, Object> kafka;
    private final String metricsTopic;

    public WindowingJob(MetricsRepository repo,
                        KafkaTemplate<String, Object> kafka,
                        @Value("${kafka.topics.metrics:" + Topics.METRICS + "}") String metricsTopic) {
        this.repo = repo;
        this.kafka = kafka;
        this.metricsTopic = metricsTopic;
    }

    /** Aggregate the minute that just closed. */
    @Scheduled(cron = "0 * * * * *")
    public void aggregateMinute() {
        OffsetDateTime end = OffsetDateTime.now(ZoneOffset.UTC).truncatedTo(ChronoUnit.MINUTES);
        OffsetDateTime start = end.minusMinutes(1);
        int rows = repo.aggregateOneMinuteWindow(start, end);
        log.debug("Aggregated {} → {}: {} services", start, end, rows);

        // Fan the new rows out to the metrics topic so the ML service can
        // consume without polling analytics history.
        List<MetricAggregate> latest = repo.latestPerService();
        for (MetricAggregate m : latest) {
            if (!start.isEqual(m.windowStart())) continue;
            MetricPayload payload = new MetricPayload(
                    m.serviceId(), m.windowStart(), m.windowEnd(), m.windowSize(),
                    m.requestCount(), m.rpm(), m.responseTimeMean(),
                    m.responseTimeP95(), m.responseTimeP99(),
                    m.errorRate(), m.successRate()
            );
            EventEnvelope<MetricPayload> env = EventEnvelope.of("metric", "analytics-service", payload);
            kafka.send(metricsTopic, m.serviceId().toString(), env);
        }
    }
}
