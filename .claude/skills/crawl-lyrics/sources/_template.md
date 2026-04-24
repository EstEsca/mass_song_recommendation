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

## 매칭 키
가장 신뢰할 수 있는 식별자부터 나열.

1. 1순위: 예) 가톨릭성가번호 (외부ID.가톨릭성가번호)
2. 2순위: 제목 완전 일치
3. fallback: 제목 유사도 (위험 — 오매칭 주의)

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

## 스크립트
- 경로: `scripts/crawler/crawl_XXX.py`
- 사용법:
  - `python scripts/crawler/crawl_XXX.py <번호 또는 범위 ...>` — 크롤링 + 자동 병합
  - `python scripts/crawler/crawl_XXX.py --merge-only`
  - 옵션: `--no-merge`, `--force`
- 출력: `scripts/crawler/data/XXX.jsonl` (append, resume 지원)
- 레코드 필드: 번호, 제목, url, 가사, 매칭방식, 수집시각

## songs.json 병합
- 크롤러 내부에서 `_merge.py` 헬퍼로 in-place 병합 (공통 구조)
- 매칭 키: (예) 번호 또는 제목 완전 일치
- 갱신 필드: `가사.본문`, `가사.출처=<source_id>`, `가사.참조URL`, `가사.수집시각`,
  소스별 `외부ID.<field>`
- 보호 정책: [SKILL.md § 병합 정책](../SKILL.md#병합-정책-공통) 공통 규칙 적용

## 주의사항 / 알려진 이슈
- 동명이곡(같은 제목 여러 곡) 처리
- 가사 오염(악보 설명, 코드 기호 포함)
- SSL/인코딩 이슈
