package com.innovations.api.exceptions;

import org.springframework.http.HttpStatus;

public class NotFoundException extends PlatformException {
    public NotFoundException(String message) {
        super(HttpStatus.NOT_FOUND, "not-found", message);
    }
}
