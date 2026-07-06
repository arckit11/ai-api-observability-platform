package com.innovations.api.gateway;

import com.innovations.api.security.JwtService;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * Validates JWTs on every incoming request except unauthenticated paths
 * (login, refresh, actuator health). Propagates {@code X-User-Id} and
 * {@code X-User-Roles} headers to downstream services so they don't have to
 * re-parse the token.
 */
@Component
public class JwtAuthFilter implements GlobalFilter, Ordered {

    private static final Logger log = LoggerFactory.getLogger(JwtAuthFilter.class);
    private static final Set<String> OPEN_PREFIXES = Set.of(
            "/auth/login", "/auth/refresh", "/actuator", "/metrics-preview"
    );

    private final JwtService jwt;

    public JwtAuthFilter(JwtService jwt) {
        this.jwt = jwt;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String path = exchange.getRequest().getPath().value();
        if (OPEN_PREFIXES.stream().anyMatch(path::startsWith)) {
            return chain.filter(exchange);
        }

        String authHeader = exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            return unauthorized(exchange, "Missing bearer token");
        }
        String token = authHeader.substring("Bearer ".length()).trim();
        Claims claims;
        try {
            claims = jwt.parse(token);
        } catch (JwtException e) {
            log.debug("JWT parse failed: {}", e.getMessage());
            return unauthorized(exchange, "Invalid token");
        }
        String typ = claims.get("typ", String.class);
        if (typ != null && !"access".equals(typ)) {
            return unauthorized(exchange, "Not an access token");
        }

        ServerHttpRequest mutated = exchange.getRequest().mutate()
                .header("X-User-Id", claims.getSubject())
                .header("X-User-Roles", String.valueOf(claims.get("roles")))
                .build();
        return chain.filter(exchange.mutate().request(mutated).build());
    }

    private Mono<Void> unauthorized(ServerWebExchange exchange, String reason) {
        exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
        exchange.getResponse().getHeaders().add("WWW-Authenticate", "Bearer");
        log.debug("401 {} — {}", exchange.getRequest().getPath(), reason);
        return exchange.getResponse().setComplete();
    }

    @Override
    public int getOrder() {
        // Run before route-forwarding so downstream services see the mutated
        // headers.
        return -100;
    }
}
