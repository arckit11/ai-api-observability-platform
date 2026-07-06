package com.innovations.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record TokenPair(
        @JsonProperty("access_token") String accessToken,
        @JsonProperty("refresh_token") String refreshToken,
        @JsonProperty("token_type") String tokenType,
        @JsonProperty("expires_in") long expiresIn,
        List<String> roles
) {
    public static TokenPair bearer(String access, String refresh, long expiresInSeconds, List<String> roles) {
        return new TokenPair(access, refresh, "Bearer", expiresInSeconds, roles);
    }
}
