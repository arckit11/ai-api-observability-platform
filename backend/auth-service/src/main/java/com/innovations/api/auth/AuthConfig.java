package com.innovations.api.auth;

import com.innovations.api.security.JwtProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableConfigurationProperties(JwtProperties.class)
@ComponentScan(basePackages = {
        "com.innovations.api.auth",
        "com.innovations.api.security",
        "com.innovations.api.exceptions"
})
public class AuthConfig {

    @Bean
    public PasswordEncoder passwordEncoder() {
        // BCrypt cost 10 is the Spring default and hashes in ~50ms — fine for
        // a login-flow throughput target where auth is not on the hot path.
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        // Auth Service itself is unauthenticated — the Gateway sits in front
        // and this service issues the tokens that gate access to everything
        // else. Disable CSRF (stateless JSON API), permit all, keep BCrypt
        // for the login endpoint's password check.
        http
                .csrf(csrf -> csrf.disable())
                .authorizeHttpRequests(a -> a.anyRequest().permitAll())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS));
        return http.build();
    }
}
