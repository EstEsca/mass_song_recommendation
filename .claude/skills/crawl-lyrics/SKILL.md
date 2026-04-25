---
name: crawl-lyrics
description: 웹/로컬에서 가사를 적극적으로 수집한다. 사이트별 전략은 sources/*.md로 분리 관리. 실행 시 어떤 소스를 어떤 우선순위로 쓸지 사용자에게 확인 후 진행. "가사 크롤링", "웹에서 가사 찾아줘", "크롤러 돌려줘" 등에 사용.
argument-hint: "곡 번호/범위 또는 '미확보' (예: 30-50, 미확보)"
---

# 가사 크롤링 스킬 (v2)

외부 호출을 포함하며 **토큰 소모가 크므로**, 사용자가 명시적으로 호출했을 때만 실행한다 (ADR-004).
사이트별 수집 전략은 `sources/*.md`로 분리되어 있다.

## v2 데이터 흐름 (중요)

```
크롤러 실행            jsonl 산출            검토 후 적용                 빌드 재실행
───────────           ───────────           ─────────────────           ─────────
crawl_maria.py   →    maria_sungga.jsonl
crawl_yseng.py   →    yseng_sungga.jsonl    →  apply_to_xlsx.py    →   rebuild.py
                                                  │                       │
                                                  ▼                       ▼
                                         data/source/곡정보.xlsx     songs.json
                                            (가사 시트)            songs_index.json
```

**핵심**: 크롤러는 **jsonl만 만든다**. v1 시절의 자동 병합(`_merge.py` 경유)은 v2 미대응이라 비활성화됨. 적용은 **`apply_to_xlsx.py`**가 담당한다.

## 실행 조건

- 사용자가 **명시적으로** 크롤링을 요청해야 실행 (자동 실행 금지)
- 각 소스는 robots.txt 준수 확인이 끝난 것만 사용 (ADR-001)

## 등록 소스

| ID | 소스 | 매칭 키 | 상태 | 전략 문서 |
|----|------|---------|------|-----------|
| C-001 | maria (굿뉴스) | 가톨릭성가번호 → 청소년청년 제목 일치 | active | [sources/maria.md](sources/maria.md) |
| C-002 | PDF 추출 (로컬) | 청소년청년 번호 | **DEPRECATED** | [sources/pdf.md](sources/pdf.md) |
| C-003 | yseng.kr | 청소년청년 번호 (입력) | active | [sources/yseng.md](sources/yseng.md) |

PDF 추출은 [extract-sheet-lyrics 스킬](../extract-sheet-lyrics/SKILL.md)이 v2 미대응으로 deprecated 처리되었다.

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
- `미확보` 또는 인자 없음 → 곡정보.xlsx의 가사 시트에서 본문이 비어있는 곡 전체

### Step 2: 소스별 적용 가능성 분석

대상 곡에 대해 각 소스를 아래 규칙으로 매핑:

1. **C-001 (maria)** 적용 가능:
   - 곡 제목이 가톨릭성가집의 곡 제목과 일치할 가능성 (사전 확신 어려움 — 시도해서 매칭 결과 확인)
2. **C-003 (yseng)** 적용 가능:
   - 곡 제목이 존재 (= 전 곡). 단 가사가 이미 있는 곡은 기본 제외

각 곡에 대해 `적용가능 소스 리스트`와 `이미 확보 여부`를 계산해 표 형태로 준비.

### Step 3: 사용자에게 실행 계획 프롬프팅 (필수)

아래 형식으로 반드시 제시한 뒤 **승인을 받고 실행한다**. 사용자가 수정을 요청하면 계획을 바꿔서 다시 제시.

```
=== 크롤링 실행 계획 ===
대상: N곡 (번호 ...)
현재 가사 확보 상태:
  - 이미 확보: X곡
  - 미확보:    Y곡

[적용할 소스 우선순위]
1. C-001 maria    — 기존 jsonl 재활용 가능 (외부 호출 없음, --merge-only 대신 apply_to_xlsx)
2. C-003 yseng    — maria 미매칭 곡에만. 제목 완전 일치로 검색. 요청당 1.2초 지연.

[이번 실행 요약]
- maria로 적용 가능: m곡 (이미 jsonl에 있음)
- yseng 외부 호출 필요: n곡 (예상 소요 약 n*1.5초)
- 최종 예상 미확보: k곡

진행할까요? 옵션:
  (a) 계획대로 진행
  (b) 소스 순서 변경 / 일부 소스만 사용
  (c) 대상 곡 축소 (번호?)
  (d) 취소
```

### Step 4: 승인 후 실행

```bash
# C-003 yseng — 번호/범위 지정해 jsonl 생성 (자동 병합 제거됨)
python scripts/crawler/crawl_yseng.py 30-50 32 38

# C-001 maria — 번호 범위 크롤링 (이미 1~527 수집된 jsonl이 있다면 재실행 불필요)
python scripts/crawler/crawl_maria.py <start> <end>

# v2 적용: jsonl → 곡정보.xlsx '가사' 시트
python scripts/crawler/apply_to_xlsx.py yseng        # yseng_sungga.jsonl 적용
python scripts/crawler/apply_to_xlsx.py maria        # maria_sungga.jsonl 적용
python scripts/crawler/apply_to_xlsx.py <path> --source yseng  # 임의 jsonl

# JSON 재빌드
python scripts/rebuild.py
```

**삭제된 옵션 (v1 호환 불가)**
- `--no-merge` / `--merge-only` / `--legacy-merge` — 모두 v1 `_merge.py` 경로. v2에서는 호출 시 에러 후 안내 출력.

### apply_to_xlsx.py 동작 요약

- **매칭 정책**:
  - yseng: jsonl '번호' (청소년청년성가집 번호) 직접 매칭
  - maria: jsonl '제목' ↔ 곡정보.xlsx 곡목록 시트의 '제목' 정확 일치 (가톨릭성가 번호로는 직접 매칭 불가)
- **보호 정책**:
  - 가사 셀이 비어있는 곡만 채움
  - 이미 채워져 있으면 skip (`--force`로 덮어쓰기)
  - jsonl 실패 레코드(가사 없음)는 skip
- **출력**: 적용·skip·매칭 실패 통계, 매칭 실패 샘플, rebuild 안내

### Step 5: 결과 보고

```
=== 크롤링 + 적용 완료 ===
- yseng:   +n곡 (jsonl 생성 → xlsx 적용)
- maria:   +m곡 (기존 jsonl → xlsx 적용)
- 전체 확보율: X/495 → Y/495

여전히 미확보: Z곡 (예: #31, #33, ...)
다음 단계: python scripts/rebuild.py
```

## 새 소스 추가 절차

1. `sources/_template.md` 복사 → `sources/<id>.md`
2. robots.txt 확인 결과 기록 (허용/차단/제한)
3. 크롤러 스크립트 작성 → `scripts/crawler/crawl_<id>.py`
   - resume 지원, User-Agent 식별, 지연 필수
   - **출력은 jsonl만**. 곡정보.xlsx 자동 갱신 금지 (ssoT는 사람 검토 거쳐 적용)
   - 출력 jsonl 키 표준: `번호`(청소년청년성가집 기준), `제목`, `가사`, `url`, `수집시각`, 실패 시 `실패원인`
4. 이 파일(SKILL.md)의 **등록 소스** 표에 한 줄 추가
5. ADR 작성 여부 판단: 정책적 결정이 있으면 `docs/spec/decisions/ADR-NNN.md` 추가

## 주의사항

- **robots.txt 준수** 소스만 사용 (ADR-001)
- **차단 소스(X-###) 크롤링 요청** 시: 거부 + 이유 설명
- **제목 부분 일치로 자동 수집 금지** — 동명이곡/유사 제목 오매칭 위험 (yseng의 `#46`, `#41` 사례)
- **대량 실행 시** 소스별 지연 설정 확인 + 번호를 작게 쪼개서 진행
- 실행 계획(Step 3) **스킵 금지** — 사용자가 명시적으로 "바로 실행"이라 해도, 적용할 소스 목록은 최소 한 줄이라도 제시하고 시작한다.
- xlsx 잠금: 엑셀에서 곡정보.xlsx를 열어둔 상태면 `apply_to_xlsx.py`가 PermissionError로 실패 → 엑셀 닫고 재시도

## 참조

- v2 SSoT 정책: [docs/spec/schema.md](../../../docs/spec/schema.md)
- 데이터 흐름: 곡정보.xlsx → songs.json → songs_index.json (`scripts/rebuild.py`)
- 레거시 v1 모듈: `scripts/crawler/_merge.py` (deprecated, 호출 금지)
