---
name: crawl-lyrics
description: 웹/로컬에서 가사를 적극적으로 수집한다. 사이트별 전략은 sources/*.md로 분리 관리. 실행 시 어떤 소스를 어떤 우선순위로 쓸지 사용자에게 확인 후 진행. "가사 크롤링", "웹에서 가사 찾아줘", "크롤러 돌려줘" 등에 사용.
argument-hint: "곡 번호/범위 또는 '미확보' (예: 30-50, 미확보)"
---

# 가사 크롤링 스킬

외부 호출을 포함하며 **토큰 소모가 크므로**, 사용자가 명시적으로 호출했을 때만 실행한다 (ADR-004).
사이트별 수집 전략은 `sources/*.md`로 분리되어 있다. 새 소스는 해당 디렉토리에 추가.

## 실행 조건

- 사용자가 **명시적으로** 크롤링을 요청해야 실행 (자동 실행 금지)
- 각 소스는 robots.txt 준수 확인이 끝난 것만 사용 (ADR-001)

## 등록 소스 (요약)

| ID | 소스 | 매칭 키 | 상태 | 전략 문서 |
|----|------|---------|------|-----------|
| C-001 | maria (굿뉴스) | 가톨릭성가번호 → URL | active | [sources/maria.md](sources/maria.md) |
| C-002 | PDF 추출 (로컬) | 성가집 번호 | active | [sources/pdf.md](sources/pdf.md) |
| C-003 | yseng.kr | 제목 완전 일치 | active | [sources/yseng.md](sources/yseng.md) |

### 사용 불가로 확인된 소스 (재조사 전 사용 금지)
| ID | 대상 | 사유 |
|----|------|------|
| X-001 | music.bugs.co.kr | robots.txt 전면 차단 |
| X-002 | www.melon.com | robots.txt 전면 차단 |
| X-003 | www.genie.co.kr | WebFetch 차단 |
| X-004 | gasazip.com | ClaudeBot/GPTBot 명시 차단 |
| X-005 | pauline.or.kr | 일반 봇 차단 |

## 실행 흐름

### Step 1: 대상 곡 파싱

`$ARGUMENTS` 해석:
- `30-50` → 30~50번
- `32 38 41` → 해당 번호만
- `미확보` 또는 인자 없음 → songs.json에서 `가사.확보여부 == false`인 곡 전체
- 명시된 번호라도 `-only-missing` 플래그가 있으면 미확보 곡만 필터

### Step 2: 소스별 적용 가능성 분석

대상 곡에 대해 각 소스를 아래 규칙으로 매핑:

1. **C-001 (maria)** 적용 가능:
   - `외부ID.가톨릭성가번호`가 있거나, maria jsonl에 제목 일치 곡이 존재
2. **C-003 (yseng)** 적용 가능:
   - 곡 제목이 존재 (= 전 곡). 단 maria로 이미 확보된 곡은 기본 제외
3. **C-002 (PDF)** 적용 가능:
   - 전 곡 (번호 기반). 하지만 품질이 낮아 우선순위 최하

각 곡에 대해 `적용가능 소스 리스트`와 `이미 확보된 소스`를 계산해 표 형태로 준비.

### Step 3: 사용자에게 실행 계획 프롬프팅 (필수)

아래 형식으로 반드시 제시한 뒤 **승인을 받고 실행한다**. 사용자가 수정을 요청하면 계획을 바꿔서 다시 제시.

```
=== 크롤링 실행 계획 ===
대상: N곡 (번호 ...)
현재 가사 확보 상태:
  - 이미 확보: X곡 (maria: a, yseng: b, PDF: c, 기타: d)
  - 미확보: Y곡

[적용할 소스 우선순위]
1. C-001 maria    — 기본 제공, 이미 수집된 jsonl에서 매칭만 다시 수행 (외부 호출 없음)
2. C-003 yseng    — maria 미매칭 곡에만. 제목 완전 일치로 검색. 요청당 1.2초 지연.
3. C-002 PDF      — 둘 다 실패한 곡에 한해, 별도 승인 시에만 실행 (품질 낮음)

[이번 실행 요약]
- C-001로 즉시 매칭 가능: m곡
- C-003 외부 호출 필요: n곡 (예상 소요 약 n*1.5초)
- 최종 예상 미매칭: k곡

진행할까요? 옵션:
  (a) 계획대로 진행
  (b) 소스 순서 변경 / 일부 소스만 사용 (어느 것?)
  (c) 대상 곡 축소 (번호?)
  (d) 취소
```

### Step 4: 승인 후 실행

각 소스의 전략 문서에 적힌 스크립트를 호출한다. 모든 크롤러는
**`jsonl` 저장 → songs.json in-place 병합**을 한 번에 수행한다 (공통 병합 정책은 아래 참고).

```bash
# C-001 maria — 번호 범위 크롤링 후 자동 병합
python scripts/crawler/crawl_maria.py <start> <end>
python scripts/crawler/crawl_maria.py --merge-only          # 기존 jsonl만 재병합

# C-003 yseng — 번호/범위 지정 후 자동 병합
python scripts/crawler/crawl_yseng.py 30-50 32 38
python scripts/crawler/crawl_yseng.py --merge-only

# C-002 PDF — extract-sheet-lyrics 스킬 경유 (songs.json 직접 갱신)
```

공통 옵션:
- `--no-merge` — jsonl만 남기고 songs.json은 건드리지 않음
- `--merge-only` — 크롤링 생략, 기존 jsonl만 병합
- `--force` — 아래 보호 정책을 무시하고 덮어쓰기

### 병합 정책 (공통)

`scripts/crawler/_merge.py`가 구현. 모든 크롤러가 공유.

1. 대상 레코드에 **`사용자수정시각`**이 있으면 **skip** — 사용자 수작업 보호
2. 대상 레코드가 **다른 소스**로 이미 `확보여부=True`면 **skip** — 소스 간 자동 교체 금지
3. 같은 소스 재수집이거나 빈 레코드면 갱신 (`가사.본문`, `출처`, `참조URL`, `수집시각`, 소스별 `외부ID`)
4. 병합 후 `metadata.updated`, `metadata.lyrics_count` 자동 갱신

각 스크립트는 resume을 지원하므로 중단/재실행에 안전.

### Step 5: 결과 보고

```
=== 크롤링 완료 ===
- C-001 maria:  +m곡 확보
- C-003 yseng:  +n곡 확보 (실패 p곡: 제목 완전 일치 없음 q, 본문 없음 r)
- 전체 확보율: X/495 → Y/495

여전히 미확보: Z곡 (예: #31, #33, ...)

후속 조치 제안:
- PDF 추출이 아직 안 된 곡: /extract-sheet-lyrics
- 제목이 다를 가능성이 있는 곡(yseng 후보 존재): sources/yseng 실패 레코드의 '후보' 참고
```

## 새 소스 추가 절차

1. `sources/_template.md` 복사 → `sources/<id>.md`
2. robots.txt 확인 결과 기록 (허용/차단/제한)
3. 크롤러 스크립트 작성 → `scripts/crawler/crawl_<id>.py`
   - resume 지원, User-Agent 식별, 지연 필수
   - **`_merge` 모듈 import** 후 `merge_into_songs_json()` 함수 추가
   - `--no-merge`, `--merge-only`, `--force` 공통 플래그 지원
4. 이 파일(SKILL.md)의 **등록 소스** 표에 한 줄 추가
5. ADR 작성 여부 판단: 정책적 결정이 있으면 `docs/decisions/ADR-NNN.md` 추가

## 주의사항

- **robots.txt 준수** 소스만 사용 (ADR-001)
- **차단 소스(X-###) 크롤링 요청** 시: 거부 + 이유 설명
- **제목 부분 일치로 자동 수집 금지** — 동명이곡/유사 제목 오매칭 위험 (yseng의 `#46`, `#41` 사례)
- **대량 실행 시** 소스별 지연 설정 확인 + 번호를 작게 쪼개서 진행
- 실행 계획(Step 3) **스킵 금지** — 사용자가 명시적으로 "바로 실행"이라 해도,
  적용할 소스 목록은 최소 한 줄이라도 제시하고 시작한다.
