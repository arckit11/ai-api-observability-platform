package com.innovations.api.dashboard;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

/**
 * Calls the Python ML service. Every method is wrapped in a Resilience4j
 * circuit breaker; the fallback surfaces the last-known cached prediction
 * from Redis, or {@code null} if we've never seen one.
 */
@Component
public class MlClient {

    private final RestTemplate rest;
    private final String baseUrl;
    private final StringRedisTemplate redis;

    public MlClient(@Value("${ml.base-url:http://localhost:8000}") String baseUrl,
                    StringRedisTemplate redis) {
        this.rest = new RestTemplate();
        this.baseUrl = baseUrl;
        this.redis = redis;
    }

    private Map<String, Object> post(String path, Map<String, Object> body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> req = new HttpEntity<>(body, headers);
        return rest.postForObject(baseUrl + path, req, Map.class);
    }

    @CircuitBreaker(name = "ml-service", fallbackMethod = "healthFallback")
    public Map<String, Object> healthScore(UUID serviceId, Map<String, Object> snapshot) {
        Map<String, Object> resp = post("/score/health",
                Map.of("service_id", serviceId.toString(), "snapshot", snapshot));
        cache("health", serviceId, resp);
        return resp;
    }

    @CircuitBreaker(name = "ml-service", fallbackMethod = "trafficFallback")
    public Map<String, Object> traffic(UUID serviceId, int horizon, List<Map<String, Object>> history) {
        Map<String, Object> resp = post("/predict/traffic", Map.of(
                "service_id", serviceId.toString(),
                "horizon_minutes", horizon,
                "history", history));
        cache("traffic", serviceId, resp);
        return resp;
    }

    @CircuitBreaker(name = "ml-service", fallbackMethod = "failureFallback")
    public Map<String, Object> failure(UUID serviceId, List<Map<String, Object>> history) {
        Map<String, Object> resp = post("/predict/failure",
                Map.of("service_id", serviceId.toString(), "history", history));
        cache("failure", serviceId, resp);
        return resp;
    }

    @CircuitBreaker(name = "ml-service", fallbackMethod = "anomalyFallback")
    public Map<String, Object> anomaly(UUID serviceId, Map<String, Object> snapshot) {
        Map<String, Object> resp = post("/predict/anomaly",
                Map.of("service_id", serviceId.toString(), "snapshot", snapshot));
        cache("anomaly", serviceId, resp);
        return resp;
    }

    // ─── Circuit-breaker fallbacks — return last cached value ───────────
    public Map<String, Object> healthFallback(UUID serviceId, Map<String, Object> snapshot, Throwable t) {
        return cached("health", serviceId, t);
    }

    public Map<String, Object> trafficFallback(UUID serviceId, int horizon, List<Map<String, Object>> history, Throwable t) {
        return cached("traffic", serviceId, t);
    }

    public Map<String, Object> failureFallback(UUID serviceId, List<Map<String, Object>> history, Throwable t) {
        return cached("failure", serviceId, t);
    }

    public Map<String, Object> anomalyFallback(UUID serviceId, Map<String, Object> snapshot, Throwable t) {
        return cached("anomaly", serviceId, t);
    }

    private void cache(String module, UUID serviceId, Map<String, Object> resp) {
        try {
            // Store JSON blob keyed by (module, service_id). Short TTL — 5 min —
            // so a very stale fallback doesn't hang around forever.
            String key = "ml:last:" + module + ":" + serviceId;
            String json = new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(resp);
            redis.opsForValue().set(key, json, java.time.Duration.ofMinutes(5));
        } catch (Exception ignored) {
            // Cache write is best-effort; the primary response was fine.
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> cached(String module, UUID serviceId, Throwable t) {
        try {
            String key = "ml:last:" + module + ":" + serviceId;
            String json = redis.opsForValue().get(key);
            if (json == null) return Map.of("stale", true, "reason", "no-cache", "error", t.getMessage());
            Map<String, Object> parsed = new com.fasterxml.jackson.databind.ObjectMapper()
                    .readValue(json, Map.class);
            parsed.put("stale", true);
            return parsed;
        } catch (Exception e) {
            return Map.of("stale", true, "reason", "cache-error", "error", e.getMessage());
        }
    }

    public record ServiceRef(UUID id, String name, @JsonProperty("base_url") String baseUrl) {}
}
