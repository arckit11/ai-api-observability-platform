package com.innovations.api.registry;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "services")
public class ServiceEntity {

    @Id
    private UUID id;

    @Column(nullable = false)
    private String name;

    @Column(name = "base_url", nullable = false)
    private String baseUrl;

    private String owner;

    @Column(nullable = false)
    private String environment;

    private String description;

    @Column(name = "capture_telemetry", nullable = false)
    private boolean captureTelemetry;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String n) { this.name = n; }
    public String getBaseUrl() { return baseUrl; }
    public void setBaseUrl(String u) { this.baseUrl = u; }
    public String getOwner() { return owner; }
    public void setOwner(String o) { this.owner = o; }
    public String getEnvironment() { return environment; }
    public void setEnvironment(String e) { this.environment = e; }
    public String getDescription() { return description; }
    public void setDescription(String d) { this.description = d; }
    public boolean isCaptureTelemetry() { return captureTelemetry; }
    public void setCaptureTelemetry(boolean c) { this.captureTelemetry = c; }
    public OffsetDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(OffsetDateTime t) { this.createdAt = t; }
    public OffsetDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(OffsetDateTime t) { this.updatedAt = t; }
}
