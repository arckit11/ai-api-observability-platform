package com.innovations.api.collector;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.innovations.api.events.ApiLogPayload;
import com.innovations.api.events.EventEnvelope;
import com.innovations.api.events.Topics;
import com.innovations.api.util.DedupKeys;
import java.time.OffsetDateTime;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

/**
 * Consumes api-log events, validates them, and persists to Postgres. Kafka
 * guarantees at-least-once so we rely on the {@code dedup_key} unique index
 * to make writes idempotent. Malformed payloads route to a dead-letter topic
 * so a single bad message never blocks the consumer group.
 */
@Component
public class ApiLogConsumer {

    private static final Logger log = LoggerFactory.getLogger(ApiLogConsumer.class);

    private final ApiLogRepository repo;
    private final ObjectMapper mapper;
    private final KafkaTemplate<String, Object> kafka;
    private final String dlqTopic;

    public ApiLogConsumer(ApiLogRepository repo,
                          ObjectMapper mapper,
                          KafkaTemplate<String, Object> kafka,
                          @Value("${kafka.topics.api-logs-dlq:" + Topics.API_LOGS_DLQ + "}") String dlqTopic) {
        this.repo = repo;
        this.mapper = mapper;
        this.kafka = kafka;
        this.dlqTopic = dlqTopic;
    }

    @KafkaListener(topics = "${kafka.topics.api-logs:" + Topics.API_LOGS + "}",
            containerFactory = "kafkaListenerContainerFactory")
    public void consume(ConsumerRecord<String, byte[]> record, Acknowledgment ack) {
        try {
            EventEnvelope<ApiLogPayload> env = mapper.readValue(
                    record.value(),
                    new TypeReference<EventEnvelope<ApiLogPayload>>() {}
            );
            ApiLogPayload p = env.payload();
            if (p == null || p.serviceId() == null || p.endpoint() == null ||
                    p.timestamp() == null || p.httpMethod() == null) {
                throw new IllegalArgumentException("payload missing required fields");
            }

            String dedup = p.dedupKey() != null && !p.dedupKey().isBlank()
                    ? p.dedupKey()
                    : DedupKeys.forApiLog(p.serviceId(), p.endpoint(),
                            p.timestamp(), p.statusCode(), p.userId());

            if (repo.existsByDedupKey(dedup)) {
                ack.acknowledge();
                return;
            }

            ApiLogEntity e = new ApiLogEntity();
            e.setServiceId(p.serviceId());
            e.setEndpoint(p.endpoint());
            e.setHttpMethod(p.httpMethod());
            e.setStatusCode((short) p.statusCode());
            e.setResponseTimeMs(p.responseTimeMs());
            e.setUserAgent(p.userAgent());
            e.setClientIp(p.clientIp());
            e.setUserId(p.userId());
            e.setRequestBytes(p.requestBytes());
            e.setResponseBytes(p.responseBytes());
            e.setRequestTimestamp(p.timestamp());
            e.setDedupKey(dedup);
            try {
                repo.save(e);
            } catch (DataIntegrityViolationException dup) {
                // Concurrent duplicate — another consumer beat us to it.
                log.debug("Duplicate dedup_key {} ignored", dedup);
            }
            ack.acknowledge();
        } catch (Exception ex) {
            log.warn("Routing to DLQ (partition={} offset={}): {}",
                    record.partition(), record.offset(), ex.getMessage());
            try {
                kafka.send(dlqTopic, record.key(),
                        new DlqEnvelope(new String(record.value()), ex.getMessage(),
                                OffsetDateTime.now()));
            } catch (Exception dlqEx) {
                log.error("Failed to publish to DLQ", dlqEx);
            }
            ack.acknowledge();
        }
    }

    /** Minimal DLQ payload — original message + error reason + when. */
    public record DlqEnvelope(String original, String error, OffsetDateTime routedAt) {}
}
