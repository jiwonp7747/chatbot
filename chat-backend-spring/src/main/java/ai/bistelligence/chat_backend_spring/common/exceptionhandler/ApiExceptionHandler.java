package ai.bistelligence.chat_backend_spring.common.exceptionhandler;

import ai.bistelligence.chat_backend_spring.common.api.Api;
import ai.bistelligence.chat_backend_spring.common.exception.ApiException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.annotation.Order;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice
@Order(Integer.MIN_VALUE)
public class ApiExceptionHandler {

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Api<Object>> apiException(ApiException apiException) {
        log.error("[ApiException] {}", apiException.getErrorDescription());

        var errorCode = apiException.getErrorCodeIfs();
        return ResponseEntity
                .status(errorCode.getHttpStatusCode())
                .body(Api.ERROR(errorCode, apiException.getErrorDescription()));
    }
}
