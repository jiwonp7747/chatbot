package ai.bistelligence.chat_backend_spring.domain.user.error;

import ai.bistelligence.chat_backend_spring.common.error.ErrorCodeIfs;
import lombok.AllArgsConstructor;
import lombok.Getter;

@AllArgsConstructor
@Getter
public enum UserErrorCode implements ErrorCodeIfs {

    USER_NOT_FOUND(404, 1404, "사용자를 찾을 수 없습니다"),
    DUPLICATE_USER_ID(409, 1409, "이미 등록된 아이디입니다"),
    INVALID_PASSWORD(401, 1401, "비밀번호가 일치하지 않습니다"),
    INACTIVE_USER(403, 1403, "비활성화된 사용자입니다"),
    ;

    private final Integer httpStatusCode;
    private final Integer errorCode;
    private final String description;
}
