package com.innovations.api.collector;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.ColumnTransformer;

@Entity
@Table(name = "api_logs")
public class ApiLogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "service_id", nullable = false)
    private UUID serviceId;

    @Column(nullable = false)
    private String endpoint;

    @Column(name = "http_method", nullable = false, length = 10)
    private String httpMethod;

    @Column(name = "status_code", nullable = false)
    private short statusCode;

    @Column(name = "response_time_ms", nullable = false)
    private int responseTimeMs;

    @Column(name = "user_agent")
    private String userAgent;

    // Postgres `inet` needs an explicit cast in the write path; JPA otherwise
    // sends a varchar and the server rejects with 42804.
    @Column(name = "client_ip", columnDefinition = "inet")
    @ColumnTransformer(write = "?::inet")
    private String clientIp;

    @Column(name = "user_id")
    private UUID userId;

    @Column(name = "request_bytes")
    private Integer requestBytes;

    @Column(name = "response_bytes")
    private Integer responseBytes;

    @Column(name = "request_timestamp", nullable = false)
    private OffsetDateTime requestTimestamp;

    @Column(name = "ingested_at", nullable = false, insertable = false, updatable = false)
    private OffsetDateTime ingestedAt;

    @Column(name = "dedup_key", nullable = false, length = 64, unique = true)
    private String dedupKey;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public UUID getServiceId() { return serviceId; }
    public void setServiceId(UUID s) { this.serviceId = s; }
    public String getEndpoint() { return endpoint; }
    public void setEndpoint(String e) { this.endpoint = e; }
    public String getHttpMethod() { return httpMethod; }
    public void setHttpMethod(String m) { this.httpMethod = m; }
    public short getStatusCode() { return statusCode; }
    public void setStatusCode(short s) { this.statusCode = s; }
    public int getResponseTimeMs() { return responseTimeMs; }
    public void setResponseTimeMs(int r) { this.responseTimeMs = r; }
    public String getUserAgent() { return userAgent; }
    public void setUserAgent(String u) { this.userAgent = u; }
    public String getClientIp() { return clientIp; }
    public void setClientIp(String c) { this.clientIp = c; }
    public UUID getUserId() { return userId; }
    public void setUserId(UUID u) { this.userId = u; }
    public Integer getRequestBytes() { return requestBytes; }
    public void setRequestBytes(Integer b) { this.requestBytes = b; }
    public Integer getResponseBytes() { return responseBytes; }
    public void setResponseBytes(Integer b) { this.responseBytes = b; }
    public OffsetDateTime getRequestTimestamp() { return requestTimestamp; }
    public void setRequestTimestamp(OffsetDateTime t) { this.requestTimestamp = t; }
    public String getDedupKey() { return dedupKey; }
    public void setDedupKey(String d) { this.dedupKey = d; }
}
