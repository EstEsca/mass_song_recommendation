# 성가 선곡 어시스턴트 (웹)

이 프로젝트의 스킬(`/recommend-hymns`, `/validate-song-list`, ...)을
브라우저에서 프롬프팅으로 호출할 수 있게 해주는 얇은 웹 래퍼.

Claude Agent SDK(Python)로 Claude를 구동하고, FastAPI + SSE로
브라우저에 스트리밍한다. 한 번에 한 세션만 실행된다.

기존 [viewer/](../viewer/) 가사 편집기도 같은 서버에 `/editor/` 경로로
마운트되어, 채팅 페이지 상단 링크로 접근할 수 있다. 편집은 `data/songs.json`
에 즉시 반영된다 — ngrok URL을 아는 사람은 누구나 편집 가능.

## 구성

- [app.py](app.py) — FastAPI 앱, `/api/chat` SSE 스트림
- [agent.py](agent.py) — Agent SDK 래퍼, 세션 락, 경로 안전 검사
- [static/](static/) — 바닐라 JS 채팅 UI

## 준비

```powershell
# 프로젝트 루트에서
pip install -r server/requirements.txt
copy server\.env.example server\.env
# server\.env 를 열어 ANTHROPIC_API_KEY 설정
```

## 실행

```powershell
# Windows
powershell -File server\run.ps1
# or
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```

로컬 테스트: http://localhost:8000

## 외부 공유 (ngrok)

```powershell
ngrok http 8000
```

ngrok이 출력한 `https://xxx.ngrok-free.app` URL만 지인에게 공유한다.

## 허용 범위

- **사용자 작업 범위**: 프로젝트 스킬 호출 위주 (system prompt로 안내)
- **허용 도구**: `Read, Write, Edit, Glob, Grep, WebFetch, Bash`
- **차단**:
  - `Write`/`Edit` 대상 경로가 `s:/song_recommendation/` 밖이면 에러
  - 프롬프트 2000자 초과 거부
  - 세션당 최대 30턴
- **동시성**: 전역 `asyncio.Lock` — 두 번째 요청은 즉시 `busy` 이벤트

## 보안/비용 ⚠️

인증이 없다. ngrok URL이 유일한 장벽이므로:

1. **ngrok URL을 공개 채널(SNS, 블로그)에 올리지 말 것.** 스캐너가 발견할 수 있다.
2. **Anthropic 콘솔에서 월간 spend limit을 설정하라.** 악용 시 과금 폭주 방지.
3. **프롬프트 로그**: 모든 프롬프트는 [logs/prompts.jsonl](logs/prompts.jsonl)에 기록된다.
   정기적으로 확인하고, 이상 행위가 보이면 즉시 ngrok을 끊는다.
4. **파일 변경은 auto-commit 하지 않는다.** 서버 운영자가 로컬에서 `git diff` 로
   검토 후 직접 커밋한다.

## 엔드포인트

| Method | Path | Desc |
|---|---|---|
| GET | `/` | 랜딩 페이지 (어시스턴트/편집기 선택) |
| GET | `/assistant/` | 채팅 UI |
| GET | `/editor/` | 가사 편집기 (viewer/index.html) |
| GET | `/api/skills` | `.claude/skills/*/SKILL.md` 목록 |
| GET | `/api/status` | 현재 세션 점유 상태 |
| GET | `/api/songs` | `data/songs.json` 전체 (편집기용) |
| PUT | `/api/songs/{num}` | 특정 곡의 가사/검증 플래그 패치 |
| POST | `/api/chat` | 프롬프트 → SSE 스트림 |
| POST | `/api/interrupt` | 현재 세션 취소 |

## 편집기 ↔ Claude 충돌

편집기는 `data/songs.json`만 건드리고, Claude 세션은 스킬 실행 중
해당 파일을 Write/Edit로 수정할 수 있다. 동시 수정 시의 대응:

- 편집기 PUT에는 `SONGS_LOCK` (asyncio.Lock)이 걸려 있어 편집기끼리는 직렬화됨
- 편집기 vs Claude는 원자적 조정이 없음 — 이론상 마지막 쓰기 승리
- 운영 팁: Claude가 `songs.json`을 건드리는 스킬(fix-lyrics-format 등)을
  돌리는 동안에는 편집기 저장을 피할 것. 필요하면 작업 후 편집기 새로고침

## SSE 이벤트

- `start` — 세션 시작
- `busy` — 다른 사용자 작업 중
- `assistant` — Claude 메시지 블록 (`text` / `tool_use`)
- `user_tool_result` — 도구 결과 (주로 에러 보고용)
- `result` — 완료 (비용/턴수)
- `error` — 오류 메시지
- `done` — 스트림 종료

## 알려진 제약

- 세션 중단은 `POST /api/interrupt` 로 가능하지만 SDK 내부에서
  진행 중인 도구 실행이 즉시 멈추지 않을 수 있다.
- Agent SDK가 업데이트되며 메시지 블록 타입 이름이 바뀌면
  [agent.py](agent.py)의 `_serialize_content_block`을 손봐야 할 수 있다.
