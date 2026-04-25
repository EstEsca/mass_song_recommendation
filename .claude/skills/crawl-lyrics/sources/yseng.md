---
id: C-003
name: yseng
base_url: http://yseng.kr/xe/sungga
status: active
---

# 소스 전략: yseng (칸투스 파밀리아 / YSENG 성가 게시판)

## 개요
홍영삼 신부 운영의 XpressEngine 기반 성가 게시판. 가톨릭성가 외에도
**청소년성가·생활성가·청소년청년성가집** 고유 편곡본이 다수 등록되어 있어,
maria에 없는 곡의 가사를 보완할 수 있는 유일한 합법적 소스로 확인됨.

## robots.txt
- 확인일: 2026-04-24
- 결과: (미확인 — 첫 실행 전 확인 필요) `http://yseng.kr/robots.txt`
- XpressEngine 기본 정책은 대체로 개방적. User-Agent 식별 + 지연 필수.

## 커버리지
- 대상: 제목 기반 전문 검색. 가톨릭성가 ∪ 청소년성가 ∪ 생활성가 ∪ 일반성가.
- 실측(2026-04-24, songs.json #30~50 중 maria 미수집 15곡 대상):
  - 가사 본문 확보 가능: **10곡** (#32, #38, #39, #40, #41, #42, #44, #45, #46, #50)
  - 가사 본문 없음(악보·유튜브 링크만): **5곡** (#31, #33, #37, #43, #47)
- 따라서 maria로 먼저 커버한 뒤 **남은 곡의 2차 소스**로 권장.

## 매칭 키
1. **1순위**: 제목 완전 일치 (검색 결과 title 스트립 후 `==`)
2. **fallback**: 없음 — 부분 일치 매칭은 **금지**
   - 예: "나"(#41)로 검색하면 "나는 믿나이다", "나는 포도나무요" 등 대량 오매칭
   - 예: "나는 부활이요 생명이니"(#46, 이용천) vs "나는 부활이요 생명이니라"(#48, Wales trad) — 완전 일치로만 구분 가능
3. **복수 일치 시**: 작곡자 비교로 수동 선별 (스크립트는 경고 후 첫 결과 기록, 리포트 확인 권장)

## 요청 방식
- 검색: `GET http://yseng.kr/xe/?mid=sungga&search_target=title&search_keyword={url인코딩제목}&page={n}`
- 상세: `GET http://yseng.kr/xe/sungga/{document_srl}`
- SSL: 자체서명 인증서 사용 — **`http://` 로 요청**하거나 `verify=False` (스크립트는 `ssl.CERT_NONE`)
- User-Agent: `SungaLiturgyBot/1.0 (...)`
- 지연: 요청당 1.2초, 검색 페이지 간 0.3초

## 파서
- 가사 블록: `<!--BeforeDocument(srl,n)-->...<!--AfterDocument-->` 구간 안
  `<div class="document_{srl}_{n} xe_content">` 내부
- `<br>` / `</p>` → `\n`, HTML 엔티티 복원
- **정제 규칙** (`clean_lyrics`):
  - URL 포함 줄 제거
  - `악보`, `반주 음원`, `파트 음원`, `유튜브`, `영상`, `노래`, `...카페`, `...채널` 등
    섹션 헤더 줄 제거
  - `이 게시물을...` 꼬리 제거
  - 3개 이상 연속 개행 → 2개로 축소

## 가사 없음 판별 (`has_real_lyrics`)
페이지가 악보/유튜브 링크만 담고 있는 경우를 배제:
- 한글 문자 수 < 60 → False
- `http`를 포함하지 않고 4자 이상인 줄 중 한글 4자 이상 줄이 4개 미만 → False

## 스크립트
- 경로: `scripts/crawler/crawl_yseng.py`
- 사용법 (v2):
  - `python scripts/crawler/crawl_yseng.py 32 38 39 40-45 46 50` — 크롤링, **jsonl 생성만** (자동 병합 비활성화)
  - `--legacy-merge` / `--merge-only` 옵션은 v2에서 차단됨 (호출 시 에러 + 안내)
  - 범위(`a-b`) 및 개별 번호 혼용 가능
- 출력: `scripts/crawler/data/yseng_sungga.jsonl` (append, resume 지원)
  - 성공 레코드: `{번호, 제목, 작곡자, document_srl, url, 매칭방식, 가사, 수집시각}` (번호는 청소년청년성가집 번호)
  - 실패 레코드: `{번호, 제목, 실패원인, (후보)}`

## v2 적용 (jsonl → 곡정보.xlsx)
- 적용 스크립트: `scripts/crawler/apply_to_xlsx.py yseng`
- 매칭: jsonl의 `번호`(청소년청년성가집 번호) 직접 매칭 → 곡정보.xlsx의 `가사` 시트 같은 번호 행
- 갱신 필드: 가사 본문(2열) — v2에서는 `출처`·`참조URL`·`외부ID` 등 부가 메타 폐기
- 보호 정책:
  - 이미 가사 셀이 채워진 행은 skip → maria/PDF 우선이 자연스럽게 유지됨
  - `--force`로 덮어쓰기 가능
- 적용 후: `python scripts/rebuild.py`로 songs.json·songs_index.json 재빌드

## 주의사항 / 알려진 이슈
- 본문에 화성/박자 표기(`G 4/4 ♩=84`), 재편곡자명, 카페 링크 등이 섞여 있음 — 파서에서 1차 제거하되
  `/clean-lyrics` 스킬로 2차 정리 권장 (v2에서는 곡정보.xlsx의 가사 시트를 직접 정리).
- 검색 결과에 공지성 글(`칸투스 파밀리아 유튜브 공개 성가` 등)이 섞이면 제외.
- 같은 제목 복수 곡에 주의 (예: `길` 여러 건). 작곡자 비교 없이 자동 반영 금지.
