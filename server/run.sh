#!/usr/bin/env bash
# 성가 선곡 어시스턴트 서버 기동
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "경고: ANTHROPIC_API_KEY 미설정. server/.env 를 만드세요." >&2
fi

exec python -m uvicorn server.app:app --host 0.0.0.0 --port 10007
