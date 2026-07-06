package com.innovations.api.exceptions;

import org.springframework.http.HttpStatus;

/**
 * Base class for domain exceptions the platform's REST layer converts into
 * RFC 7807 problem-detail responses via {@link GlobalExceptionHandler}.
 */
public class PlatformException extends RuntimeException {

    private final HttpStatus status;
    private final String code;

    public PlatformException(HttpStatus status, String code, String message) {
        super(message);
        this.status = status;
        this.code = code;
    }

    public HttpStatus status() {
        return status;
    }

    public String code() {
        return code;
    }
}
