package ai.bistelligence.chat_backend_spring.common.exception;

import ai.bistelligence.chat_backend_spring.common.error.ErrorCodeIfs;

public interface ApiExceptionIfs {
    ErrorCodeIfs getErrorCodeIfs();
    String getErrorDescription();
}
