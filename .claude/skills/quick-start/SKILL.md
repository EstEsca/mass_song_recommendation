---
name: quick-start
description: 새 세션 시작 시 프로젝트 컨텍스트를 자동 파악한다. CURRENT.md → 활성 스프린트 본문/체크리스트 → STATUS.md → ISSUES.md 순으로 읽고 다음 우선 작업을 보고. "세션 시작", "맥락 파악", "지금 뭐 할 차례야", "프로젝트 상태 보고" 등에 사용.
argument-hint: ""
---

# Quick Start 스킬

새 Claude 세션 시작 시 프로젝트의 현재 컨텍스트를 빠르게 파악하고, 다음 우선 작업을 사용자에게 한 화면 분량으로 보고한다.

이전에는 [docs/status/RESUME.md](../../../docs/status/RESUME.md)의 Quick Start 프롬프트를 복사해야 했다. 이 스킬이 자동 실행을 대체.

## 실행 흐름

### Step 1: 핵심 파일 순차 읽기

다음 순서로 Read:

1. **`docs/tracker/sprints/CURRENT.md`** — 활성 스프린트 + 보류 스프린트 포인터
2. **활성 스프린트 본문** — CURRENT.md에서 추출한 `docs/tracker/sprints/S-NNN-*.md`
3. **활성 스프린트 체크리스트** — `docs/tracker/sprints_checklist/S-NNN-*.md` (있으면)
4. **`docs/status/STATUS.md`** — 진행 수치, 다음 작업, 블로킹
5. **`ISSUES.md`** — 시작 전·진행 중 이슈만 빠르게 훑기

조건부 (필요 시 추가):
- 사용자가 스키마·vocab 관련 질문 → `docs/spec/schema.md`, `docs/spec/vocab.md`
- 미결정 검토 항목 언급 → `docs/tracker/CONSIDERATIONS.md`
- 작업 관리 정책 의문 → `docs/tracker/work_management.md`

체크리스트가 없는 보류 스프린트는 본문만 빠르게 훑고 넘어감.

### Step 2: 종합 보고

다음 형식으로 사용자에게 보고 (한 화면 분량):

```
## 📍 현재 컨텍스트

**활성 스프린트:** S-NNN <제목> (시작 YYYY-MM-DD)
**최근 STATUS 갱신:** YYYY-MM-DD

### 진행도

- 체크리스트: 시작 전 N개 / 진행 중 M개 / 완료 K개
- 미완 이슈 (시작 전·진행 중): 합계 N건 (담당 🤖 X / 🤝 Y / 👤 Z)
- 보류 스프린트: S-XXX, S-YYY

### 다음 우선 작업 후보 (2~3개)

1. **[작업 제목]** — 한 줄 설명. 관련: [링크]
2. **[작업 제목]** — 한 줄 설명.
3. **[작업 제목]** — 한 줄 설명.

준비되면 지시해주세요.
```

### Step 3: 작업 지시 대기

사용자가 결정하면 해당 작업으로 진행. 결정 전 추가 정보가 필요하면 사용자가 묻고, Claude는 관련 파일을 추가로 읽거나 답함.

## 보고 작성 원칙

- **간결성**: 사용자가 5초 안에 현재 위치를 파악 가능해야 함.
- **체크리스트 우선**: 활성 스프린트 체크리스트의 `[ ]` 미체크 항목 중 블로킹·우선순위 높은 것 위주로 추천.
- **이슈 우선순위**: 시작 전·진행 중 + 담당자 🤝/👤인 것 우선 (사용자 입력 필요).
- **링크 제공**: 추천 작업마다 관련 파일 한 줄.
- **모드 가이드**: 만약 활성 스프린트가 없거나 모든 항목이 완료되면, 보류 스프린트 활성화 후보 또는 신규 스프린트 제안.

## 자동 실행 트리거

다음 표현이 사용자 요청에 등장하면 호출:

- "/quick-start"
- "세션 시작" / "오늘 시작"
- "맥락 파악" / "현재 상태 보고"
- "지금 뭐 할 차례" / "다음에 할 일"
- "프로젝트 상태"

## 주의

- **읽기 전용** — 어떤 파일도 수정하지 않음
- **외부 호출 없음** — 순수 로컬
- **장황 금지** — 보고는 한 화면. 자세한 내용은 사용자 후속 질문 시 추가 Read

## 관련

- 가이드 원본: [docs/status/RESUME.md](../../../docs/status/RESUME.md)
- 활성 스프린트: [docs/tracker/sprints/CURRENT.md](../../../docs/tracker/sprints/CURRENT.md)
- 작업 관리 정책: [docs/tracker/work_management.md](../../../docs/tracker/work_management.md)
