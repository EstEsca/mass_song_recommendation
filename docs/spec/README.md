# 스펙

Claude가 정확성을 위해 참조하는 **정책·스키마·결정 기록**. 사람이 매뉴얼 보듯 따라하는 문서가 아니라, 자동화·스킬·스크립트의 행동 기준.

## 인덱스

| 문서 | 역할 |
|---|---|
| [schema.md](schema.md) | `data/songs.json` 공식 데이터 스키마 (v2.0). 곡 객체·색인·매핑 규칙 |
| [vocab.md](vocab.md) | 색인 카테고리별 허용값 (시기·성월·역할·느낌). controlled vocab |
| [lyrics_format.md](lyrics_format.md) | 가사 본문 형식 스펙 (절 마커 등) |
| [skills_policy.md](skills_policy.md) | 스킬들의 역할 경계·외부호출·소유 영역 |
| [decisions/](decisions/) | 아키텍처 결정 기록 (ADR-001 ~ ADR-006) |

## 사용

- **스킬·스크립트 작성 시**: vocab/format을 강제 검증
- **데이터 마이그레이션 시**: schema.md의 매핑 규칙을 기준
- **변경 시**: ADR 작성 → schema.md/vocab.md 갱신 → 영향 받는 스킬·스크립트 갱신
