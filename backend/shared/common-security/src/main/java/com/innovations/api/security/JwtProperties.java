package com.innovations.api.security;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Bound from {@code jwt.*} properties. Both Auth Service (which issues) and
 * the Gateway (which validates) read from the same shape so a secret rotation
 * only requires editing {@code JWT_SECRET} in the shared env file.
 */
@ConfigurationProperties(prefix = "jwt")
public record JwtProperties(
        String secret,
        String issuer,
        long accessTtlSeconds,
        long refreshTtlSeconds
) {}
