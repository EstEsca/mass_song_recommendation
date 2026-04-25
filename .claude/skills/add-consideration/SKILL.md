---
name: add-consideration
description: docs/tracker/CONSIDERATIONS.md에 새 고려사항(C-NN) 섹션을 추가한다. 사용자가 "고려사항 추가", "이건 나중에 검토", "C-NN 등록" 등을 요청할 때 사용.
argument-hint: "[고려사항 제목 또는 자연어 설명]"
---

# 고려사항 추가 스킬

`docs/tracker/CONSIDERATIONS.md`의 끝에 표준 구조로 새 `## C-NN: <제목>` 섹션을 append한다. 갱신 이력에도 한 줄 추가.

## 표준 구조 (작성할 형식)

```markdown
## C-NN: <제목>

**상태:** 검토 필요
**카테고리:** <카테고리 — 예: 추천 알고리즘 / 인프라 / 데이터 구조 / 운영>

### 문제

<현재 상황의 문제점 또는 검토 동기>

### 검토 포인트

- <항목 1>
- <항목 2>

### 도입 시 이점

- <장점>

### 도입 시 비용

- <단점·복잡도>

---
```

## 실행 흐름

### Step 1: 자연어 파싱

`$ARGUMENTS`에서 다음을 추출:

| 정보 | 필수 | 예 |
|---|---|---|
| 제목 | ✓ | "벡터 임베딩 옵션화" |
| 카테고리 | ✓ | "추천 알고리즘" |
| 문제·동기 | ✓ | "키워드 검색의 한계" |
| 검토 포인트 | 권장 | "도입 시점, 옵션 구조" |
| 이점·비용 | 권장 | |

부족한 정보는 사용자에게 묻기. 모호하면 한두 문장이라도 받아서 채우기.

### Step 2: 다음 번호(C-NN) 결정

`docs/tracker/CONSIDERATIONS.md`를 Read → 가장 큰 `C-NN` 찾기 → +1.

### Step 3: 섹션 작성

표준 구조에 정보 채우기. **섹션은 "갱신 이력" 앞에 삽입** (CONSIDERATIONS.md는 끝에 갱신 이력 섹션이 있음).

### Step 4: 갱신 이력에 한 줄 추가

```markdown
## 갱신 이력

...
- YYYY-MM-DD: C-NN(<제목>) 추가
```

### Step 5: 결과 보고

```
## ✅ 고려사항 C-NN "<제목>" 등록 완료

- 위치: docs/tracker/CONSIDERATIONS.md
- 카테고리: <카테고리>
- 상태: 검토 필요

이 고려사항은 도입 결정 시 이슈 또는 스프린트로 승격 가능합니다.
```

## 주의사항

- **번호는 자동 증가**, 중복 금지
- **표준 구조 유지** — 4개 서브섹션(문제/검토 포인트/도입 시 이점/도입 시 비용)
- **사용자 정책 고려** — `feedback_no_auto_field_fill.md` 정신과 충돌하는 자동화 아이디어는 비용에 명시
- **상태 기본값**: "검토 필요". 이미 검토 진행 중이면 "검토 중", 결정됐으면 "채택" 또는 "기각"

## 관련

- 위치: [docs/tracker/CONSIDERATIONS.md](../../../docs/tracker/CONSIDERATIONS.md)
- 정책: [docs/tracker/work_management.md](../../../docs/tracker/work_management.md)
- 스프린트 신설: [/add-sprint](../add-sprint/SKILL.md)
- 이슈 등록: [/add-issue](../add-issue/SKILL.md)
