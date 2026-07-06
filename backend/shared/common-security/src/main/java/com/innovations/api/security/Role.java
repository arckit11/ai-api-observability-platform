package com.innovations.api.security;

/**
 * Platform-wide RBAC roles. Gateway enforces per-route requirements from these
 * three values; adding a role means updating both the DB check constraint on
 * {@code users.role} and the gateway route configuration.
 */
public enum Role {
    ADMIN,
    DEVELOPER,
    VIEWER
}
