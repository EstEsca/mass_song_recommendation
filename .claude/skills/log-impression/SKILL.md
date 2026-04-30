---
name: log-impression
description: 미사 후 곡별 또는 미사 전체에 대한 소감을 기록하고, 곡별 집계(song_impressions) 갱신 여부를 사용자에게 묻는다. raw 로그는 항상 남기되 집계는 사용자 승인 게이트를 거친다. "회고", "소감 남길게", "오늘 미사 후기", "log-impression" 등에 사용.
argument-hint: "[자연어 요청 또는 비워두기]"
allowed-tools: Bash(curl) Read
---

# 미사 소감 기록 스킬

미사 후 사용자가 남기는 인상(곡별·미사 전체)을 [`data/impression_log.jsonl`](../../data/impression_log.jsonl)에 raw로 누적하고, 일정량이 쌓이면 곡별 집계([`data/song_impressions.json`](../../data/song_impressions.json))의 enum 값을 갱신할지 사용자에게 묻는다.

## 데이터 모델 요약

- **raw 로그** (`impression_log.jsonl`): append-only. 한 줄 = 한 시점 한 대상의 인상. id 8자리 hex.
- **곡별 집계** (`song_impressions.json`): 추천 LLM이 빠르게 참조하는 뷰. enum 4개(`난이도`·`음역`·`떼창적합`·`반주필수`) + 메모 + `last_reflected_id`(watermark).
- **자동 갱신 없음**: 집계 변경은 항상 사용자 승인. ADR-008 + `feedback_no_auto_field_fill` 원칙.

상세는 [docs/spec/usage_data.md](../../docs/spec/usage_data.md).

## 실행 흐름

### Step A. 어떤 미사를 회고할지 정하기

다음 중 하나로 진행:

1. **자동 후보 제시**: GET `/api/setlist`로 선곡표 최근 행을 조회 → 가장 최근 미사 1~2개를 후보로 보여주고 "이 미사 회고할까요?" 묻기.
2. **사용자 직접 입력**: "2026-04-27 부활 제3주일 회고할게"처럼 사용자가 명시.

미사 식별자는 **전례명 + 날짜** 결합 문자열(예: `"부활 제3주일 (2026-04-27)"`)로 통일. raw 로그의 `미사` 필드에 그대로 기록.

### Step B. 곡별/미사 전체 분기

사용자에게 묻기:

> 이 미사에 대해 어떤 소감을 남기시겠어요?
> 1. 곡별로 — 해당 미사의 곡들을 하나씩 묻기
> 2. 미사 전체 — 한 덩어리로 자유 코멘트
> 3. 둘 다

**곡별 모드**: 선곡표에서 해당 미사 행을 가져와 카테고리·곡번호·곡명을 표로 보여준 뒤, 곡별로 짧은 코멘트와 (선택) 태그 묻기. 비워둔 곡은 건너뛰기 (강제 입력 X).

**미사 전체 모드**: 한 덩어리 자유 텍스트 (예: "봉헌-성체 텀이 길었음. 파견곡이 너무 가라앉음.").

### Step C. raw 로그 append

각 답변마다 POST `/api/impression-log`:

```bash
# 곡별 소감
curl -X POST http://localhost:8000/api/impression-log \
  -H "Content-Type: application/json" \
  -d '{"대상":"곡","미사":"부활 제3주일 (2026-04-27)","곡번호":123,"코멘트":"떼창 좋음","태그":["떼창"]}'

# 미사 전체 소감
curl -X POST http://localhost:8000/api/impression-log \
  -H "Content-Type: application/json" \
  -d '{"대상":"미사","미사":"부활 제3주일 (2026-04-27)","곡번호":null,"코멘트":"봉헌-성체 텀이 길었음"}'
```

서버가 `id`(8자리 hex)와 `시각`을 자동 채움. 응답에서 id를 받아두기.

### Step D. 집계 갱신 승인 게이트 (핵심)

**모든 raw append가 끝난 직후**, 이번 세션에서 곡별 소감을 입력받은 곡들을 대상으로:

