package ai.bistelligence.chat_backend_spring.common.error;

import lombok.AllArgsConstructor;
import lombok.Getter;

@AllArgsConstructor
@Getter
public enum TokenErrorCode implements ErrorCodeIfs {

    INVALID_TOKEN(401, 2000, "유효하지 않은 토큰"),
    EXPIRED_TOKEN(401, 2001, "만료된 토큰"),
    TOKEN_NOT_FOUND(401, 2002, "토큰을 찾을 수 없습니다"),
    ;

    private final Integer httpStatusCode;
    private final Integer errorCode;
    private final String description;
}
