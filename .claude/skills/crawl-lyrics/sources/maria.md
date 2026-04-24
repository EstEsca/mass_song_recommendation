---
id: C-001
name: maria
base_url: https://maria.catholic.or.kr
status: active
---

# 소스 전략: maria (굿뉴스 성가 DB)

## 개요
CBCK 공식 포털 굿뉴스의 **가톨릭성가** 전체 DB. 가톨릭성가(1~527번 범위)에 한해
번호 기반으로 직접 조회 가능해 가장 정확도가 높다. 청소년청년성가집 수록곡 중
가톨릭성가 번호가 있는 곡(약 173곡)이 대상.

## robots.txt
- 확인일: 2026-04-16 (ADR-001)
- 결과: **허용** — `/*.pdf$`, `/root_file/`만 차단. 성가 페이지는 개방.
- 링크: https://maria.catholic.or.kr/robots.txt

## 커버리지
- 대상: 가톨릭성가 1~약 527번
- 현재 수집: 527곡 (`scripts/crawler/data/maria_sungga.jsonl`)
- songs.json 매칭 결과: 약 173/495곡 (`가사.출처 == "maria"`)

## 매칭 키
1. **1순위**: 가톨릭성가 번호 (URL의 `ctxtIndex` = 성가번호)
   - songs.json의 `외부ID.가톨릭성가번호` 혹은 제목 일치로 주입
2. **2순위**: 제목 완전 일치 (jsonl의 `제목` ↔ songs.json의 `제목`)
3. **3순위**: 제목 정규화(`norm_title`) 일치 (공백·구두점 제거)

## 요청 방식
- 엔드포인트: `GET https://maria.catholic.or.kr/sungga/search/sungga_view.asp?ctxtIndex={num}`
- 인증: 불필요
- User-Agent: `SungaLiturgyBot/1.0 (Korean Catholic liturgy preparation; non-commercial)`
- 지연: 요청당 1.5초 (`DELAY_SEC`)

## 파서
- 가사 블록: `<td class="... song_txt ..." colspan="5">...</td>`
- `<br>` → `\n`, HTML 엔티티 복원, 빈 줄 정리
- 메타: `<th>성가 번호/제목/분류/작곡가/작사가</th><td class="al">값</td>`

## 가사 없음 판별
가톨릭성가 번호가 없으면 페이지가 비어 있음 — 레코드를 건너뜀. 추가 휴리스틱 불필요.

## 스크립트
- 경로: `scripts/crawler/crawl_maria.py`
- 사용법:
  - `python scripts/crawler/crawl_maria.py <start> <end>` — 크롤링 + 자동 병합
  - `python scripts/crawler/crawl_maria.py --merge-only` — 기존 jsonl만 병합
  - 옵션: `--no-merge`, `--force`
- 출력: `scripts/crawler/data/maria_sungga.jsonl` (append)
- resume 지원 (기존 ctxtIndex는 skip)

## songs.json 병합
- 크롤러 자체가 `_merge.py` 헬퍼로 in-place 병합 수행
- 매칭 키: `jsonl.제목` → `songs.json.제목` (완전 일치) → `norm_title` 일치 순
- 갱신 필드: `가사.본문`, `가사.출처="maria"`, `가사.참조URL=[sungga_view URL]`,
  `가사.수집시각`, `외부ID.가톨릭성가번호=ctxtIndex`
- 보호 정책은 [SKILL.md § 병합 정책](../SKILL.md#병합-정책-공통) 참고
  (사용자수정시각 있으면 skip, 다른 소스 확보분은 skip)

## 주의사항 / 알려진 이슈
- 청소년청년성가집 전용 편곡/가사 변형은 maria에 없을 수 있음 — 제목 같아도
  가사가 다를 수 있으므로 **편곡 표기된 곡은 교차 검증** 필요.
- SSL 인증서 정상. 별도 우회 불필요.
