package com.innovations.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.OffsetDateTime;
import java.util.UUID;

/** Registry service response shape. Mirrors {@code registry-openapi.yaml}. */
public record ServiceDto(
        UUID id,
        String name,
        @JsonProperty("base_url") String baseUrl,
        String owner,
        String environment,
        String description,
        @JsonProperty("capture_telemetry") boolean captureTelemetry,
        @JsonProperty("created_at") OffsetDateTime createdAt,
        @JsonProperty("updated_at") OffsetDateTime updatedAt
) {
    public record CreateRequest(
            @NotBlank @Size(max = 100) String name,
            @NotBlank @JsonProperty("base_url") String baseUrl,
            @Size(max = 128) String owner,
            @NotBlank @Pattern(regexp = "production|staging|development") String environment,
            @Size(max = 500) String description,
            @JsonProperty("capture_telemetry") Boolean captureTelemetry
    ) {}

    public record UpdateRequest(
            @Size(max = 100) String name,
            @JsonProperty("base_url") String baseUrl,
            @Size(max = 128) String owner,
            @Pattern(regexp = "production|staging|development") String environment,
            @Size(max = 500) String description,
            @JsonProperty("capture_telemetry") Boolean captureTelemetry
    ) {}
}
