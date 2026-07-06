package com.innovations.api.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.UUID;
import javax.crypto.SecretKey;
import org.springframework.stereotype.Component;

/**
 * Issues and parses JWTs. Kept intentionally small — no session state, no
 * refresh-token revocation list yet (deferred). Both Auth Service and any
 * validating service share the same secret via {@link JwtProperties}.
 */
@Component
public class JwtService {

    private final JwtProperties props;
    private final SecretKey key;

    public JwtService(JwtProperties props) {
        this.props = props;
        // HS256 requires ≥ 256-bit key material. Fail fast if the operator
        // wired in a stubby dev secret so we don't sign with a weak key.
        byte[] bytes = props.secret().getBytes(StandardCharsets.UTF_8);
        if (bytes.length < 32) {
            throw new IllegalStateException(
                    "JWT_SECRET must be at least 32 bytes (256 bits) for HS256");
        }
        this.key = Keys.hmacShaKeyFor(bytes);
    }

    public String issueAccessToken(UUID userId, String username, List<String> roles) {
        return build(userId, username, roles, "access",
                Duration.ofSeconds(props.accessTtlSeconds()));
    }

    public String issueRefreshToken(UUID userId, String username) {
        return build(userId, username, List.of(), "refresh",
                Duration.ofSeconds(props.refreshTtlSeconds()));
    }

    public Claims parse(String token) {
        return Jwts.parser()
                .verifyWith(key)
                .requireIssuer(props.issuer())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    private String build(UUID userId, String username, List<String> roles,
                         String tokenType, Duration ttl) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(userId.toString())
                .issuer(props.issuer())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttl)))
                .claim("username", username)
                .claim("roles", roles)
                .claim("typ", tokenType)
                .signWith(key)
                .compact();
    }
}
