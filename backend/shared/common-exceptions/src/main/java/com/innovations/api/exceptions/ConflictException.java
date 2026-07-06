package com.innovations.api.exceptions;

import org.springframework.http.HttpStatus;

public class ConflictException extends PlatformException {
    public ConflictException(String message) {
        super(HttpStatus.CONFLICT, "conflict", message);
    }
}
