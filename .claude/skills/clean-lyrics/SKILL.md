---
name: clean-lyrics
description: songs.json의 가사 본문에서 오염(Copyright·화성 기호·깨진 영문), 빈 줄, 짧은 절을 정리한다. 절/후렴 구조는 건드리지 않음. "가사 오염 제거", "본문 정리", "clean 가사" 등에 사용.
argument-hint: "곡 번호/범위 또는 전부"
---

# 가사 본문 정리 스킬

`가사.본문`에서 **정리 성격의 교정만** 수행한다. 절/후렴 구조는 보존한다.

## 교정 항목

| ID | 교정 | 구현 함수 | 비고 |
|----|------|----------|------|
| X11 | 악보 메타 제거 (`♩`, `♪`, `=템포`, `4/4`, 단독 조표 `G`/`F#`, BOM·제로폭 문자) | `strip_music_notation` | 항상 실행, 순서상 최우선 (remove_slashes 전) |
| X2 | 슬래시 구분자 제거 (` / ` → 공백) | `remove_slashes` | 항상 실행 |
| X3 | Copyright 줄/부분 제거, 코드 심볼(CHORD_RE) 제거, 깨진 영문 연속 제거 | `remove_contamination` | 항상 실행 |
| X4 | 빈 줄 제거 | `drop_blank_lines` | 항상 실행 |
| X7 | 영문 잔존 토큰 제거 (한글/구두점/숫자 외, 마커 유무 무관) | `strip_english_residue` | **opt-in** — 실행 시 사용자 확인 |
| X8 | 10자 미만 절을 인접 절에 병합 | `merge_short_verses` | 항상 실행 (마커 있는 절에만 작용) |

### X7의 opt-in 이유

X7은 "한글·숫자·구두점 외 토큰"을 모두 삭제한다. 악보 잔재(`G`, `Am`, 코드 조합)를 정리하는 데 효과적이지만
**영문 원제·원가사도 함께 지워진다**. 예:
- `Oh Father`, `Kumbaya`, `Nada te turbe`, `Bless the Lord` 등 라틴·영어 원제가 본문에 포함된 곡

그래서 CLI는 실행 시 y/N 프롬프트를 띄운다. 자동화를 위한 플래그:
- `--yes-x7` : 확인 없이 X7 적용
- `--no-x7`  : 확인 없이 X7 생략 (안전 기본값)

모든 로직은 [scripts/_lyrics_cleanup.py](../../../scripts/_lyrics_cleanup.py)에 집중되어 있고,
[scripts/fix_lyrics_format.py](../../../scripts/fix_lyrics_format.py)(deprecated)도 이 모듈을 재사용한다.

## 하지 않는 일 (의도적 제외)

- 마커 통일(`1)` → `[1절]`, `후렴 :` → `[후렴]`) → `/fix-lyrics-format` (deprecated) 또는 `/structure-lyrics`
- 마커 없는 줄에 강제로 `[N절]` 부여
- 절 번호 재정렬
- 절별 dict / 절구조 재생성
- 절/후렴 경계 추론

이런 작업은 사용자 확인이 필요하거나, 별도 스킬(`/structure-lyrics`, 미구현)의 책임이다.

## 파생 필드 처리

본문이 바뀐 곡에 대해서만 다음을 **null로 초기화**한다 (옛 본문 기준 계산값이라 stale):
- `가사.절별 → null`
- `가사.절구조 → null`
- `신뢰도 → {점수: null, 등급: null, 세부지표: {}, 실패원인: []}`
- `검증완료` 키 삭제

재계산은 후속 스킬이 담당.

## 데이터

- 입력/출력: [data/songs.json](../../../data/songs.json) (in-place)
- 외부 호출 없음 (순수 로컬)

## 실행

```bash
python scripts/clean_lyrics.py 전부             # 495곡 전체 (X7 프롬프트 발생)
python scripts/clean_lyrics.py 30-500 --no-x7   # 범위 + X7 생략
python scripts/clean_lyrics.py 32,38,50 --yes-x7# 복수 + X7 강제 적용
python scripts/clean_lyrics.py 5                # 단일
```

결과 보고: 교정 건수 + 유형별 집계 (`X11: N건`, `X2: N건`, `X3: M건`, …) + X7 적용 여부.

### 스킬 호출 시 권장 흐름

1. 사용자의 요청을 받는다
2. X7 적용 여부를 사용자에게 명시적으로 확인 (CLI 인터랙티브 프롬프트에 의존하지 말고)
3. 결과에 따라 `--yes-x7` 또는 `--no-x7`을 붙여 CLI 실행

## 실행 흐름

1. `scripts/clean_lyrics.py` 호출 (argument 파싱)
2. songs.json 로드 → 대상 곡 반복 → `clean_song(song)` 호출
3. 본문 변경이 있으면 파생 필드 리셋
4. songs.json 저장 (`metadata.updated` / `lyrics_count` 갱신)
5. 요약 출력

## 파이프라인 권장 순서

```
crawl-lyrics / extract-sheet-lyrics  →  clean-lyrics  →  structure-lyrics  →  validate-lyrics-format
        (본문 확보)                        (오염 정리)        (절 구조)          (스펙 검증)
```

## 후속 스킬

- `/structure-lyrics` — 리셋된 `가사.절별`/`가사.절구조`를 본문에서 재추출 (현재 DRAFT)
- `/validate-lyrics-format` — 정리 후 스펙 준수 재검증

## 원칙

- **본문 정리 전용** — 절 구조는 건드리지 않는다
- songs.json 직접 수정 (재실행 안전)
- 수정 전후는 `git diff data/songs.json`로 확인 가능
- 외부 호출 없음
