# 프로젝트 현재 상태

**마지막 갱신:** 2026-11-04
**현재 Phase:** Phase 3 진입 직전 — 인프라 완성, 실전 운영 데이터 누적은 0

> 2026-11-04: 반년 공백(2026-05-01 ~) 후 재개. 사용자는 그 사이 저장소를 수정하지 않았고, 로컬에서 `/recommend-hymns`(모드 A)를 수 회 사용해 추천이 잘 되는 것을 확인함. 운영 Windows 머신 포맷으로 gitignore였던 xlsx·사이드카·PDF는 유실됨. 같은 날 두 세션이 병행: (1) 트래커 정리 — 끝난 스프린트를 닫고 활성을 비움, (2) 멀티 머신 규약 — 데이터 복구 + git 동기화 전환 + 경로 하드코딩 제거.

## 진행 수치

| 항목 | 수치 | 비율 |
|------|------|------|
| 곡 메타데이터 (번호·제목·작곡자·분류) | 495/495 | 100% ✅ |
| 조표·박자 (v2.1) | 495/495 | 100% ✅ (사용자 진리표) |
| **가사 확보** | **493/495** | **99.6%** ✅ (잔여 2곡 영문 원곡, #42) |
| 곡모음집(가톨릭성가) 자동 태깅 | 173/495 | 35% |
| 색인 시기 매핑 | 48/495 | 10% |
| **요약·느낌·키워드 라벨링** | 0/495 | **0%** ⏳ (#36) |
| **선곡표·소감 운영 기록** | 0건 | **0%** ⏳ (#15, 포맷으로 유실 #40) |
| 스키마 버전 | v2.1 | ✅ (2026-04-29) |
| 운영 스킬 | 핵심 7종 v2 (recommend·clean·crawl·add-tag·label·log-setlist·log-impression), 6종 deprecated, structure-lyrics DRAFT | ✅ |

## 데이터 레이어

| 계층 | 파일 | 편집 가능 | git 추적 | 상태 |
|---|---|---|---|---|
| 편집 SSoT | `data/source/곡정보.xlsx` (4시트) | ✅ 사람·에디터 | ✅ (2026-11-04부터) | songs.json에서 복구, 라운드트립 검증 완료 |
| 파생 SSoT | `data/songs.json` (v2.1) | ❌ 빌드 산출물 | ✅ | 자동 동기화 |
| 경량 색인 | `data/songs_index.json` | ❌ 파생의 파생 | ✅ (2026-11-04부터) | 자동 동기화 |
| 운영 사이드카 | `data/source/선곡표.xlsx`, `data/song_impressions.json`, `data/impression_log.jsonl` | ✅ 스킬·뷰어 | ✅ (2026-11-04부터) | 빈 상태로 초기화 |
| 원본 | `source/청소년청년성가집.pdf` | — | ❌ (저작권) | 로컬 재배치 완료 (2026-11-04, #39) |

> 2026-11-04 결정: **데이터 파일은 모두 git으로 동기화** ([manuals/multi_machine.md](../manuals/multi_machine.md)). 저장소는 비공개 개발 단계이므로 가사 포함 파일 추적 허용. public 전환 시 선행 조치는 [PROJECT.md 저작권 정책](PROJECT.md#데이터-저작권-정책) 참조.

## 활성 스프린트

**없음.** 다음 활성 후보는 [CURRENT.md](../tracker/sprints/CURRENT.md) 참조.

**보류**: [S-009](../tracker/sprints/S-009-출력-표-양식-도구.md), [S-010](../tracker/sprints/S-010-파일-관리-프로세스-리팩터링-후-수습.md), [S-012](../tracker/sprints/S-012-출력-양식-프리셋.md)

## 다음 작업 (우선순위 순)

1. **운영 기록 시작** (#15) — 다음 추천 확정 시 `/log-setlist`, 미사 후 `/log-impression`. 기억나는 과거 선곡이 있으면 #40으로 재입력. (👤)
2. **모드 B 회귀 테스트** (#37) — 운영 기록이 1~2회 쌓인 뒤 모드 A vs B 비교. (🤝)
3. **S-010 처분 결정** — 2026-11-04 재현 확인 완료: 가사 빈 화면 회귀 **재현 안 됨**. 잔여 목표(뷰어 메타·색인 편집 확장)를 축소 재정의/종료+이슈화/활성화 중 선택. (👤)
4. **#36 라벨링** — fail case가 나온 곡부터 점진. (🤝)

## 블로킹/이슈

- ⚠️ **모드 B 정확도**는 색인 라벨링(#36)에 의존.
- 🚧 그 외 외부 대기 없음.

## 최근 결정사항

- 2026-11-04: **멀티 머신 git 운영 규약 채택** ([manuals/multi_machine.md](../manuals/multi_machine.md)) — 데이터 파일 gitignore 해제(git이 유일한 동기화 수단), 로컬은 master 직접 + pull 선행, 클라우드는 `claude/*` → master ff 병합, Conventional Commits, Windows 전용 권한은 `settings.local.json`.
- 2026-11-04: **트래커 정리** — S-003·S-007 완료 처리, S-012 보류, 이슈 #4 완료·#24 스킵, #41·#42 신규. 활성 스프린트 없음 상태로 재시작.
- 2026-04-30: **사용 경험 사이드카 4종 도입** ([ADR-008](../spec/decisions/ADR-008-usage-data-sidecars.md)) — 선곡표·곡별 인상·소감 로그. 카탈로그 빌드 외부.
- 2026-04-29: **schema v2.1** ([ADR-007](../spec/decisions/ADR-007-schema-v2.1-음악메타-확장.md)) — 비고 부활 + 조표·박자.
- 2026-04-25: **schema v2.0 채택** ([ADR-006](../spec/decisions/ADR-006-schema-v2.md)) — xlsx SSoT, 3계층 분업, 색인 8카테고리.
- 2026-04-16: 중앙 데이터([ADR-003](../spec/decisions/ADR-003-json-schema-policy.md)), 외부 호출 정책([ADR-004](../spec/decisions/ADR-004-external-call-policy.md)), 스킬 역할 분리([ADR-005](../spec/decisions/ADR-005-skill-role-separation.md)).

## 갱신 규칙

- 세션 종료 시 Claude가 이 파일을 갱신
- "진행 수치", "다음 작업"은 매번 재검토
- "최근 결정사항"은 3개월 이상 지난 항목은 `../spec/decisions/`로 이동 (이미 ADR화된 경우 링크만 남김)
