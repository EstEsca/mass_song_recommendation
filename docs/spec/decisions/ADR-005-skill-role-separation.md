# ADR-005: 가사 관련 스킬 역할 분리

**일자:** 2026-04-16
**상태:** 채택

## 맥락

기존 스킬 3종(`find-lyrics`, `repair-lyrics`, `extract-sheet-lyrics`) 역할이 일부 중복됨:
- `find-lyrics`가 크롤링 DB + 웹 + OCR 모두 시도 → 책임 과다
- `repair-lyrics`가 OCR 결과만 가정 → 입력 범위 모호
- `extract-sheet-lyrics`가 신뢰도 평가, 교차 검증까지 하려 함 → 경계 모호

ADR-002에서 find와 repair를 분리했지만, 추가로 extract와 validate도 명확히 분리해야 함.

## 결정

**4개 스킬의 역할을 다음과 같이 분리.**

### /extract-sheet-lyrics (1차 추출)
- 역할: PDF 텍스트 레이어 → songs.json 가사 필드
- 외부 호출: 없음
- 입력: 곡 번호/범위
- 출력: songs.json 갱신

### /validate-lyrics (형식 검증) [신규]
- 역할: songs.json의 가사가 형식 스펙을 준수하는지 검증
- 외부 호출: 없음
- 입력: songs.json
- 출력: 위반 리포트

### /repair-lyrics (웹 기반 복구)
- 역할: 어색한 구간을 WebSearch 스니펫으로 수정
- 외부 호출: WebSearch 多 (명시 요청 시에만)
- 입력: 곡 번호
- 출력: songs.json 갱신 (본문, 신뢰도)

### /find-lyrics (오케스트레이터)
- 역할: 위 세 스킬을 단계별로 호출하는 통합 흐름
- 외부 호출: 위임 (각 단계별 승인)
- 입력: 곡 번호/범위
- 출력: songs.json 갱신

## 대안

1. **단일 통합 스킬** — 기각 (책임 과다, 유지보수 어려움)
2. **extract + validate를 하나로** — 기각 (형식 검증은 수작업 입력에도 적용 필요)
3. **repair만 extract 결과 대상으로 한정** — 기각 (수작업 가사에도 적용 가능해야 함)

## 결과

**긍정:**
- 각 스킬이 단일 책임 원칙 준수
- 사용자가 필요한 단계만 호출 가능 (예: 수작업 입력 후 validate만)
- 각 스킬 독립 테스트 가능

**부정:**
- 사용자가 상황에 맞는 스킬을 선택해야 함 (→ find-lyrics가 오케스트레이션으로 해결)
- 4개 스킬 간 인터페이스(songs.json) 일관성 유지 부담

## 참조

- [docs/spec/skills_policy.md](../skills_policy.md)
- [docs/spec/schema.md](../schema.md)
- [ADR-002: find/repair 분리](ADR-002-skill-separation.md) — 이 결정의 확장
