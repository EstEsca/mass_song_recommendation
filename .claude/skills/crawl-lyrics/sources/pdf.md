---
id: C-002
name: pdf
base_url: source/청소년청년성가집.pdf  (로컬)
status: deprecated
---

# 소스 전략: PDF 텍스트 추출 (로컬) — DEPRECATED

> ⚠️ **DEPRECATED (2026-04-25~) — v2 미대응**
>
> 이 소스를 사용하는 [extract-sheet-lyrics 스킬](../../extract-sheet-lyrics/SKILL.md)이
> v2 스키마 미대응으로 deprecated 처리되었다. PDF 추출 결과는 v1 시절의 `절별` dict 출력 포맷을
> 사용하는데, v2 가사는 단일 문자열이라 직접 호환되지 않는다.
>
> 향후 PDF 재추출이 필요해지면 `extract_pdf_lyrics_v3.py`를 v2 출력 포맷으로 리팩토링한 뒤
> `apply_to_xlsx.py`로 곡정보.xlsx에 적용하는 흐름으로 재구성해야 한다.
>
> 현재 청소년청년성가집 PDF 추출 결과는 이미 v1 → v2 마이그레이션 시점에 곡정보.xlsx에 반영되어 있으므로
> 추가 호출 가능성은 낮다.

## 개요
청소년청년성가집 PDF 파일에서 텍스트 레이어를 위치 기반으로 파싱해 가사를 추출한다.
외부 호출이 없고 robots.txt 무관. OCR 아님 — 임베디드 텍스트 레이어만 사용.

## robots.txt
- 해당 없음 (로컬 파일)

## 커버리지
- 대상: 청소년청년성가집 전 곡 (495곡, 번호 1:1 대응)
- 현재 추출: 약 262곡 (출처 = `PDF추출(v3)`)
- 한계: 악보 위 텍스트 레이어가 일부 왜곡되어 있어 **저신뢰 레코드 다수**
  (`신뢰도.등급 = 중/낮음`인 곡의 대부분이 여기서 나옴)

## 매칭 키
- **1순위**: 청소년청년성가집 번호 (songs.json `번호` == PDF 내 곡 번호)
- 다른 매칭 없음 (번호가 모든 것)

## 요청 방식
- 해당 없음 — 로컬 파일 처리

## 파서
- `scripts/crawler/extract_pdf_lyrics_v3.py`
- 텍스트 좌표 기반 라벨링: 절 구분은 y좌표로 1/2/3절 분리
- 부가 메타(화성·코드)는 가능한 한 제거

## 가사 없음 판별
- 텍스트 레이어 자체가 없는 페이지는 빈 문자열 반환 → 신뢰도 0점으로 표시

## 스크립트
- 경로: `scripts/crawler/extract_pdf_lyrics_v3.py`
- 사용법: 스킬 `extract-sheet-lyrics` 참고
- 출력: songs.json에 직접 write (현재) — 별도 jsonl 없음

## songs.json 병합
- `extract-sheet-lyrics` 스킬 / `extract_pdf_lyrics_v3.py`가 songs.json에 직접 in-place 갱신
- 다른 크롤러와 달리 현재는 `_merge.py` 헬퍼 미사용 — 추출기 자체에 갱신 로직 내장
- `가사.출처 = "PDF추출(v3)"`, 절별 분리 결과(`가사.절별`, `가사.절구조`, `신뢰도`) 포함
- 정리 필요: 공통 보호 정책(사용자수정시각 등) 적용을 위해 `_merge.py` 채택은 후속 TODO

## 주의사항 / 알려진 이슈
- OCR이 아니라 임베디드 텍스트라서 **PDF 자체가 왜곡되어 있으면 복구 불가**
- 절 마커 오판정 많음 → `fix-lyrics-format` / `structure-lyrics` 후속 필요
- 저작권 표기, 화음 기호, 음표 마커 잔존 빈번
