package com.innovations.api.exceptions;

import org.springframework.http.HttpStatus;

public class UnauthorizedException extends PlatformException {
    public UnauthorizedException(String message) {
        super(HttpStatus.UNAUTHORIZED, "unauthorized", message);
    }
}
