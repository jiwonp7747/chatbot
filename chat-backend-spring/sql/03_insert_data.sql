-- ============================================
-- 초기 데이터 삽입 (chat_app 스키마)
-- chat_app 계정으로 접속하여 실행
-- ============================================

-- 사용자 (id: bistelligence, password: admin)
INSERT INTO "user" (user_id, password, name, status, created_at, updated_at)
VALUES ('bistelligence', '$2b$10$5kfwU/1sTj7qHdbl5U8YT.pa8jU4t.oJjxP.5tRhY2.NJd5Bx29Im', 'Admin', 'ACTIVE', SYSTIMESTAMP, SYSTIMESTAMP);

-- 모델
INSERT INTO model_type (name, model_type, provider, api_model, is_active, summary)
VALUES ('GPT-4.1 Mini', 'CHAT', 'OPENAI', 'gpt-4.1-mini', 1, 'OpenAI GPT-4.1 Mini');

INSERT INTO model_type (name, model_type, provider, api_model, is_active, summary)
VALUES ('GPT-4.1', 'CHAT', 'OPENAI', 'gpt-4.1', 1, 'OpenAI GPT-4.1');

COMMIT;
