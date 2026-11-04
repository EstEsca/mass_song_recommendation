# 어시스턴트 + 편집기 서버 실행 매뉴얼

**갱신일:** 2026-11-04 (포트 10007 반영)
**적용 버전:** schema v2.0 / server/app.py v2 어댑터 적용본

브라우저로 어시스턴트(`/assistant/`)와 편집기(`/editor/`)를 띄우는 절차.

## 목적

- Claude 기반 채팅 어시스턴트 사용 (스킬 호출 — 추천·라벨링·태그 추가 등)
- 가사 편집기 UI 사용 (가사 본문 수정 → 곡정보.xlsx 자동 반영)

## 사전 준비

### 1) Python 의존성 설치

```powershell
# 프로젝트 루트에서
pip install -r server/requirements.txt
```

설치 항목: `fastapi`, `uvicorn`, `claude-agent-sdk`, `python-dotenv`, **`openpyxl`**, **`xlsx2csv`** (v2 도입).

### 2) 환경 변수

```powershell
copy server\.env.example server\.env
notepad server\.env
```

`ANTHROPIC_API_KEY`를 설정. (어시스턴트 채팅이 필요 없다면 비워둬도 편집기는 동작.)

### 3) 데이터 점검

다음 파일이 있어야 한다 (Stage A 마이그레이션 산출물):

- `data/songs.json` — schema v2.0
- `data/songs_index.json` — songs.json 파생
- `data/source/곡정보.xlsx` — 사람 편집 SSoT

없거나 stale이면:

```bash
python scripts/rebuild.py --check
```

`stale_vs_xlsx: true` 또는 `stale_vs_songs: true`가 보이면:

```bash
python scripts/rebuild.py
```

## 실행

```powershell
# Windows PowerShell
powershell -File server\run.ps1

# 또는 직접
python -m uvicorn server.app:app --host 0.0.0.0 --port 10007 --reload
```

## 접속

| 경로 | 용도 |
|---|---|
| http://localhost:10007/ | 랜딩 페이지 (어시스턴트/편집기 선택) |
| http://localhost:10007/assistant/ | Claude 채팅 (스킬 호출) |
| http://localhost:10007/editor/ | 가사 편집기 (viewer/index.html 마운트) |

## 편집기 사용 (가사 본문 수정)

1. `/editor/` 접속
2. 곡 목록에서 수정할 곡 선택
3. 가사 본문 textarea 편집 → 저장
4. 백엔드 동작:
   - **v2 어댑터**가 v1 형식 patch에서 `가사.본문`만 추출
   - `data/source/곡정보.xlsx`의 `가사` 시트 해당 행에 직접 쓰기
   - 자동으로 `python scripts/rebuild.py` 호출 → `songs.json`·`songs_index.json` 동기화
5. 응답에 `"rebuilt": true` 표시되면 정상

> **편집 가능 범위**: v2 어댑터는 가사 본문만 실제 반영함. 절별·절구조·참조URL·검증완료 등 v1 필드는 무시(응답 `무시된_필드`에 명시). 색인 등은 엑셀 직접 또는 `/add-tag` 스킬로.

## 외부 공유 (ngrok, 옵션)

```powershell
ngrok http 10007
```

`https://xxx.ngrok-free.app` URL만 지인에게 공유. 보안 주의는 [server/README.md](../../server/README.md) "보안/비용" 섹션 참조.

## 종료

서버 실행 콘솔에서 `Ctrl+C`.

## 검증

서버 시작 후 다음 명령으로 동작 확인:

```bash
# Health check
curl http://localhost:10007/api/status
# → {"busy": false, ...}

# 곡 데이터 (v1 호환 형태로 어댑트되어 반환)
curl http://localhost:10007/api/songs | python -m json.tool | head -50
```

## 트러블슈팅

### `409 Conflict — 곡정보.xlsx가 잠겼습니다`

엑셀에서 `data/source/곡정보.xlsx`를 열어둔 상태에서 편집기 저장 시 발생.

**해결**: 엑셀에서 파일 저장 후 닫고 재시도.

### `500 — rebuild failed`

`scripts/rebuild.py` 실행 중 오류. 로그를 확인:

```bash
python scripts/rebuild.py
```

흔한 원인:
- xlsx 시트 헤더 변경 (예: `번호`·`타입`·`값` 외 컬럼이 들어감)
- vocab 위반 값 다수 (build_songs_json이 경고하지만 실패는 안 함)
- songs.json 손상

복구가 안 되면 `data/songs.v1.bak.json`(마이그레이션 시점 백업)으로 롤백 후 재마이그레이션 가능.

### `Address already in use` (포트 10007 충돌)

다른 프로세스가 10007을 사용 중.

```powershell
# 사용 프로세스 확인
netstat -ano | findstr :10007

# 다른 포트로 실행
python -m uvicorn server.app:app --port 8765
```

### `ModuleNotFoundError: openpyxl` 등

```powershell
pip install -r server/requirements.txt
```

### 편집기에서 저장이 안 됨 + 서버 콘솔에 에러 없음

브라우저 캐시 문제일 수 있음. 강력 새로고침(`Ctrl+F5`).

또는 `data/songs.json`과 `곡정보.xlsx`의 sha256 동기화 깨짐:

```bash
python scripts/rebuild.py
```

후 페이지 새로고침.

### `viewer/server.py` 단독 실행 시 즉시 종료

의도된 동작. v2 미대응으로 deprecated 처리됨. `server/app.py`(FastAPI)를 사용하라.

## 알려진 제약

- 어시스턴트 세션은 **한 번에 하나만**. 두 번째 요청은 `busy` 이벤트.
- 편집기 vs Claude 세션 동시 수정의 원자적 보장은 없음 — Claude가 가사 관련 스킬을 돌리는 동안에는 편집기 저장 자제.
- 매 가사 수정마다 자동 rebuild가 호출됨 (~수초). 빈번한 수정 시 약간의 지연.

## 관련 문서

- [server/README.md](../../server/README.md) — 서버 자체 README (엔드포인트·SSE·보안)
- [docs/spec/schema.md](../spec/schema.md) — 데이터 스키마 v2.0
- [docs/manuals/](.) — 다른 매뉴얼
- [scripts/rebuild.py](../../scripts/rebuild.py) — 빌드 파이프라인
