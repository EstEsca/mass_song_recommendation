# 사용 경험 데이터 스펙 (선곡표·집계·로그)

**상태:** 채택 (2026-04-30)
**관련 ADR:** [ADR-008: 사용 경험 데이터 — 사이드카 4개 도입](decisions/ADR-008-usage-data-sidecars.md)

카탈로그 스키마([schema.md](schema.md))와 분리된 **사용 경험 도메인**의 데이터 형식. 모든 저장소는 카탈로그 빌드(`rebuild.py`) 외부.

## 저장소 4개 구성

```
[엑셀 편집]                           [사이드카 JSON / JSONL]
data/source/선곡표.xlsx                data/song_impressions.json
  └ 시트 "선곡"                          └ 곡별 집계 (사용경험)
                                       data/impression_log.jsonl
                                         └ 소감 raw (append-only)
```

| 파일 | 형식 | 편집 경로 | 용도 |
|---|---|---|---|
| `data/source/선곡표.xlsx` | xlsx (Tall) | 엑셀 직접 / `/log-setlist` | 부른 곡 누적 — 추천 중복 회피 기준 |
| `data/song_impressions.json` | JSON | viewer / `/log-impression` 후 승인 | 곡별 사용경험 집계 — 추천 LLM 1차 입력 |
| `data/impression_log.jsonl` | JSONL append-only | `/log-impression` + viewer audit | 시점별 raw 소감 |

## `data/source/선곡표.xlsx`

단일 시트 `선곡`, Tall 형식 (한 행 = 한 주일 × 한 카테고리). 모든 셀 서식은 텍스트.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `주일` | str | `YYYY-MM-DD` (해당 주일 날짜) |
| `전례명` | str | `"부활 제5주일"`, `"부활대축일"` 등 |
| `카테고리` | str | `입당`·`봉헌`·`성체`·`파견`·`묵상` 등 |
| `곡번호` | int | 청소년청년성가집 곡 번호 |
| `곡명` | str | 정식 제목 |
| `선정이유` | str | 추천 시 LLM이 남긴 이유 또는 사용자 메모 |
| `비고` | str | 자유 메모 (옵션) |

**불변**
- 주일·곡번호 유일성 강제하지 않음 — 같은 주일에 한 카테고리에 여러 곡 부르거나, 한 곡을 여러 미사에 부르는 케이스 허용.
- 행은 누적 — 사용자가 직접 행 삭제·수정 가능. 별도 "확정 일자" 컬럼은 두지 않는다 (다듬은 결과 자체가 진리).
- 카탈로그 빌드와 무관. `rebuild.py` 영향 없음.

## `data/song_impressions.json`

```json
{
  "metadata": {
    "updated": "2026-04-27T20:14:33"
  },
  "songs": {
    "123": {
      "난이도":         "중",
      "음역":           "높음",
      "떼창적합":       true,
      "반주필수":       false,
      "메모":           "후렴 쉬움, 도입부 어려움. 청소년 반응 좋음.",
      "최종갱신":       "2026-04-27",
      "last_reflected_id": "a3f2b91c"
    }
  }
}
```

### 필드 명세

| 필드 | 타입 | 허용값 | 설명 |
|---|---|---|---|
| `난이도` | str \| null | `"상"`·`"중"`·`"하"`·`null` | 가창·반주 난이도 종합 인상 |
| `음역` | str \| null | `"높음"`·`"중간"`·`"낮음"`·`null` | 청년 평균 기준 |
| `떼창적합` | bool \| null | `true`·`false`·`null` | 회중 따라부르기 가능성 |
| `반주필수` | bool \| null | `true`·`false`·`null` | `false`면 무반주도 가능 |
| `메모` | str | — | 자유 텍스트, 비어있으면 `""` |
| `최종갱신` | str \| null | `YYYY-MM-DD` | 마지막 갱신일 (갱신 시 서버가 오늘자 자동) |
| `last_reflected_id` | str \| null | 8자리 hex | "이 곡 집계에 마지막 반영된 로그 id" (미반영 카운트 기준) |

곡 객체가 한 번도 만들어지지 않았으면 `songs[번호]` 키 자체가 없을 수 있다 — 클라이언트는 미존재를 모든 필드 `null`/`""` 로 해석.

### 갱신 경로

1. **회고 승인** (`/log-impression` 종료 직전 게이트)
2. **viewer 직접 편집** — 즉시 갱신 + audit 로그 1건 append + watermark 이동

자동 갱신 없음 — `feedback_no_auto_field_fill` 원칙.

## `data/impression_log.jsonl`

JSONL append-only. 한 줄 = 한 시점 한 대상의 인상.

```jsonl
{"id":"a3f2b91c","시각":"2026-04-27T20:14:33","대상":"곡","미사":"부활 제3주일","곡번호":123,"코멘트":"떼창 좋음","태그":["떼창"],"출처":"log-impression"}
{"id":"b9e0d442","시각":"2026-04-27T20:15:02","대상":"미사","미사":"부활 제3주일","곡번호":null,"코멘트":"봉헌-성체 텀이 길었음","태그":[],"출처":"log-impression"}
{"id":"c0a17e88","시각":"2026-04-29T11:02:11","대상":"곡","미사":null,"곡번호":234,"코멘트":"viewer 편집: 난이도 중→상","태그":[],"출처":"viewer-edit"}
```

### 필드 명세

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | str | 8자리 소문자 hex. 서버가 생성 (랜덤 또는 timestamp+rand). 중복 검사는 하지 않음(충돌률 사실상 0) |
| `시각` | str | ISO 8601, 초 단위. 서버 생성 |
| `대상` | str | `"곡"` 또는 `"미사"` |
| `미사` | str \| null | 미사 식별자(전례명 + 날짜로 충분). 직접 viewer 편집 등 미사와 무관하면 `null` |
| `곡번호` | int \| null | `대상="곡"`이면 필수. `대상="미사"`면 `null` |
| `코멘트` | str | 자유 텍스트 |
| `태그` | list[str] | 자주 쓰는 표현 재사용용. 자유 문자열, vocab 강제 없음 |
| `출처` | str | `"log-impression"`(스킬) / `"viewer-edit"`(UI 직접 편집) |

### Append 정책

- **중간 수정·삭제 금지**. 잘못 입력했으면 새 엔트리를 append해 정정한다 (예: `코멘트:"이전 코멘트 취소: ..."`).
- viewer 직접 편집 시 audit 라인 1건 자동 append + 그 곡 `last_reflected_id`도 그 id로 갱신.

## ID 생성 규칙

8자리 소문자 hex. 추천 구현: `secrets.token_hex(4)` (Python).

- 충돌률: 4억 분의 1 — 본 도메인 데이터 양(연 1000건 이하 예상)에서 사실상 0
- 짧고 가독성 양호 (사용자 프롬프트에 노출 가능)
- 시간 정보 포함 안 함 — `시각` 필드와 분리

## 변경 이력 정책

- `song_impressions.json` 변경 이력은 git에 의존 (스키마 원칙 그대로).
- `impression_log.jsonl`은 **시계열 관찰 데이터**로 분류 — "이력 기록"이 아니라 그 자체가 데이터. ADR-008 참조.

## 관련 문서

- [ADR-008: 사용 경험 데이터 사이드카](decisions/ADR-008-usage-data-sidecars.md) — 도입 결정·근거
- [schema.md](schema.md) — 카탈로그 스키마 (분리된 도메인)
