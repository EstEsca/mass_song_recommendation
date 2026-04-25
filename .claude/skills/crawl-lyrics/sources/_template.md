---
id: C-XXX
name: 소스명
base_url: https://example.com
status: draft  # draft | active | blocked | deprecated
---

# 소스 전략: {이름}

## 개요
이 사이트가 어떤 성격의 사이트인지, 어떤 곡을 기대할 수 있는지 한두 문장.

## robots.txt
- 확인일: YYYY-MM-DD
- 결과: 허용 | 차단(사유) | 제한(조건)
- 링크: https://example.com/robots.txt

## 커버리지
- 대상: (예) 가톨릭성가 1~527번 / 청소년성가 / 생활성가 등
- 매칭 가능 예상 곡 수: N곡 / 495곡
- 확인 근거: (대화/실측/공식 문서)

## 매칭 키 (v2 — apply_to_xlsx 기준)
청소년청년성가집 번호로 직접 매칭 가능한 소스가 가장 다루기 쉽다.

1. 1순위: 청소년청년성가집 번호 직접 매칭 (jsonl `번호` ↔ 곡정보.xlsx 가사 시트)
2. 2순위: 제목 완전 일치/정규화 일치 (곡정보.xlsx 곡목록 시트의 `제목`)
3. fallback: 제목 유사도 (위험 — 오매칭 주의, 자동 채택 금지)

별도 외부 식별자(가톨릭성가번호 등)는 v2에선 청소년청년성가집 번호와 매핑이 없으므로
번호 또는 제목 매칭으로 환원 필요.

## 요청 방식
- 엔드포인트 패턴: `https://...`
- 예: `GET https://maria.catholic.or.kr/sungga/search/sungga_view.asp?ctxtIndex={번호}`
- 인증/쿠키 필요 여부: 없음 | 필요
- User-Agent: `SungaLiturgyBot/1.0 (...)`
- 지연: 초당 N회 / 요청당 N초 sleep

## 파서
- 가사 블록 추출 셀렉터/정규식:
- HTML 엔티티/줄바꿈 처리:
- 부가 콘텐츠(악보/유튜브 링크) 제거 규칙:

## 가사 없음 판별
링크만 있고 본문이 없는 페이지를 걸러내기 위한 휴리스틱.
- 예: 한글 문자 수 < 60, 가사 행 < 4개

## 스크립트 (v2)
- 경로: `scripts/crawler/crawl_XXX.py`
- 사용법:
  - `python scripts/crawler/crawl_XXX.py <번호 또는 범위 ...>` — 크롤링, **jsonl 생성만** (자동 병합 없음)
- 출력: `scripts/crawler/data/XXX.jsonl` (append, resume 지원)
- 레코드 필드 (표준): `번호`(청소년청년성가집), `제목`, `url`, `가사`, `매칭방식`, `수집시각`
  실패 레코드: `번호`, `제목`, `실패원인`, (선택) `후보`
- v1 흐름의 자동 병합(`_merge.py`)은 v2 미대응 → 신규 크롤러는 **자동 병합을 구현하지 말 것**

## v2 적용 (jsonl → 곡정보.xlsx)
- 적용 스크립트: `scripts/crawler/apply_to_xlsx.py <source_id>` 또는 `apply_to_xlsx.py <jsonl경로> --source <yseng|maria>`
- 매칭: jsonl `번호` 직접 (yseng 패턴) / jsonl `제목` 정규화 일치 (maria 패턴)
- 갱신 위치: 곡정보.xlsx의 `가사` 시트, 매칭 행의 본문 셀
- 보호: 가사 셀이 비어있는 곡만 채움 (이미 있으면 skip, `--force`로 덮어쓰기)
- 적용 후 `python scripts/rebuild.py`로 songs.json·songs_index.json 재빌드

## 주의사항 / 알려진 이슈
- 동명이곡(같은 제목 여러 곡) 처리
- 가사 오염(악보 설명, 코드 기호 포함)
- SSL/인코딩 이슈
