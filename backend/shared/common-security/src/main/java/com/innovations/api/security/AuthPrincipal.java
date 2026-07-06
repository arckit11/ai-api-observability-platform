package com.innovations.api.security;

import java.util.List;
import java.util.UUID;

/** Deserialised JWT claims for the current request. */
public record AuthPrincipal(UUID userId, String username, List<String> roles) {

    public boolean hasRole(Role role) {
        return roles != null && roles.contains(role.name());
    }
}
