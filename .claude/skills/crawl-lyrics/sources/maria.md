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
- 청소년청년성가집 매칭 결과: 약 173/495곡 (v1 시절 `가사.출처 == "maria"`로 표기되던 곡; v2 마이그레이션에서 이 173곡은 `색인.곡모음집 = ["가톨릭성가"]`로 자동 태깅됨)

## 매칭 키 (v2 — `apply_to_xlsx.py` 기준)
1. **유일 매칭**: 제목 정규화 일치 (공백·구두점 제거 후 jsonl `제목` ↔ 곡정보.xlsx 곡목록 시트의 `제목`)
2. v1의 `외부ID.가톨릭성가번호` 키는 v2에서 폐기됨 (`색인.곡모음집 = ["가톨릭성가"]`로 대체) → 가톨릭성가번호로 직접 매칭하는 경로는 더 이상 없음
3. 제목이 미묘하게 다른 청소년청년성가집 편곡 등은 **수동 매칭/제목 정정** 필요

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
- 사용법 (v2):
  - `python scripts/crawler/crawl_maria.py <start> <end>` — 크롤링, **jsonl 생성만** (자동 병합 비활성화)
  - `--legacy-merge` / `--merge-only` 옵션은 v2에서 차단됨 (호출 시 에러 + 안내)
  - `--force` 옵션은 `--legacy-merge`용으로만 의미 있음 (v2 흐름에서는 무관)
- 출력: `scripts/crawler/data/maria_sungga.jsonl` (append)
- resume 지원 (기존 ctxtIndex는 skip)
- 현재 jsonl에 1~527까지 모두 수집되어 있어 일반적으로 재크롤링 불필요

## v2 적용 (jsonl → 곡정보.xlsx)
- 적용 스크립트: `scripts/crawler/apply_to_xlsx.py maria`
- 기록 위치: 곡정보.xlsx의 **`가사` 시트**, 매칭된 청소년청년성가집 번호의 행
- 갱신 필드: 가사 본문(2열) — v2에서는 `출처`·`참조URL`·`외부ID` 등 부가 메타 폐기
- 보호 정책: 이미 가사 셀이 채워진 행은 skip (`--force`로 덮어쓰기)
- 적용 후: `python scripts/rebuild.py`로 songs.json·songs_index.json 재빌드

## 주의사항 / 알려진 이슈
- 청소년청년성가집 전용 편곡/가사 변형은 maria에 없을 수 있음 — 제목 같아도
  가사가 다를 수 있으므로 **편곡 표기된 곡은 교차 검증** 필요.
- SSL 인증서 정상. 별도 우회 불필요.
