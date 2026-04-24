# 성가 추천 시스템

한국 가톨릭 청소년/청년 성가대 선곡을 돕는 Claude Code 기반 도구 모음.

## 구성

### 스킬 (`.claude/skills/`)
- **`/recommend-hymns`** — 주일 전례 말씀(복음/독서)을 기반으로 봉헌·성체·파견·묵상 등 카테고리별 성가 추천
- **`/find-lyrics`** — PDF 이미지 판독 + 웹 검색으로 가사 정보 수집
- **`/add-issue`** — ISSUES.md에 새 이슈/할 일 추가

### 데이터
- `data/raw/곡목록.csv` — 청소년청년성가집 495곡 메타데이터 (번호, 제목, 작곡자, 비고)
- `data/raw/song_list_index_sample.xlsx` — 전례별/시기별/성월별/대축일별/성경구절 색인
- `data/songs.json` — 통합 곡 DB (495곡 + 가사 + 신뢰도)

### 스크립트 (`scripts/`)
- `scripts/fix_lyrics_format.py`, `scripts/validate_lyrics.py` — 가사 형식 교정/검증
- `scripts/crawler/_merge.py` — 크롤러 공용 in-place 병합 헬퍼 (사용자 수정 보호)
- `scripts/crawler/crawl_maria.py` — robots.txt 준수 가톨릭성가 크롤러 (maria.catholic.or.kr)
- `scripts/crawler/crawl_yseng.py` — yseng.kr 청소년성가 게시판 크롤러 (제목 완전 일치)
- `scripts/crawler/extract_pdf_lyrics_v3.py` — 성가집 PDF 텍스트 레이어 추출

각 크롤러는 수집 후 `songs.json`을 in-place 병합한다. 크롤링/병합 플로우는
`.claude/skills/crawl-lyrics/` 스킬과 `sources/*.md` 전략 문서 참고.

### 원본 자료 (`source/`, gitignored)
- `source/청소년청년성가집.pdf` — 주 원본 PDF
- `source/야훼이레원본.pdf` — 별도 성가 PDF
- `source/순서별로 정리/` — .nwc 악보 파일 모음

### 샌드박스 (`sandbox/`)
- 스킬을 안전하게 테스트하는 격리된 공간

### 이슈 추적
- `ISSUES.md` — 할 일/아이디어 목록

## 제외 항목 (.gitignore)

다음 파일들은 저작권 보호 대상이므로 저장소에 포함되지 않습니다:
- 성가집 PDF 원본 및 페이지 이미지
- 크롤링/OCR로 수집된 가사 데이터
- 로컬 설정 파일

개인 사용자는 합법적으로 보유한 자료를 로컬에 배치하여 사용합니다.

## 사용 조건

비영리 가톨릭 사목 활동(성가대 선곡 준비) 용도로 제작됨.
