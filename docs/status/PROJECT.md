# 성가 추천 프로젝트

## 비전

한국 가톨릭 청소년/청년 성가대의 선곡 작업을 자동화하여, 매주 전례 말씀(복음/독서)에 가장 적합한 성가를 추천받는 시스템.

## 최종 목표

청소년청년성가집 495곡을 데이터베이스화하고, 주일 전례 말씀에 기반하여 봉헌·성체·파견·묵상 등 카테고리별 성가를 추천하는 Claude Code 기반 도구 완성.

## 아키텍처 (v2.0 — schema 2026-04-25 채택)

### 3계층 데이터 분업

```
[편집 계층 — 사람]                    [SSoT 계층 — 스킬]              [뷰 계층 — 빠른 색인]
data/source/곡정보.xlsx               data/songs.json                  data/songs_index.json
  ├ 시트 "곡목록"           build      (JSON, v2.0, 가사 포함)   build  (JSON, 가사 제외 경량)
  ├ 시트 "요약"          ────────▶                            ────────▶
  ├ 시트 "색인" (tall)                                                          │
  └ 시트 "가사"                                                                 │ 런타임
                                                                                ▼ Python이
                                                                          Wide TSV 직렬화
                                                                                │
                                                                                ▼
                                                                        [LLM 입력 — 프롬프트]
```

핵심 원칙:
- **편집은 곡정보.xlsx 한 곳에서만** (사람 + 에디터 둘 다)
- **JSON은 빌드 산출물** — 직접 편집 금지, 다음 빌드에 덮어쓰여짐
- **LLM 입력은 Wide TSV로 재직렬화** — JSON 대비 ~5배 압축

### 빌드 파이프라인

```
data/source/곡정보.xlsx
  │ scripts/build_songs_json.py
  ▼
data/songs.json
  │ scripts/build_song_index.py
  ▼
data/songs_index.json

scripts/rebuild.py — 위 둘 일괄
```

### 운영 스킬 (v2)

```
.claude/skills/
├── /recommend-hymns      [전례 기반 선곡 — 모드 A(Classic) + 모드 B(Funnel)]
├── /clean-lyrics         [본문 정리, xlsx 가사 시트 직접 편집]
├── /crawl-lyrics         [jsonl 수집 → apply_to_xlsx → rebuild]
├── /structure-lyrics     [DRAFT — 절/후렴 마커 부여]
├── /add-tag              [자연어 태그 추가, xlsx 색인 시트 append]
├── /label-lyrics         [LLM 라벨링: 요약·느낌·키워드 제안]
├── /add-issue            [ISSUES.md 추가]
└── (deprecated 6종)      validate-lyrics-format / get-lyrics-data-local /
                          repair-lyrics / extract-sheet-lyrics /
                          enrich-liturgy-index / fix-lyrics-format
```

### 외부 소스

```
cbck.or.kr                (주일 전례 말씀, recommend-hymns 호출 시)
maria.catholic.or.kr      (가톨릭성가 173곡 매칭, 크롤링 완료)
yseng.kr                  (청소년청년성가집 일부 보완, 크롤링 완료)
```

**핵심 참조 문서:**
- 데이터 스키마: [docs/spec/schema.md](../spec/schema.md) (v2.0)
- vocab: [docs/spec/vocab.md](../spec/vocab.md)
- 스킬 정책: [docs/spec/skills_policy.md](../spec/skills_policy.md)
- 작업 관리: [docs/tracker/work_management.md](../tracker/work_management.md)
- v2 전환 ADR: [docs/spec/decisions/ADR-006-schema-v2.md](../spec/decisions/ADR-006-schema-v2.md)

## 담당자 역할 분담

| 유형 | 표기 | 범위 |
|------|------|------|
| Claude 단독 | 🤖 | 자동화 가능한 데이터 작업, 분석, 매칭 |
| 협업 | 🤝 | Claude 제안 → 사용자 승인 |
| 사용자 단독 | 👤 | 저작권 보유 자료, 최종 판단 |
| 외부 블로킹 | 🚧 | 외부 기관 응답 대기 |

