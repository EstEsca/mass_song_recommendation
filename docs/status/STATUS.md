# 프로젝트 현재 상태

**마지막 갱신:** 2026-11-04
**현재 Phase:** 운영 도구 안정화 + 색인 라벨링 (Phase 2/3 사이)

## 진행 수치

| 항목 | 수치 | 비율 |
|------|------|------|
| 곡 메타데이터 | 495/495 | 100% ✅ |
| **가사 확보** (xlsx 가사 시트) | **493/495** | **99.6%** ✅ |
| 곡모음집(가톨릭성가) 자동 태깅 | 173/495 | 35% |
| 색인 시기 매핑 | 48/495 | 10% (자동 마이그레이션 결과) |
| 색인 대축일·역할 등 | 부분적 | 마이그레이션에서 정화 |
| **요약·느낌·키워드 라벨링** (수작업/LLM) | 0/495 | **0%** ⏳ |
| 스키마 버전 | v2.0 | ✅ (2026-04-25 채택) |
| 운영 도구(스킬) 상태 | 핵심 4종 v2, 6종 deprecated | ✅ |

## 데이터 레이어

| 계층 | 파일 | 편집 가능 | 상태 |
|---|---|---|---|
| 편집 SSoT | `data/source/곡정보.xlsx` (4시트) | ✅ 사람·에디터 | 운영 중 |
| 파생 SSoT | `data/songs.json` (v2.0) | ❌ 빌드 산출물 | 자동 동기화 |
| 경량 색인 | `data/songs_index.json` | ❌ 파생의 파생 | 자동 동기화 |
| 백업 | `data/songs.v1.bak.json`, `data/archive/신뢰도_스냅샷_2026-04-25.xlsx` | — | 보존 |

## 활성 스프린트

**[S-012 출력 양식 프리셋](../tracker/sprints/S-012-출력-양식-프리셋.md)** (2026-04-30 활성화, 체크리스트 전 항목 미착수)
- 대표 작업: 한 달치 추천 결과 → Google Sheets·마크다운 프리셋
- 체크리스트: [../tracker/sprints_checklist/S-012-출력-양식-프리셋.md](../tracker/sprints_checklist/S-012-출력-양식-프리셋.md)

**보류**: [S-003](../tracker/sprints/S-003-가사-완전복구.md), [S-007](../tracker/sprints/S-007-스키마-확장-데이터-추가.md), [S-009](../tracker/sprints/S-009-출력-표-양식-도구.md), [S-010](../tracker/sprints/S-010-파일-관리-프로세스-리팩터링-후-수습.md)

(활성 스프린트의 기준은 항상 [sprints/CURRENT.md](../tracker/sprints/CURRENT.md). 이 섹션은 2026-11-04에 CURRENT.md와 맞춤.)

## 다음 작업 (우선순위 순)

1. **S-007 진행** — 조표 vocab 결정 + xlsx 컬럼 추가 + 데이터 수집 경로 (🤝)
2. **S-009 활성화 가능** — 사용자가 양식 예시 제공하면 출력 표 양식 도구 (🤝)
3. **#36 라벨링** — 495곡 요약·느낌·키워드 라벨링 (`/label-lyrics`, 사용자 명시 요청 시 점진) (🤝)
4. **#37 회귀 테스트** — recommend-hymns 모드 B 실전 검증 (🤝)

## 블로킹/이슈

- ⚠️ **2026-11-04 데이터 유실·복구**: 운영 Windows 머신 포맷으로 gitignore였던 xlsx·사이드카·PDF 유실. `songs.json`에서 `곡정보.xlsx`·`songs_index.json` 완전 복구(라운드트립 검증 완료). 선곡표·소감 로그는 빈 파일로 초기화, 원본 PDF는 사용자 재배치 필요(#39, #40). 상세: [manuals/multi_machine.md](../manuals/multi_machine.md#배경-2026-11-04-데이터-유실과-복구)
- 🚧 그 외 외부 대기 없음
- ⚠️ **모드 B 정확도**는 색인 라벨링 완료에 의존 (#36이 핵심 변수)

## 최근 결정사항

- 2026-11-04: **멀티 머신 git 운영 규약 채택** ([manuals/multi_machine.md](../manuals/multi_machine.md)) — 데이터 파일 gitignore 해제(git이 유일한 동기화 수단), master 직접 + pull 선행, 클라우드는 `claude/*` → 로컬 병합, Conventional Commits, Windows 전용 권한은 `settings.local.json`
- 2026-04-25: **schema v2.0 채택** ([ADR-006](../spec/decisions/ADR-006-schema-v2.md)) — 신뢰도·외부ID·가사 중첩 제거, 색인 8카테고리, xlsx SSoT, 3계층 분업
- 2026-04-25: **가사 스킬 9종 정리** — 핵심 3종(clean/crawl/structure) 리팩토링, 6종 deprecated
- 2026-04-25: **추천 스킬 모드 B 도입** — Python 후보 필터(`filter_candidates.py`) + Wide TSV 직렬화로 토큰 ~75% 감축
- 2026-04-25: **트래커 시스템 정비** — 스프린트 + 체크리스트 한 쌍, work_management 정책, 카테고리 폴더 정리(tracker/spec/manuals/status)
- 2026-04-16: **songs.json 중앙 데이터 채택** ([ADR-003](../spec/decisions/ADR-003-json-schema-policy.md))
- 2026-04-16: **외부 호출은 명시 요청 시에만** ([ADR-004](../spec/decisions/ADR-004-external-call-policy.md))
- 2026-04-16: **가사 스킬 역할 분리** ([ADR-005](../spec/decisions/ADR-005-skill-role-separation.md))

## 갱신 규칙

- 세션 종료 시 Claude가 이 파일을 갱신
- "진행 수치", "다음 작업"은 매번 재검토
- "최근 결정사항"은 3개월 이상 지난 항목은 `../spec/decisions/`로 이동 (이미 ADR화된 경우 링크만 남김)
