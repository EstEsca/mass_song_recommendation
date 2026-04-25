---
name: add-sprint
description: docs/tracker/sprints/에 새 스프린트 본문 + 체크리스트(sprints_checklist/_TEMPLATE 복사) + CURRENT.md 갱신을 한 번에 처리한다. 사용자가 "새 스프린트 만들어줘", "S-NNN 시작" 등을 요청할 때 사용.
argument-hint: "[자연어 요청 또는 제목]"
---

# 스프린트 신설 스킬

새 스프린트는 **4개 파일**의 정합 처리가 필요하다. 이 스킬이 자연어 요청을 받아 한 번에 처리한다:

1. `docs/tracker/sprints/S-NNN-<제목>.md` — 본문(목표·범위·완료기준·회고 템플릿)
2. `docs/tracker/sprints_checklist/S-NNN-<제목>.md` — 체크리스트 (`_TEMPLATE.md` 복사 + 맞춤화)
3. `docs/tracker/sprints/CURRENT.md` — 활성/보류 등록
4. (선택) `ISSUES.md` — 포함 이슈의 설명에 `(S-NNN)` 표기 추가

## 자연어 파싱 가이드

다음 정보를 사용자 입력에서 추출:

| 정보 | 예 |
|---|---|
| **제목** | "출력 양식 도구", "선곡 피드백 누적" |
| **목표** (1~3줄) | "사용자 양식을 LLM이 변환하고 에셋화" |
| **포함 이슈** (선택) | "#36, #37" |
| **활성 여부** | "지금 활성으로", "일단 보류로" (기본: 보류) |
| **대표 작업** | "조표 데이터 추가" 등 |

명시되지 않은 정보는 사용자에게 되묻는다. **목표가 모호하면 활성화하지 말 것** (시작 전 `[👤] 목표·범위 본문 검토 후 승인` 체크 항목이 막힘).

## 실행 흐름

### Step 1: 자연어 파싱 + 정보 수집

`$ARGUMENTS`에서 제목·목표·포함 이슈·활성 여부를 추출. 부족한 정보는 묻기:

> 새 스프린트 정보를 정리합니다.
> - 제목: ?
> - 핵심 목표 (1~3줄):
> - 포함 이슈 (#NN 형태, 없으면 생략):
> - 활성으로 시작? (예: 기존 활성 스프린트는 자동으로 보류 전환됨 / 아니오: 보류 등록)

### Step 2: 다음 스프린트 번호 결정

`docs/tracker/sprints/`의 기존 `S-NNN-*.md` 파일을 Glob으로 조회 → 가장 큰 번호 +1.

### Step 3: 파일명 정규화

제목에서 파일명 안전 문자열 생성:
- 공백 → `-`
- 특수문자 제거 (괄호·콤마·따옴표 등)
- 한글은 그대로 사용 가능 (기존 스프린트가 `S-007-스키마-확장-데이터-추가.md` 형태)

예: "출력 양식 도구" → `S-010-출력-양식-도구.md`

### Step 4: 본문 작성

`docs/tracker/sprints/S-NNN-<제목>.md`에 다음 구조:

```markdown
# S-NNN: <제목>

**상태:** 활성 | 보류
**기간 시작:** YYYY-MM-DD (활성 시) | —
**기간 종료:** —

## 목표

<사용자가 제공한 목표 1~3개>

## 배경

<왜 이 스프린트가 필요한지. 사용자에게 1~2 문장 받기>

## 범위

(체크박스로 단계 작성. 사용자 협의 항목은 비워둠)

- [ ] 단계 1
- [ ] 단계 2

## 완료 기준

| 기준 | 목표 |
|------|------|
| ...  | ...  |

## 포함 이슈

- (사용자가 제공한 #NN 목록)
- (스프린트 진행 중 발견되는 새 이슈는 추가)

## 진행 로그

- YYYY-MM-DD: 스프린트 생성. 활성/보류 상태로 시작.

## 참고 문서

- (관련 ADR / 다른 스프린트 / spec 문서)
```

### Step 5: 체크리스트 작성

`docs/tracker/sprints_checklist/_TEMPLATE.md`를 Read → 맞춤화 → `docs/tracker/sprints_checklist/S-NNN-<제목>.md`로 Write.

맞춤화 항목:
- 제목 라인 `# S-NNN 체크리스트: <제목>`
- 본문 링크 `[../sprints/S-NNN-<제목>.md](...)`
- 진행 중 단계는 스프린트 본문의 "범위"와 일치시킴
- 메모 섹션에 생성 날짜 기록

### Step 6: CURRENT.md 갱신

활성 등록 시:
1. 기존 활성 스프린트(S-XXX) → "보류 중인 스프린트"로 이동 + 보류 사유 한 줄
2. 신규 스프린트를 "활성 스프린트"로 등록 + 체크리스트 링크 추가

보류 등록 시:
1. 기존 활성 스프린트는 그대로
2. 신규 스프린트를 "보류 중인 스프린트" 목록에 추가

CURRENT.md 형식 참조: 현재 파일을 Read해서 같은 스타일로 일관 작성.

### Step 7: ISSUES.md에 스프린트 표기 (선택)

사용자가 포함 이슈를 제공했다면, ISSUES.md의 해당 행 설명 끝에 ` (S-NNN)` 표기 추가. 사용자 확인 후 적용.

### Step 8: 결과 보고

```
## ✅ 스프린트 S-NNN 등록 완료

- 본문: docs/tracker/sprints/S-NNN-<제목>.md
- 체크리스트: docs/tracker/sprints_checklist/S-NNN-<제목>.md
- 상태: 활성 (또는 보류)
- 포함 이슈: #NN, #NN, ...

다음 단계:
- 활성: 체크리스트의 "시작 전" 섹션부터 진행
- 보류: 활성화 시 CURRENT.md 갱신 + 시작 전 체크리스트 확인
```

## 주의사항

- **번호는 자동 증가**, 중복 금지
- **활성 스프린트는 동시에 1개만** (배타적 활성 규칙) — 기존 활성을 자동 보류 전환
- **본문과 체크리스트는 한 쌍** — ID·제목 일치 강제
- **체크리스트의 "시작 전" 항목이 비어있는 채로 활성화하지 말 것** — 최소 사용자 승인은 받았는지 확인

## 관련

- 정책: [docs/tracker/work_management.md](../../../docs/tracker/work_management.md)
- 스프린트 정책: [docs/tracker/sprints/README.md](../../../docs/tracker/sprints/README.md)
- 체크리스트 정책: [docs/tracker/sprints_checklist/README.md](../../../docs/tracker/sprints_checklist/README.md)
- 템플릿: [docs/tracker/sprints_checklist/_TEMPLATE.md](../../../docs/tracker/sprints_checklist/_TEMPLATE.md)