1. 각 곡의 GET `/api/impressions/{num}`로 현재 집계 + 최근 raw 로그 조회.
2. `last_reflected_id` 이후의 미반영 raw 엔트리들을 식별 (이번 세션 + 이전 누적).
3. 곡별로 카운트 표시:

```
회고 정리:
  123번 ○○○: 미반영 4건 (이번 1건 + 누적 3건)
  87번 △△△: 미반영 1건 (이번만)

집계에 반영할까요? (곡별 Y/N 또는 "전부 Y"/"건너뛰기")
```

4. 사용자가 곡 X에 대해 Y → 그 곡의 미반영 raw 엔트리들을 LLM이 요약해 변경 제안:

```
123번 — 미반영 4건 요약:
  1. (2026-04-27) "떼창 좋음" [떼창]
  2. (2026-04-27) "후렴부 잘 따라옴"
  3. (2026-04-13) "도입부 음정 어려움"
  4. (이번) "청소년 반응 좋음"

제안 (집계 변경):
  난이도: (현재 미정) → 중
  떼창적합: (현재 미정) → true
  메모: "후렴 잘 따라옴, 도입부 음정 어려움. 청소년 반응 좋음."

이대로 갱신할까요?
```

5. 사용자 확정 → POST `/api/impressions/reflect`:

```bash
curl -X POST http://localhost:8000/api/impressions/reflect \
  -H "Content-Type: application/json" \
  -d '{
    "곡번호": 123,
    "사용경험": {"난이도":"중","떼창적합":true,"메모":"후렴 잘 따라옴, ..."},
    "last_log_id": "<가장 마지막 반영 raw 로그 id>"
  }'
```

`last_log_id`는 **이번에 반영하기로 한 raw 엔트리 중 가장 마지막의 id**. 서버가 이를 `last_reflected_id` watermark로 저장.

6. 사용자 N → raw만 남기고 watermark는 그대로. "다음 회고에서 또 보일 겁니다" 안내.

### Step E. 종료 보고

```
✓ raw 로그 5건 추가
✓ 곡별 집계 갱신: 123번
○ 곡별 집계 미반영: 87번 (다음 회고에서 다시 보일 것입니다)
```

## API 응답 처리

- POST `/api/impression-log`: `{"ok":true,"entry":{"id":"...","시각":"...",...}}`
- GET `/api/impressions/{num}`: `{"곡번호":N,"사용경험":{...,"last_reflected_id":"..."},"최근로그":[{...}]}`
  - `최근로그`는 기본 5건 — 더 필요하면 `?n=20` 쿼리 파라미터.
- POST `/api/impressions/reflect`: `{"ok":true,"곡번호":N,"사용경험":{...}}`

## 미반영 카운트 산출

```
GET /api/impressions/{num} → 사용경험.last_reflected_id 와 최근로그 비교
   → 최근로그 중 id가 last_reflected_id 이후인 것들 = 미반영
   → last_reflected_id == null 이면 모든 raw 엔트리가 미반영
```

`최근로그`는 기본 5건이므로 누적이 5건 초과면 `?n=50` 등으로 더 가져와 정확히 카운트. 양 적은 도메인이라 큰 N도 무리 없음.

## 주의

- **자동 갱신 절대 금지**: 사용자가 명시 Y 하지 않으면 집계 갱신하지 말 것. raw 로그만 남는다.
- raw 로그는 **수정·삭제 안 됨**. 잘못 입력했으면 새 라인을 append해 정정 (예: "이전 코멘트 취소: ...").
- 미사 전체 소감(`대상="미사"`)은 곡별 집계에 직접 반영되지 않는다 — 다음 추천 시 LLM이 "최근 1~2개월 미사 소감" 요약 컨텍스트로만 사용.
- 사용자가 회고 도중 빠져나가도 raw 로그는 이미 누적됨 (Step C가 끝났으면). 다음 회고에서 그 미반영 엔트리들이 자연 노출.

## 파라미터 미명시 시 진행 정책

`$ARGUMENTS`가 비어있으면 Step A부터 시작. argument에 미사 식별자가 있으면 Step A 건너뛰고 Step B부터.
