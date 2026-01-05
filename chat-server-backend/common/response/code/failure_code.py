from common.response.code.base_code import BaseCode

class FailureCode(BaseCode):
    INTERNAL_SERVER_ERROR = ("서버 에러입니다.", 500)
    NOT_FOUND_DATA = ("존재하지 않는 데이터입니다", 404)
    BAD_REQUEST = ("잘못된 요청입니다", 400)

    # 인증 관련 (신원 확인 실패)
    UNAUTHORIZED = ("인증되지 않은 사용자입니다. 로그인 후 이용해주세요.", 401)
    INVALID_TOKEN = ("유효하지 않은 토큰입니다.", 401)
    EXPIRED_TOKEN = ("만료된 토큰입니다.", 401)

    # 인가 관련 (권한 부족)
    FORBIDDEN = ("해당 요청에 대한 권한이 없습니다.", 403)
    ACCESS_DENIED = ("접근이 거부되었습니다.", 403)