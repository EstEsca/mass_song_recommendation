# ADR-002: find-lyrics와 repair-lyrics 스킬 분리

**일자:** 2026-04-16
**상태:** 채택

## 맥락

가사 수집 중 OCR/웹 검색 결과의 일부가 어색하거나 결손된 경우가 발생.
이를 웹 스니펫 기반으로 복구하는 기능이 필요.

두 가지 통합 방식을 검토:
1. find-lyrics 내부에 복구 단계 포함
2. repair-lyrics 별도 스킬로 분리

## 결정

**별도 스킬로 분리 (/repair-lyrics)**.

- /find-lyrics: 소스 우선순위에 집중 (어디서 가져올지)
- /repair-lyrics: 품질 향상에 집중 (있는 자료 다듬기)

/find-lyrics는 가사 저장 완료 후, 신뢰도 '중' 이하 곡이 있으면 /repair-lyrics를 **제안**만 함 (자동 호출 X).

## 대안

1. **통합 스킬** — 기각 (책임 분리 원칙 위배, 재사용성 저하)
2. **자동 체인 호출** — 기각 (사용자 통제권 감소, 예상 못한 작업 실행)

## 결과

- **긍정**: 각 스킬을 독립 테스트 가능. 사용자가 OCR 결과만 들고 와서 복구만 요청 가능.
- **부정**: 사용자가 두 단계로 호출해야 함 (약간의 번거로움)

## 참조

- .claude/skills/find-lyrics/SKILL.md
- .claude/skills/repair-lyrics/SKILL.md
