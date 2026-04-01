package ai.bistelligence.chat_backend_spring.common.error;

import lombok.AllArgsConstructor;
import lombok.Getter;

@AllArgsConstructor
@Getter
public enum ErrorCode implements ErrorCodeIfs {

    OK(200, 200, "성공"),
    BAD_REQUEST(400, 400, "잘못된 요청"),
    UNAUTHORIZED(401, 401, "인증이 필요합니다"),
    FORBIDDEN(403, 403, "권한이 없습니다"),
    NOT_FOUND(404, 404, "요청한 리소스를 찾을 수 없습니다"),
    SERVER_ERROR(500, 500, "서버 에러"),
    NULL_POINT(500, 512, "Null Point"),
    ;

    private final Integer httpStatusCode;
    private final Integer errorCode;
    private final String description;
}
