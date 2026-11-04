# 새 세션 시작 가이드 (v2)

이 프로젝트를 새로운 Claude 세션에서 이어서 작업할 때 참조한다.

## Quick Start

**세션을 열면 먼저 저장소를 최신화한다** (여러 머신을 번갈아 쓰므로 필수):

```bash
git status                 # 지난 세션의 미커밋 변경이 없는지
git pull origin master
```

규약 전체는 [docs/manuals/multi_machine.md](../manuals/multi_machine.md) 참조 (새 머신 셋업·데이터 동기화·브랜치·커밋 형식·종료 체크리스트).

그 다음 한 줄만 입력:

```
/quick-start
```

`/quick-start` 스킬이 자동으로:
0. `git status`·`git log`로 작업 트리와 최신 커밋 확인 (pull이 안 된 상태면 경고)
1. `docs/tracker/sprints/CURRENT.md` → 활성 스프린트 본문 → 체크리스트 → `docs/status/STATUS.md` → `ISSUES.md` 순으로 읽고
2. 진행도·미완 이슈·보류 스프린트를 요약해 보고
3. 이번 세션에 할 만한 작업 2~3가지를 제안

자세한 동작: [.claude/skills/quick-start/SKILL.md](../../.claude/skills/quick-start/SKILL.md)

### 수동 호출이 필요한 경우 (스킬 미사용)

스킬 자동 실행이 막힐 때 다음 프롬프트를 복사해서 사용:

```
성가 추천 프로젝트를 이어서 작업하겠습니다.

먼저 다음 파일을 이 순서로 읽고 현재 상황을 파악해주세요:

1. docs/tracker/sprints/CURRENT.md             — 현재 활성 스프린트 포인터
2. (CURRENT.md에서 가리킨) 활성 스프린트 본문 + 체크리스트
3. docs/status/STATUS.md                       — 가장 최신 진행도
4. ISSUES.md                                   — 구체적 할일 목록

읽고 나서:
- 활성 스프린트 + 다음 우선 작업을 간단히 보고
- 이번 세션에 무엇을 하면 좋을지 2~3가지 제안

준비되면 작업을 지시하겠습니다.
```

## 읽는 순서와 이유

| 순서 | 문서 | 왜 |
|------|------|---|
| 1 | docs/status/RESUME.md | 이 가이드 (읽는 순서) |
| 2 | **docs/tracker/sprints/CURRENT.md** | **활성 스프린트 포인터** (세션 재개 최우선) |
| 3 | 활성 스프린트 본문 + 체크리스트 | 진행도와 다음 단계 |
| 4 | docs/status/STATUS.md | 진행 수치·블로킹·최근 결정 |
| 5 | docs/tracker/work_management.md | 이슈/고려사항/스프린트 관계 |
| 6 | ISSUES.md | 구체적 할일 |
| 7 | docs/manuals/multi_machine.md | 머신 간 git 동기화·브랜치·커밋 규약 (머신을 옮길 때) |

**필요할 때만 추가로 읽기:**
- `docs/spec/schema.md` — 스키마 작업 시
- `docs/spec/vocab.md` — 색인·라벨 작업 시
- `docs/spec/skills_policy.md` — 스킬 수정 시
- `docs/spec/decisions/*.md` — 결정 근거 확인 시
- `docs/tracker/CONSIDERATIONS.md` — 미결정 아이디어 검토 시
- `docs/manuals/server_runtime.md` — 서버 실행 시
- `docs/manuals/multi_machine.md` — 머신을 옮기거나 새 머신을 셋업할 때
- `docs/status/PROJECT.md` — 비전·아키텍처 재확인 시
- `.claude/skills/*/SKILL.md` — 특정 스킬 동작 확인 시

## 세션 종료 시 Claude가 할 일

작업 마무리 단계에서:

1. **활성 스프린트 체크리스트 갱신**
   - 완료된 항목 `[x]` 마킹 + 메모 추가
   - 새로 발견된 점검 항목 추가

2. **STATUS.md 갱신**
   - 진행 수치 재계산
   - 다음 작업 섹션 업데이트
   - 마지막 갱신 날짜 변경

3. **새 결정·새 이슈 기록**
   - 스키마/스킬 정책 변경 → `docs/spec/decisions/ADR-NNN-주제.md`
   - 작은 작업 → `/add-issue`
   - 보류 아이디어 → `/add-consideration`(예정) 또는 CONSIDERATIONS.md 직접

4. **세션 요약**
   - 한 일 3~5줄
   - 다음 세션 사용자 액션 (있으면) 명시

