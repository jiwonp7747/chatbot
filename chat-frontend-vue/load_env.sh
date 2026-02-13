#!/bin/bash
# .env 파일의 환경변수를 시스템 환경에 export하는 스크립트
#
# 사용법:
#   source load_env.sh          # 현재 셸에 환경변수 로드
#   source load_env.sh .env.local  # 특정 파일 지정
#
# npm 스크립트에서 사용:
#   "dev": "source load_env.sh && vite"

ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "[load_env] $ENV_FILE 파일을 찾을 수 없습니다."
  return 1 2>/dev/null || exit 1
fi

COUNT=0

while IFS= read -r line || [ -n "$line" ]; do
  # 빈 줄, 주석 스킵
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

  # KEY=VALUE 형태만 처리 (= 기준으로 분리, bash/zsh 호환)
  KEY="${line%%=*}"
  VALUE="${line#*=}"

  # KEY 유효성 검사 (공백/특수문자 포함 시 스킵)
  [[ -z "$KEY" || "$KEY" =~ [^A-Za-z0-9_] ]] && continue

  # 따옴표 제거
  VALUE="${VALUE#\"}"
  VALUE="${VALUE%\"}"
  VALUE="${VALUE#\'}"
  VALUE="${VALUE%\'}"

  export "$KEY=$VALUE"
  COUNT=$((COUNT + 1))
done < "$ENV_FILE"

echo "[load_env] $ENV_FILE 로드 완료 ($COUNT개 환경변수)"
