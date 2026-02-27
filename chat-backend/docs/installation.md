# 설치 가이드

AI Chatbot Platform의 상세 설치 및 환경 설정 방법을 안내합니다.

---

## 목차

- [사전 요구사항](#사전-요구사항)
- [1. 데이터베이스 설정](#1-데이터베이스-설정)
- [2. 백엔드 설정](#2-백엔드-설정)
- [3. 프론트엔드 설정](#3-프론트엔드-설정)
- [4. MCP 서버 설정 (선택)](#4-mcp-서버-설정-선택)
- [5. OpenTelemetry 설정 (선택)](#5-opentelemetry-설정-선택)
- [문제 해결](#문제-해결)

---

## 사전 요구사항

| 소프트웨어 | 최소 버전 | 용도 |
|-----------|---------|------|
| Python | 3.11+ | 백엔드 런타임 |
| Node.js | 18+ | 프론트엔드 빌드 |
| PostgreSQL | 15+ (권장 17) | 데이터베이스 |
| Docker (선택) | 20+ | PostgreSQL 컨테이너 |

### LLM API 키

사용할 LLM 프로바이더에 따라 하나 이상의 API 키가 필요합니다:

| 프로바이더 | 환경변수 | 발급처 |
|-----------|---------|--------|
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| Google Gemini | `GOOGLE_API_KEY` | https://aistudio.google.com/apikey |
| OCI | `OCI_API_KEY` 등 | Oracle Cloud Console |

---

## 1. 데이터베이스 설정

### 방법 A: Docker Compose (권장)

프로젝트에 포함된 `docker-compose.yml`을 사용하면 가장 간편합니다.

```bash
cd chat-backend

# PostgreSQL 컨테이너 시작 (백그라운드)
docker compose up -d
```

기본 설정:
- **포트**: `5433` (호스트) -> `5432` (컨테이너)
- **사용자**: `postgres`
- **비밀번호**: `postgres` (환경변수 `POSTGRES_PASSWORD`로 변경 가능)
- **데이터베이스**: `postgres`
- **데이터 영속화**: Docker 볼륨 `chat-db-data`

컨테이너 상태 확인:

```bash
docker compose ps
docker compose logs chat-db
```

### 방법 B: 직접 설치

PostgreSQL을 직접 설치한 경우:

```bash
# macOS (Homebrew)
brew install postgresql@17
brew services start postgresql@17

# Ubuntu/Debian
sudo apt install postgresql-17
sudo systemctl start postgresql

# 데이터베이스 생성 (필요시)
createdb chatbot
```

---

## 2. 백엔드 설정

### 2.1 가상환경 생성

```bash
cd chat-backend

# 가상환경 생성
python -m venv .venv

# 활성화
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
```

### 2.2 의존성 설치

```bash
pip install -r requirements.txt
```

주요 패키지:
- `fastapi`, `uvicorn` -- API 서버
- `langchain`, `langgraph` -- LLM 에이전트 프레임워크
- `langchain-google-genai` -- Google Gemini 지원
- `SQLAlchemy` -- 비동기 ORM
- `pydantic` -- 데이터 검증
- `python-dotenv` -- 환경변수 로드

### 2.3 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성합니다:

```bash
cp .env.example .env
```

`.env` 파일 예시:

```dotenv
# === 데이터베이스 ===
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/postgres

# === LLM API 키 (사용할 프로바이더만 설정) ===
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...

# === 서버 설정 ===
# CORS_ORIGINS=http://localhost:5173
# LOG_LEVEL=INFO
```

> **주의**: `.env` 파일은 절대 Git에 커밋하지 마세요. `.gitignore`에 포함되어 있는지 확인하세요.

### 2.4 데이터베이스 초기화

```bash
python init_db.py
```

이 스크립트는 필요한 테이블을 자동으로 생성합니다.

### 2.5 서버 실행

```bash
# 개발 모드 (자동 리로드)
uvicorn main:app --reload --port 8000

# 프로덕션 모드
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

서버 시작 시 다음 순서로 초기화됩니다:
1. 데이터베이스 연결 확인
2. `model_type` 스키마 마이그레이션
3. 시스템 프롬프트 로드
4. MCP 레지스트리 초기화
5. OpenTelemetry 트레이싱 초기화

정상 실행 시 다음과 같은 로그가 출력됩니다:

```
🚀 서버 시작 프로세스 가동...
✅ 데이터베이스 연결 성공
✅ model_type 스키마 보강 완료
✨ 서버 준비 완료
```

### 2.6 API 문서 확인

서버 실행 후 Swagger UI에서 API를 확인할 수 있습니다:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 3. 프론트엔드 설정

### 3.1 의존성 설치

```bash
cd chat-frontend-vue
npm install
```

### 3.2 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일 예시:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

### 3.3 개발 서버 실행

```bash
npm run dev
```

브라우저에서 `http://localhost:5173` 으로 접속합니다.

### 3.4 프로덕션 빌드

```bash
# 타입 체크 + 빌드
npm run build

# 빌드 결과 미리보기
npm run preview
```

빌드 결과물은 `dist/` 디렉토리에 생성됩니다.

---

## 4. MCP 서버 설정 (선택)

MCP (Model Context Protocol)를 사용하면 외부 도구를 동적으로 연결할 수 있습니다.

### 4.1 MCP 서버 설정 파일

`chat-backend/mcp_servers.json` 파일에 MCP 서버를 등록합니다:

```json
{
  "mcpServers": {
    "example-server": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "your-api-key"
      }
    }
  }
}
```

### 4.2 MCP 도구 확인

서버 실행 후 등록된 MCP 도구 목록을 확인할 수 있습니다:

```bash
curl http://localhost:8000/mcp/tools
```

MCP 서버 초기화에 실패하더라도 챗봇 서버는 정상 동작합니다 (MCP 도구만 사용 불가).

---

## 5. OpenTelemetry 설정 (선택)

분산 추적을 활성화하면 에이전트 실행 흐름을 관측할 수 있습니다.

### 5.1 환경변수

```dotenv
# === OpenTelemetry ===
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=chat-backend
```

### 5.2 수집기 설정

Jaeger 또는 OTLP 호환 수집기를 실행합니다:

```bash
# Jaeger (Docker)
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest
```

Jaeger UI: http://localhost:16686

### 5.3 추적 항목

활성화 시 다음 스팬이 자동으로 기록됩니다:

| 스팬 | 설명 |
|------|------|
| `orchestrator.run` | 전체 오케스트레이터 실행 |
| `orchestrator.resume` | HITL 재개 실행 |

각 스팬에는 `thread.id`, `session.id`, `model`, `hitl.interrupted`, `hitl.approved` 등의 속성이 포함됩니다.

---

## 문제 해결

### 데이터베이스 연결 실패

```
❌ 데이터베이스 연결 실패: ...
```

**확인사항:**
1. PostgreSQL이 실행 중인지 확인: `docker compose ps` 또는 `pg_isready`
2. `.env`의 `DATABASE_URL` 포트가 올바른지 확인 (Docker 사용 시 기본 `5433`)
3. 데이터베이스 사용자/비밀번호가 올바른지 확인

### MCP 레지스트리 초기화 실패

```
⚠️ MCP Registry 초기화 실패 (서버는 계속 동작): ...
```

이 경고는 MCP 서버 연결에 실패한 경우 발생합니다. MCP 기능 없이도 챗봇은 정상 동작합니다.

**확인사항:**
1. `mcp_servers.json` 파일의 JSON 형식이 올바른지 확인
2. MCP 서버 실행에 필요한 패키지가 설치되어 있는지 확인 (예: `npx` 사용 서버의 경우 Node.js 필요)
3. MCP 서버의 환경변수(API 키 등)가 올바른지 확인

### LLM API 호출 실패

**확인사항:**
1. `.env`에 API 키가 올바르게 설정되어 있는지 확인
2. API 키의 유효기간 및 사용량 한도 확인
3. 네트워크 연결 상태 확인 (프록시/방화벽 설정)

### 프론트엔드 빌드 실패

```bash
# 타입 에러 발생 시
npm run build
# -> vue-tsc 에러
```

**확인사항:**
1. Node.js 버전이 18 이상인지 확인: `node --version`
2. `node_modules` 삭제 후 재설치: `rm -rf node_modules && npm install`
3. TypeScript 타입 오류가 있는 경우 에러 메시지 확인 후 수정

### 포트 충돌

- 백엔드 기본 포트: `8000`
- 프론트엔드 기본 포트: `5173`
- PostgreSQL 기본 포트: `5433` (Docker) / `5432` (직접 설치)

포트 변경 방법:

```bash
# 백엔드
uvicorn main:app --port 9000

# 프론트엔드 (vite.config.ts 수정 또는)
npm run dev -- --port 3000
```
