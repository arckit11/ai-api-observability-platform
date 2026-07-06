package com.innovations.api.util;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.HexFormat;
import java.util.UUID;

/**
 * Stable dedup-key generation for api-log rows. The composite identity is
 * (service_id, endpoint, timestamp truncated to seconds, status_code,
 * user_id). Truncating to seconds is deliberate — Gateway and consumer
 * clocks differ by a few milliseconds under duplicate delivery, and
 * per-second granularity is well below the per-minute aggregation window
 * used by Analytics, so no information is lost.
 */
public final class DedupKeys {

    private DedupKeys() {}

    public static String forApiLog(UUID serviceId,
                                   String endpoint,
                                   OffsetDateTime timestamp,
                                   int statusCode,
                                   UUID userId) {
        String canonical = String.join("|",
                String.valueOf(serviceId),
                endpoint == null ? "" : endpoint,
                timestamp
                        .withOffsetSameInstant(ZoneOffset.UTC)
                        .truncatedTo(ChronoUnit.SECONDS)
                        .toString(),
                String.valueOf(statusCode),
                userId == null ? "" : userId.toString()
        );
        return sha256Hex(canonical);
    }

    private static String sha256Hex(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(input.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            // SHA-256 is guaranteed by the JDK spec — treat as fatal.
            throw new IllegalStateException("SHA-256 not available in JRE", e);
        }
    }
}
