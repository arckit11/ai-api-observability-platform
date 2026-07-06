package com.innovations.api.gateway;

import com.innovations.api.events.ApiLogPayload;
import com.innovations.api.events.EventEnvelope;
import com.innovations.api.events.Topics;
import com.innovations.api.util.DedupKeys;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.HttpHeaders;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * Records every forwarded request as an {@code api-logs} event. Runs after
 * {@link JwtAuthFilter} so it can attribute traffic to a user, but the
 * capture itself is best-effort — a Kafka publish failure never blocks the
 * response.
 *
 * <p>Service resolution uses the first path segment (e.g. {@code /orders/42}
 * → {@code orders}) mapped to a placeholder UUID. Once the Registry Service
 * ships with a cached lookup, wire that in here.
 */
@Component
public class TelemetryFilter implements GlobalFilter, Ordered {

    private static final Logger log = LoggerFactory.getLogger(TelemetryFilter.class);

    private final KafkaTemplate<String, Object> kafka;
    private final String topic;
    private final UUID fallbackServiceId;
    private final String producerName;

    public TelemetryFilter(KafkaTemplate<String, Object> kafka,
                           @Value("${kafka.topics.api-logs:" + Topics.API_LOGS + "}") String topic,
                           @Value("${gateway.fallback-service-id:00000000-0000-0000-0000-00000000feed}") String fallbackId) {
        this.kafka = kafka;
        this.topic = topic;
        this.fallbackServiceId = UUID.fromString(fallbackId);
        this.producerName = "gateway-service";
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        long start = System.nanoTime();
        return chain.filter(exchange).doFinally(sig -> capture(exchange, start));
    }

    private void capture(ServerWebExchange exchange, long startNanos) {
        try {
            long elapsedMs = Duration.ofNanos(System.nanoTime() - startNanos).toMillis();
            OffsetDateTime ts = OffsetDateTime.now();
            String path = exchange.getRequest().getPath().value();
            String method = exchange.getRequest().getMethod().name();
            int status = exchange.getResponse().getStatusCode() != null
                    ? exchange.getResponse().getStatusCode().value()
                    : 0;

            String userIdHeader = exchange.getRequest().getHeaders().getFirst("X-User-Id");
            UUID userId = userIdHeader != null ? safeUuid(userIdHeader) : null;
            UUID serviceId = fallbackServiceId; // TODO: resolve via Registry Service (Phase 2)

            String dedup = DedupKeys.forApiLog(serviceId, path, ts, status, userId);
            ApiLogPayload payload = new ApiLogPayload(
                    serviceId, path, method, status, (int) elapsedMs,
                    exchange.getRequest().getHeaders().getFirst(HttpHeaders.USER_AGENT),
                    exchange.getRequest().getRemoteAddress() != null
                            ? exchange.getRequest().getRemoteAddress().getHostString() : null,
                    userId, null, null, ts, dedup
            );
            EventEnvelope<ApiLogPayload> env = EventEnvelope.of("api-log", producerName, payload);
            kafka.send(topic, serviceId.toString(), env);
        } catch (Exception e) {
            log.warn("Telemetry publish failed", e);
        }
    }

    private static UUID safeUuid(String v) {
        try { return UUID.fromString(v); } catch (IllegalArgumentException e) { return null; }
    }

    @Override
    public int getOrder() {
        return 0; // after auth
    }
}
