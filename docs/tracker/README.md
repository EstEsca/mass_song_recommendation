# 트래커

작업 트래커 — 스프린트·이슈·고려사항을 관리한다.

## 작업 단위

| 단위 | 위치 | 크기 | 의도 |
|---|---|---|---|
| **이슈** | [/ISSUES.md](../../ISSUES.md) (root) | 작음 (1~3시간) | 구체적 작업 항목 |
| **고려사항** | [CONSIDERATIONS.md](CONSIDERATIONS.md) | 미정 | 도입 검토·아이디어 |
| **스프린트** | [sprints/](sprints/) | 큼 (며칠~주) | 여러 이슈 묶음 |
| **스프린트 체크리스트** | [sprints_checklist/](sprints_checklist/) | 행동 점검표 | 단계별 점검 (Claude·사용자 책임) |

세 단위의 관계·라이프사이클은 [work_management.md](work_management.md) 참조.

## 빠른 진입점

- **현재 활성 스프린트**: [sprints/CURRENT.md](sprints/CURRENT.md)
- **이슈 추가**: `/add-issue` 스킬
- **새 스프린트 시작**: `/add-sprint` 스킬 (본문 + 체크리스트 + CURRENT.md 자동)
- **고려사항 등록**: `/add-consideration` 스킬

## 정책

- 새 작업·아이디어는 우선 **이슈** 또는 **고려사항**으로 등록.
- 여러 이슈가 한 목표를 향하면 **스프린트**로 묶음.
- 스프린트 본문(`sprints/`)과 체크리스트(`sprints_checklist/`)는 한 쌍 — 같이 작성, 같이 갱신.
- 이슈 상태 갱신(시작전·진행중·완료·스킵)은 작업 진행에 맞춰 즉시.

## 인덱스

- [work_management.md](work_management.md) — 세 단위 관리 정책 (라이프사이클·상호 참조 컨벤션)
- [CONSIDERATIONS.md](CONSIDERATIONS.md) — 미결정 검토 항목 (C-NN 형태)
- [sprints/README.md](sprints/README.md) — 스프린트 정책
- [sprints/CURRENT.md](sprints/CURRENT.md) — 현재 활성·보류 스프린트
- [sprints_checklist/README.md](sprints_checklist/README.md) — 체크리스트 정책
- [sprints_checklist/_TEMPLATE.md](sprints_checklist/_TEMPLATE.md) — 새 스프린트 시 복사할 템플릿
