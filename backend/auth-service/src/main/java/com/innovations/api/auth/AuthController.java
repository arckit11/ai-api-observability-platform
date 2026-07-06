package com.innovations.api.auth;

import com.innovations.api.dto.LoginRequest;
import com.innovations.api.dto.RefreshRequest;
import com.innovations.api.dto.TokenPair;
import com.innovations.api.exceptions.UnauthorizedException;
import com.innovations.api.security.JwtProperties;
import com.innovations.api.security.JwtService;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/auth")
public class AuthController {

    private final UserRepository users;
    private final PasswordEncoder encoder;
    private final JwtService jwt;
    private final JwtProperties props;

    public AuthController(UserRepository users, PasswordEncoder encoder,
                          JwtService jwt, JwtProperties props) {
        this.users = users;
        this.encoder = encoder;
        this.jwt = jwt;
        this.props = props;
    }

    @PostMapping("/login")
    public TokenPair login(@Valid @RequestBody LoginRequest req) {
        UserEntity user = users.findByUsername(req.username())
                .filter(UserEntity::isActive)
                .orElseThrow(() -> new UnauthorizedException("Invalid credentials"));
        if (!encoder.matches(req.password(), user.getPasswordHash())) {
            throw new UnauthorizedException("Invalid credentials");
        }
        List<String> roles = List.of(user.getRole());
        String access = jwt.issueAccessToken(user.getId(), user.getUsername(), roles);
        String refresh = jwt.issueRefreshToken(user.getId(), user.getUsername());
        return TokenPair.bearer(access, refresh, props.accessTtlSeconds(), roles);
    }

    @PostMapping("/refresh")
    public TokenPair refresh(@Valid @RequestBody RefreshRequest req) {
        Claims claims;
        try {
            claims = jwt.parse(req.refreshToken());
        } catch (JwtException e) {
            throw new UnauthorizedException("Invalid refresh token");
        }
        if (!"refresh".equals(claims.get("typ", String.class))) {
            throw new UnauthorizedException("Not a refresh token");
        }
        UUID userId = UUID.fromString(claims.getSubject());
        UserEntity user = users.findById(userId)
                .filter(UserEntity::isActive)
                .orElseThrow(() -> new UnauthorizedException("User no longer active"));
        List<String> roles = List.of(user.getRole());
        String newAccess = jwt.issueAccessToken(user.getId(), user.getUsername(), roles);
        String newRefresh = jwt.issueRefreshToken(user.getId(), user.getUsername());
        return TokenPair.bearer(newAccess, newRefresh, props.accessTtlSeconds(), roles);
    }
}
