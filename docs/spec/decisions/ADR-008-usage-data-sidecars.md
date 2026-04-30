# ADR-008: 사용 경험 데이터 — 사이드카 4개 도입 (선곡표·집계·로그)

**상태:** 채택 (2026-04-30)
**관련 ADR:** [ADR-006: 스키마 v2.0 전환](ADR-006-schema-v2.md), [ADR-007: 스키마 v2.1](ADR-007-schema-v2.1-음악메타-확장.md)

## 맥락

`/recommend-hymns`가 현장에서 더 유용해지려면 두 종류의 정보를 누적해야 한다.

1. **이번 달 부른 선곡표** — 매달 추천을 받고 다듬은 결과. 추천 시 중복 회피 기준이자, 다음 달 회고의 단위.
2. **곡별/미사 전체 소감** — "떼창 좋다·도입부 어렵다·음역 높다"처럼 학생들과 부딪쳐 본 인상. 다음 달 추천에 반영.

기존 자산만으로는 부족했다.
- `색인.비고`(v2.1 부활) 한 줄로는 누적·시계열을 담을 수 없다.
- `선곡기록.csv`는 행 단위 누적이라 "한 달치 묶음을 다듬는" 흐름과 맞지 않는다.
- 카탈로그 SSoT(`곡정보.xlsx`)에 사용 경험을 끼워 넣으면 빌드 파이프라인이 사용 데이터로 오염된다.

## 결정

### 4개 사이드카 저장소 (모두 카탈로그 빌드 외부)

| 데이터 | 저장소 | 편집 경로 |
|---|---|---|
| 선곡표 | `data/source/선곡표.xlsx` | 엑셀 직접 / `/log-setlist` |
| 곡별 집계 (사용경험) | `data/song_impressions.json` | viewer / `/log-impression` 후 승인 |
| 소감 raw | `data/impression_log.jsonl` | `/log-impression` append + viewer audit |
| (deprecated) 선곡 계획 누적 | `선곡기록.csv` | 1회 마이그레이션 후 종료 |

### 단일 SSoT 원칙은 카탈로그에 한정한다

[schema.md:35](../schema.md) 의 "사람이 편집하는 파일은 `data/source/곡정보.xlsx` 하나뿐"은 **카탈로그 도메인**에 적용되는 원칙으로 재해석한다.

- **카탈로그**: 곡의 정체성 — 제목·작곡자·색인·가사. 단일 파일 SSoT 유지.
- **사용 경험**: 사용자의 누적 판단·소감·선곡 이력. 카탈로그와 도메인이 다르므로 별도 저장소.

이 구분을 명시함으로써 사이드카 도입이 SSoT 원칙 위배가 아니라 도메인 분리임을 분명히 한다.

### 빌드 파이프라인 외부

[`scripts/rebuild.py`](../../../scripts/rebuild.py) 는 `곡정보.xlsx → songs.json → songs_index.json` 만 다룬다. 본 ADR에서 신설하는 4개 저장소는 빌드가 건드리지 않으므로 viewer/스킬이 직접 써도 덮어쓰기 위험이 없다.

### 자동 채움 금지 — 집계는 항상 사용자 승인 게이트

`feedback_no_auto_field_fill` 원칙을 본 영역에도 적용한다. 곡별 집계(`song_impressions.json`)의 enum 값은 **사용자가 명시적으로 승인할 때만** 갱신된다.

두 갱신 경로:

1. **회고 기반**: `/log-impression`에서 raw 소감을 입력한 직후, LLM이 그 곡의 미반영 raw 엔트리(아래 watermark 참조)를 요약해 변경 제안 → 사용자 Y → 사이드카 갱신.
2. **viewer 직접 편집**: 사용자가 사용경험 편집 블록에서 enum/메모를 직접 수정 → 즉시 갱신.

### Watermark — `last_reflected_id`

각 raw 로그 엔트리는 8자리 hex `id`를 가진다. 곡별 집계 객체는 `last_reflected_id`를 보유하여 "이 곡 집계에 마지막 반영된 로그 id"를 추적한다.