### Claude 담당 (🤖)
- 곡 메타데이터 정합성 + xlsx → JSON 빌드
- 로컬 DB 조회·통합·검증
- 공식 크롤러 실행 (robots.txt 준수)
- 전례 말씀 수집 (cbck.or.kr)
- 추천 알고리즘 (모드 A/B)
- 스킬 유지보수

### 사용자 담당 (👤)
- 곡정보.xlsx 직접 편집 (가사·색인·요약)
- 라벨링 결과 검수·승인
- 저작권자 공식 문의 (CBCK, 교구청)
- 최종 선곡 검토/승인
- 실전 성가대 피드백
- 우선순위 결정

### 협업 (🤝)
- 라벨링 (Claude 제안 → 사용자 승인 → apply_labels)
- 색인 보강 (`/add-tag`)
- 선곡 추천 → 검토/수정
- 스프린트 진행 (체크리스트 점검)

## Phase별 로드맵

### Phase 1: 기반 완성 ✅ 완료
- 스키마 v1.0 → v2.0 전환
- 곡 메타데이터 100%, 가사 99.6%
- 핵심 스킬 + 빌드 파이프라인 + 에디터

### Phase 2: 색인·라벨링 (인프라 완료, 라벨링은 미착수)
- ✅ S-007: 조표·박자 음악 메타 확장 (v2.1, 495곡 전수)
- ✅ S-011: 사용 경험 사이드카 (선곡표·인상·소감 로그)
- ⏳ #36: 495곡 요약·느낌·키워드 라벨링 — 실전 fail case 기반으로 점진
- 보류: S-009(외부 선곡표 import), S-010(에디터 회귀), S-012(출력 양식 프리셋)

### Phase 3: 실전 운영 (현재 — 2026-11-04 진입)
- 매주 추천 사용 → 피드백 누적
- 모드 B 가중치 튜닝
- 선곡기록 누적 → 다양성 자동 조정

## 데이터 저작권 정책

- **저작권 보호 자료**: PDF 원본, 페이지 이미지, 가사 본문
- **처리 원칙**: 사용자가 합법 보유한 자료 내에서만 처리. 가사 본문은 대화창 출력 제한.
- **현재 (비공개 개발 단계, 2026-11-04 결정)**: 저장소가 private이므로 가사 본문이 든 `data/songs.json`·`data/source/곡정보.xlsx`·`data/songs_index.json`과 개인 기록인 운영 사이드카(선곡표·인상·소감 로그)를 모두 git에 추적한다. 머신 간 동기화 수단을 git 하나로 통일하기 위한 의도적 선택이며, 로컬 머신 포맷으로 gitignore 데이터가 유실된 경험이 계기. 원본 PDF·페이지 이미지·크롤링 raw·OMR 산출물은 `.gitignore`로 계속 차단. 상세: [manuals/multi_machine.md](../manuals/multi_machine.md).
- **저장소를 public으로 전환할 경우 (필수 선행 조치)**: 가사 본문과 개인 기록이 든 파일을 공개하면 안 된다. 전환 전에 반드시 다음을 수행.
  1. `data/songs.json`·`data/source/곡정보.xlsx`·`data/songs_index.json`·운영 사이드카 3종을 `.gitignore`에 추가하고 추적 해제 (`git rm --cached`)
  2. git 히스토리에 이미 들어간 가사 본문·개인 기록 제거 (`git filter-repo` 등으로 히스토리 재작성) — 단순 삭제 커밋으로는 공개 시 과거 커밋에서 노출됨
  3. `data/raw/audiveris_sample/` 등 악보 파생물도 공개 여부 재검토
  4. 데이터 동기화를 git 외 수단(개인 클라우드 드라이브·private 데이터 저장소 등)으로 바꾸고 멀티 머신 가이드의 "새 머신 셋업"·"데이터 동기화" 절을 갱신

## 세션 연속성

- 다음 세션 진입: [RESUME.md](RESUME.md)
- 현재 진행도: [STATUS.md](STATUS.md)
- 활성 스프린트: [../tracker/sprints/CURRENT.md](../tracker/sprints/CURRENT.md)
- 작업 관리 정책: [../tracker/work_management.md](../tracker/work_management.md)
- 결정 이력: [../spec/decisions/](../spec/decisions/)
