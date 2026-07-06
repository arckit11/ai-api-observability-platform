package com.innovations.api.exceptions;

import java.net.URI;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * Advice that converts platform exceptions and validation failures into
 * RFC 7807 problem-detail responses so all services return errors in the
 * same shape.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(PlatformException.class)
    public ProblemDetail onPlatform(PlatformException ex) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(ex.status(), ex.getMessage());
        pd.setTitle(ex.status().getReasonPhrase());
        pd.setType(URI.create("https://iapi.dev/errors/" + ex.code()));
        pd.setProperty("code", ex.code());
        return pd;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ProblemDetail onValidation(MethodArgumentNotValidException ex) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST,
                "Request validation failed");
        pd.setTitle("Bad Request");
        pd.setType(URI.create("https://iapi.dev/errors/validation"));
        pd.setProperty("code", "validation");
        pd.setProperty("errors", ex.getBindingResult().getAllErrors().stream()
                .map(err -> err.getDefaultMessage()).toList());
        return pd;
    }
}
