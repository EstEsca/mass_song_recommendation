# ADR-003: songs.json을 중앙 데이터 구조로 채택

**일자:** 2026-04-16
**상태:** 채택

## 맥락

프로젝트의 가사/색인 데이터가 여러 파일에 분산되어 있음:
- `data/raw/곡목록.csv` — 기본 메타
- `data/raw/song_list_index_sample.xlsx` — 색인 (사용자 편집)
- `scripts/crawler/data/maria_sungga.jsonl` — 크롤링 결과
- `inbox/가사.json`, `inbox/가사_sample.json` — 이전 실험 결과

각 스킬이 서로 다른 파일을 읽고 쓰면서 일관성 유지 어려움. CONSIDERATIONS.md의 C-01 "데이터 스키마 고정"이 이 문제를 제기했음.

## 결정

**`data/songs.json`을 중앙 운영 데이터로 채택.**

- 모든 스킬의 입출력 기준
- 스키마는 `docs/spec/schema.md`에 v1.0으로 명시
- 495곡 전체를 포함, 가사 확보 여부는 `가사.확보여부` 필드로 관리
- 기존 파일들은 **입력 소스**로만 역할 유지:
  - `data/raw/곡목록.csv` → 기본 메타 공급
  - `data/raw/song_list_index_sample.xlsx` → 색인 공급
  - `scripts/crawler/data/maria_sungga.jsonl` → 크롤링 가사 공급

이력 기록 안 함 (git 커밋으로만 추적).

## 업데이트 (2026-04-24)

**songs.json은 이제 "단일 진리 저장소(source of truth)"**이며,
원료 파일(곡목록.csv, 색인 xlsx)에서 **매번 재생성하지 않는다**.

- `scripts/build_songs_json.py` (전체 덮어쓰기형 빌더) **제거**
- 이유: 재빌드가 `사용자수정시각`, `신뢰도`, `PDF추출(v3)` 출처 등
  재구성 불가능한 파생 필드를 덮어써 수개월치 편집을 날릴 위험
- 신규 접근: 각 크롤러가 `scripts/crawler/_merge.py` 헬퍼로
  **in-place 부분 병합** 수행. 사용자 수정과 타 소스 우선분은 기본 보호
- 최초 부트스트랩은 이미 완료됨 (commit a41aeab). 원료 파일은 참고용으로 보존

## 대안

1. **기존 여러 파일 유지** — 기각 (스킬 간 일관성 유지 어려움)
2. **SQLite 등 DB 도입** — 기각 (과한 의존성, JSON으로 충분)
3. **곡별 개별 파일** — 기각 (파일 수 폭증)
4. **곡 객체 내 이력 배열** — 기각 (파일 비대)
5. **별도 이력 파일(append-only)** — 기각 (git 커밋으로 충분)

## 결과

**긍정:**
- 모든 스킬이 단일 데이터 구조 공유
- 스키마 버전 관리 명확화
- Python/JavaScript 등에서 바로 로드 가능
- git diff로 변경 추적 용이

**부정:**
- 수작업 편집 시 스키마 위반 가능성 (→ validate-lyrics 스킬로 감지)
- 원료 파일에서의 재빌드 경로 없음 — songs.json 손상 시 git 히스토리/스냅샷에서 복구

## 참조

- [docs/spec/schema.md](../schema.md)
- [scripts/crawler/_merge.py](../../../scripts/crawler/_merge.py) — 크롤러 공용 병합 헬퍼
- [.claude/skills/crawl-lyrics/SKILL.md](../../../.claude/skills/crawl-lyrics/SKILL.md)
- [CONSIDERATIONS.md](../../tracker/CONSIDERATIONS.md) C-01