- `/log-impression` 종료 직전, 곡별로 `last_reflected_id` 이후 엔트리를 카운트해 "미반영 N건" 프롬프트.
- 사용자가 갱신 승인하면 watermark를 가장 마지막 반영 id로 이동.
- 사용자가 미루면 raw만 남고 watermark는 그대로 — 다음 회고에서 누적 미반영분이 자연 노출.

### 양방향 기록 (viewer 편집 → audit 라인)

viewer에서 사용경험을 직접 편집하면 사이드카 갱신과 함께 `impression_log.jsonl`에 `출처:"viewer-edit"` audit 라인 1건이 append된다. watermark도 그 audit id로 이동.

목적: 모든 집계 변경이 raw 로그에 흔적으로 남아 추후 "왜 난이도가 상으로 잡혔는지" 추적 가능. git 변경 이력과 별개로 사용자 의도를 데이터로 보존.

### 추천 LLM 참조 정책

| 데이터 | 참조 시점 | 비용 |
|---|---|---|
| `song_impressions.json` | 매 추천 자동, 후보 평가 가중치 | 가벼움 |
| `impression_log.jsonl`의 `대상="미사"` (최근 1~2개월) | 추천 시작 시 1회 요약 컨텍스트 주입 | 중간 |
| `impression_log.jsonl`의 `대상="곡"` raw | 사용자 명시 요청 시만 grep | 비쌈 |

raw 로그를 매 추천 호출마다 통째로 읽지 않는다 — 곡별 집계가 1차 인풋, raw는 명시 요청·미사 회고 컨텍스트에 한정.

### 스킬 역할 분리

- `/log-setlist` — 선곡표 기록 (단독·`/recommend-hymns`에서 호출 모두 가능)
- `/log-impression` — 미사 후 소감 기록 + 집계 갱신 승인 게이트
- `/recommend-hymns` Step 7은 직접 csv 저장을 멈추고 `/log-setlist` 호출 제안으로 전환

## 결과

### 긍정

- 카탈로그 빌드 파이프라인이 사용 데이터로 오염되지 않는다.
- 사이드카는 viewer가 직접 써도 안전하다(rebuild 무관).
- 사용자가 미사 후 소감을 쌓되 집계 갱신은 본인 페이스로 결정한다.
- watermark 덕에 "회고만 하고 집계는 미루기"가 자연스럽다.
- viewer 편집도 raw 로그에 흔적이 남아 의도가 보존된다.

### 부정 / 비용

- 편집 가능 파일이 `곡정보.xlsx` 하나에서 사이드카 포함 다섯 곳으로 늘어난다 — 인지 부담↑. 그러나 도메인 구분이 명확하므로 운영상 혼동 위험은 낮다.
- 추천 시 두 종류의 데이터(`songs.json` + `song_impressions.json`)를 서버가 머지해야 한다. 어댑터 한 군데만 변경.
- raw 로그는 시계열로 누적되므로 매우 장기에는 양이 많아질 수 있음 — 본 단계 스코프는 무관, 추후 압축·요약 정책은 후속 검토.

## 변경 이력 정책 — 본 데이터는 "이력 기록"이 아니다

[schema.md:114](../schema.md#L114) 정신("변경 이력은 git으로만 추적")과 충돌하지 않도록 명시:

- `impression_log.jsonl`은 시계열 관찰 목적의 **데이터** — 시점별 사용자 인상이 그 자체로 의미를 가진다 (집계의 변경 이력 추적용이 아님).
- 곡별 집계 `song_impressions.json` 의 변경 이력은 git으로만 추적 (스키마 원칙 그대로 적용).

## 관련 문서

- [docs/spec/usage_data.md](../usage_data.md) — 본 ADR이 도입하는 4개 저장소의 구체적 형식
- [docs/spec/schema.md](../schema.md) — 카탈로그 스키마 (본 ADR과 분리된 도메인)
