# 새 세션 시작 가이드

이 프로젝트를 새로운 Claude 세션에서 이어서 작업할 때 참조하는 문서입니다.

## Quick Start 프롬프트

새 Claude 세션을 시작할 때, 아래 프롬프트를 복사해서 사용하세요:

```
성가 추천 프로젝트를 이어서 작업하겠습니다.

먼저 다음 파일을 이 순서로 읽고 현재 상황을 파악해주세요:

1. docs/RESUME.md     — 이 가이드 (읽는 순서 확인)
2. docs/PROJECT.md    — 전체 비전과 로드맵
3. docs/STATUS.md     — 현재 진행 상태 (가장 최신)
4. ISSUES.md          — 할일 목록과 담당자

읽고 나서:
- 현재 Phase와 다음 우선 작업을 간단히 보고
- 제가 이번 세션에서 무엇을 하면 좋을지 2~3가지 제안

준비되면 작업을 지시하겠습니다.
```

## 읽는 순서와 이유

| 순서 | 문서 | 왜 먼저? |
|------|------|---------|
| 1 | docs/RESUME.md | 읽는 순서와 맥락 파악 |
| 2 | **docs/sprints/CURRENT.md** | **현재 활성 스프린트 포인터** (세션 재개 최우선) |
| 3 | docs/PROJECT.md | 변하지 않는 기준점 |
| 4 | docs/STATUS.md | 가장 최신 진행 상황 |
| 5 | docs/schema.md | 데이터 스키마 기준 |
| 6 | docs/skills_policy.md | 스킬 설계 정책 |
| 7 | ISSUES.md | 구체적 할일 목록 |

**주의:** 필요 시에만 추가로 읽을 것:
- `.claude/skills/*/SKILL.md` — 스킬 세부 스펙 (스킬 수정 시만)
- `docs/decisions/*.md` — 과거 결정 이력 (근거 확인 시만)
- `docs/CONSIDERATIONS.md` — 미결정 이슈 (방향 변경 시만)
- `docs/lyrics_format.md` — 가사 형식 스펙 (작성/검증 시만)
- `data/songs.json` — 실제 운영 데이터 (작업 시만)
- `data/raw/곡목록.csv`, `data/raw/song_list_index_sample.xlsx` — 입력 소스 (수정 시만)

## 세션 종료 시 Claude가 할 일

작업 마무리 단계에서:

1. **STATUS.md 갱신**
   - 진행 수치 재계산
   - 완료/진행중/다음 작업 섹션 업데이트
   - 마지막 갱신 날짜 변경

2. **새로운 결정사항이 있으면 기록**
   - 중요도 높으면 `docs/decisions/ADR-NNN-주제.md` 생성
   - 간단한 것은 STATUS.md의 "최근 결정사항"에 추가

3. **새 이슈 발생 시**
   - ISSUES.md에 추가 (담당자 명시)

4. **세션 요약 출력**
   - 이번 세션에서 한 일 3~5줄
   - 사용자가 다음 세션에서 해야 할 일 (있으면) 명시

## 사용자가 세션을 끊을 때 Claude에게 요청할 말

```
세션 종료 전 마무리:
1. STATUS.md를 지금 상태로 갱신해줘
2. 새로운 결정이 있었으면 decisions/에 기록해줘
3. 오늘 한 일과 다음에 내가 할 일을 요약해줘
```

## 자주 사용되는 스킬 호출

```
/recommend-hymns    # 전례 기반 선곡
/find-lyrics        # 가사 수집
/repair-lyrics      # OCR 가사 복구 (/find-lyrics 후)
/add-issue          # 이슈 추가
```

## 문제 상황 대응

**Q. Claude가 프로젝트 맥락을 못 잡는다**
→ Quick Start 프롬프트를 다시 사용, RESUME.md부터 읽도록 지시

**Q. 스킬이 예상과 다르게 동작한다**
→ `.claude/skills/{스킬명}/SKILL.md`를 함께 읽고 수정 논의

**Q. 가사 데이터에 문제가 있다**
→ `scripts/crawler/data/maria_sungga.jsonl`는 로컬 파일, 직접 확인 가능
→ 청소년청년성가집 PDF는 저작권 자료, Claude가 대화창에 출력 제한됨

**Q. 세션이 오래 걸려 느려진다**
→ 긴 대화는 Claude Code의 `/clear` 또는 `/compact`로 정리
→ STATUS.md를 갱신한 후 새 세션으로 이어가기

## 프로젝트 핵심 파일 맵

```
s:/song_recommendation/
├── README.md                         # 프로젝트 개요
├── ISSUES.md                         # 할일 목록 (담당자별)
├── data/
│   ├── songs.json                    # 통합 곡 DB (주 운영 데이터)
│   └── raw/
│       ├── 곡목록.csv                  # 495곡 기본 메타데이터
│       ├── song_list_index_sample.xlsx  # 색인 (전례/시기/성경구절)
│       └── 가사_입력_템플릿.xlsx        # 수작업 입력용 템플릿
├── docs/
│   ├── PROJECT.md                    # 불변 기준점
│   ├── STATUS.md                     # 진행 상태 (매 세션 갱신)
│   ├── RESUME.md                     # 이 파일
│   ├── CONSIDERATIONS.md             # 미결정 이슈
│   └── decisions/                    # 주요 결정 이력 (ADR)
├── .claude/skills/                   # 스킬들
├── scripts/
│   ├── fix_lyrics_format.py          # 가사 형식 교정
│   ├── validate_lyrics.py            # 가사 형식 검증
│   └── crawler/
│       ├── _merge.py                 # 공용 in-place 병합 헬퍼
│       ├── crawl_maria.py            # maria 크롤러 + 자동 병합
│       ├── crawl_yseng.py            # yseng 크롤러 + 자동 병합
│       ├── extract_pdf_lyrics_v3.py  # PDF 텍스트 추출 (songs.json 직접 갱신)
│       ├── data/maria_sungga.jsonl   # 크롤링 결과 (gitignored)
│       └── data/yseng_sungga.jsonl   # 크롤링 결과 (gitignored)
├── viewer/                           # songs.json 뷰어 웹앱
├── inbox/                            # 임시/일회성 산출물 (gitignored)
├── sandbox/                          # 스킬 테스트 공간
└── (저작권 자료 - gitignored)
    ├── source/청소년청년성가집.pdf
    ├── source/야훼이레원본.pdf
    ├── source/순서별로 정리/          # .nwc 악보
    └── pages/                        # PDF 페이지 이미지
```
