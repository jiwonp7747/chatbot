-- ============================================
-- 테이블 생성 (chat_app 스키마)
-- chat_app 계정으로 접속하여 실행
-- ============================================

-- 1. 사용자 테이블
CREATE TABLE "user" (
    user_id       VARCHAR2(50)   PRIMARY KEY,
    password      VARCHAR2(255)  NOT NULL,
    name          VARCHAR2(100)  NOT NULL,
    status        VARCHAR2(20)   DEFAULT 'ACTIVE' NOT NULL,
    created_at    TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at    TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL
);

COMMENT ON TABLE "user" IS '사용자 정보';
COMMENT ON COLUMN "user".user_id IS '사용자 ID (로그인 ID)';
COMMENT ON COLUMN "user".password IS '비밀번호 (BCrypt)';
COMMENT ON COLUMN "user".name IS '사용자 이름';
COMMENT ON COLUMN "user".status IS '상태 (ACTIVE, INACTIVE, DELETED)';
COMMENT ON COLUMN "user".created_at IS '생성일시';
COMMENT ON COLUMN "user".updated_at IS '수정일시';

-- 2. 채팅 세션 테이블
CREATE TABLE chat_session (
    thread_id     VARCHAR2(36)   DEFAULT SYS_GUID() PRIMARY KEY,
    user_id       VARCHAR2(50)   NOT NULL,
    title         VARCHAR2(500)  DEFAULT '새 대화',
    created_at    TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at    TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES "user"(user_id)
);

CREATE INDEX idx_session_user ON chat_session(user_id);

COMMENT ON TABLE chat_session IS '채팅 세션';
COMMENT ON COLUMN chat_session.thread_id IS '세션 고유 ID (UUID)';
COMMENT ON COLUMN chat_session.user_id IS '소유 사용자 ID';
COMMENT ON COLUMN chat_session.title IS '세션 제목';

-- 3. 모델 타입 테이블
CREATE TABLE model_type (
    model_id      NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          VARCHAR2(100)  NOT NULL,
    model_type    VARCHAR2(50)   NOT NULL,
    provider      VARCHAR2(50)   NOT NULL,
    api_model     VARCHAR2(200)  NOT NULL,
    is_active     NUMBER(1)      DEFAULT 1 NOT NULL,
    summary       VARCHAR2(500),
    created_at    TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL
);

COMMENT ON TABLE model_type IS 'LLM 모델 설정';

-- 4. 프롬프트 템플릿 테이블
CREATE TABLE prompt_template (
    prompt_id     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          VARCHAR2(100)  NOT NULL,
    prompt_type   VARCHAR2(50)   NOT NULL,
    priority      NUMBER         DEFAULT 0 NOT NULL,
    is_active     NUMBER(1)      DEFAULT 1 NOT NULL,
    content       CLOB           NOT NULL,
    created_at    TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at    TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL
);

COMMENT ON TABLE prompt_template IS '시스템 프롬프트 템플릿';