5. **커밋 + push** ([multi_machine.md §4-2](../manuals/multi_machine.md#4-2-종료-모든-머신-공통))
   - 데이터를 바꿨으면 `python scripts/rebuild.py` 후 xlsx·songs.json·songs_index.json 함께 커밋
   - 커밋 메시지는 Conventional Commits (`type(scope): 한국어 요약`)
   - `git push` 까지 끝내고 세션을 닫는다. 클라우드 세션은 `claude/xxx` 브랜치로 push → 사용자가 로컬에서 master 병합

## 사용자가 세션을 끊을 때 요청 예

```
세션 종료 전 마무리:
1. 활성 스프린트 체크리스트의 완료 항목 마킹
2. STATUS.md를 지금 상태로 갱신
3. 새 결정이 있었으면 ADR로 기록
4. 오늘 한 일과 다음에 내가 할 일 요약
5. 커밋하고 push (multi_machine.md 규약)
```

## 자주 사용되는 스킬 호출

```
/recommend-hymns       # 전례 기반 선곡 (모드 A 기본, B 선택 시 토큰 절감)
/clean-lyrics          # 가사 본문 정리 (xlsx 직접 편집)
/add-tag               # 자연어로 색인 태그 추가
/label-lyrics          # LLM 라벨링: 요약·느낌·키워드 제안
/crawl-lyrics          # 가사 크롤링 (jsonl + apply_to_xlsx + rebuild)
/add-issue             # 이슈 추가
```

## 문제 상황 대응

**Q. Claude가 프로젝트 맥락을 못 잡는다**
→ Quick Start 프롬프트 재사용, RESUME.md부터 읽도록 지시

**Q. 가사 편집기 저장이 409 Conflict**
→ 곡정보.xlsx가 엑셀로 열려 있음. 엑셀 닫고 재시도. [docs/manuals/server_runtime.md](../manuals/server_runtime.md) 참조.

**Q. songs.json·songs_index.json 동기화 깨짐**
→ `python scripts/rebuild.py --check`로 확인, `python scripts/rebuild.py`로 재빌드.

**Q. 스킬이 v1 시절처럼 동작한다**
→ deprecated 처리된 6개 중 하나일 수 있음. description의 `[DEPRECATED]` 표시 확인.

**Q. 다른 머신에서 작업한 내용이 안 보인다 / pull이 거부된다**
→ [docs/manuals/multi_machine.md](../manuals/multi_machine.md) 트러블슈팅. 보통 이전 머신에서 push를 안 했거나 이 머신에 미커밋 변경이 남은 것.

**Q. 세션이 길어 느려짐**
→ `/clear` 또는 `/compact`로 정리 후, STATUS.md 갱신·새 세션으로 이어가기

## 프로젝트 핵심 파일 맵 (v2)

```
<프로젝트 루트>/                           # clone 위치는 머신마다 다름 (multi_machine.md 참조)
├── README.md                              # 프로젝트 개요
├── ISSUES.md                              # 할일 목록
├── data/
│   ├── songs.json                         # v2.0 SSoT (파생, 빌드 산출물)
│   ├── songs_index.json                   # 경량 색인 (파생)
│   ├── songs.v1.bak.json                  # v1 안전 백업
│   ├── source/
│   │   └── 곡정보.xlsx                     # ⭐ 사람 편집 SSoT (4시트)
│   └── archive/
│       └── 신뢰도_스냅샷_2026-04-25.xlsx    # v1 신뢰도/외부ID 1회 백업
├── docs/
│   ├── README.md                          # 카테고리 인덱스
│   ├── tracker/                           # 작업 트래커
│   │   ├── work_management.md
│   │   ├── CONSIDERATIONS.md
│   │   ├── sprints/CURRENT.md             # 활성 스프린트 포인터
│   │   └── sprints_checklist/
│   ├── spec/                              # Claude 참조 정책·스키마
│   │   ├── schema.md
│   │   ├── vocab.md
│   │   ├── skills_policy.md
│   │   ├── lyrics_format.md
│   │   └── decisions/                     # ADR-001~006
│   ├── manuals/                           # 사용자 절차 가이드
│   ├── status/                            # 현황 (이 파일 포함)
│   └── study/                             # 학습 노트
├── .claude/skills/                        # 스킬 (v2 4종 + deprecated 6종 + 기본 3종)
├── scripts/
│   ├── rebuild.py                         # xlsx → JSON 일괄 재빌드
│   ├── build_songs_json.py
│   ├── build_song_index.py
│   ├── filter_candidates.py               # 모드 B 후보 필터
│   ├── serialize_candidates.py            # JSON → Wide TSV
│   ├── add_tag.py                         # /add-tag 백엔드
│   ├── apply_labels.py                    # /label-lyrics 적용 도구
│   └── crawler/
│       ├── crawl_maria.py
│       ├── crawl_yseng.py
│       └── apply_to_xlsx.py               # jsonl → 곡정보.xlsx
├── server/                                # FastAPI 어시스턴트 + 편집기
│   ├── app.py                             # v2 어댑터 + xlsx writer
│   └── ...
├── viewer/                                # 가사 편집 UI (server/app.py가 마운트)
└── (저작권 자료 - gitignored)
    └── source/청소년청년성가집.pdf
```
