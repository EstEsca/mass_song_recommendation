---
name: clean-lyrics
description: data/source/곡정보.xlsx의 가사 시트에서 오염(Copyright·화성 기호·깨진 영문), 빈 줄, 짧은 절을 정리한다. 절/후렴 구조는 건드리지 않음. "가사 오염 제거", "본문 정리", "clean 가사" 등에 사용.
argument-hint: "곡 번호/범위 또는 전부"
---

# 가사 본문 정리 스킬 (v2)

`data/source/곡정보.xlsx`의 **`가사` 시트**에서 본문(B열)을 정리한다. 절/후렴 구조는 보존한다.

## 데이터 흐름 (v2 SSoT 모델)

- **편집 대상**: `data/source/곡정보.xlsx`의 `가사` 시트 (직접 갱신)
- **건드리지 않음**: `data/songs.json`, `data/songs_index.json` (파생물 — 다음 빌드에 자동 갱신)
- **변경 후 사용자 책임**: `python scripts/rebuild.py` 실행 (xlsx → JSON 재빌드)

xlsx가 사용자에 의해 엑셀로 열려 있으면 잠금으로 저장 실패 → "엑셀을 닫아주세요" 안내 후 재시도.

## 교정 항목

| ID | 교정 | 구현 함수 | 비고 |
|----|------|----------|------|
| X11 | 악보 메타 제거 (`♩`, `♪`, `=템포`, `4/4`, 단독 조표, BOM·제로폭) | `strip_music_notation` | 항상 실행, X2보다 먼저 |
| X2 | 슬래시 구분자 제거 (` / ` → 공백) | `remove_slashes` | 항상 실행 |
| X3 | Copyright 줄/부분 제거, 코드 심볼 제거, 깨진 영문 연속 제거 | `remove_contamination` | 항상 실행 |
| X4 | 빈 줄 제거 | `drop_blank_lines` | 항상 실행 |
| X7 | 영문 잔존 토큰 제거 (한글/구두점/숫자 외) | `strip_english_residue` | **opt-in** — 실행 시 사용자 확인 |
| X8 | 10자 미만 절을 인접 절에 병합 | `merge_short_verses` | 항상 실행 (마커 있는 절만) |

### X7의 opt-in 이유

X7은 한글/숫자/구두점 외 토큰을 모두 삭제한다. 악보 잔재(`G`, `Am` 등) 정리에 효과적이지만 **영문 원제·원가사도 함께 지워진다**:
- `Oh Father`, `Kumbaya`, `Nada te turbe`, `Bless the Lord` 등

CLI 실행 시 y/N 프롬프트. 자동화용 플래그:
- `--yes-x7` : 확인 없이 적용
- `--no-x7`  : 확인 없이 생략 (안전 기본값)

모든 정리 로직은 [scripts/_lyrics_cleanup.py](../../../scripts/_lyrics_cleanup.py)의 텍스트 in/out 함수에 집중되어 있다.

## 하지 않는 일 (의도적 제외)

- 마커 통일(`1)` → `[1절]`, `후렴 :` → `[후렴]`) → `/structure-lyrics`
- 마커 없는 줄에 강제로 `[N절]` 부여 → `/structure-lyrics`
- 절 번호 재정렬 → `/structure-lyrics`
- 절/후렴 경계 추론 → `/structure-lyrics`

이런 작업은 별도 스킬의 책임이다.

## 실행

```bash
python scripts/clean_lyrics.py 전부             # 495곡 전체 (X7 프롬프트 발생)
python scripts/clean_lyrics.py 30-500 --no-x7   # 범위 + X7 생략
python scripts/clean_lyrics.py 32,38,50 --yes-x7# 복수 + X7 강제 적용
python scripts/clean_lyrics.py 5                # 단일
python scripts/clean_lyrics.py 5 --dry-run      # 저장 없이 결과만 확인
```

결과 보고: 교정 건수 + 유형별 집계(X11, X2, X3, …) + X7 적용 여부 + 후속 rebuild 안내.

### 스킬 호출 시 권장 흐름

1. 사용자의 요청을 받는다
2. xlsx가 엑셀에서 열려 있는지 사전 안내
3. X7 적용 여부를 사용자에게 명시적으로 확인 (CLI 인터랙티브 프롬프트에 의존하지 말고)
4. `--yes-x7` 또는 `--no-x7`을 붙여 CLI 실행
5. 변경이 있었다면 `python scripts/rebuild.py` 실행 권유

## 실행 흐름

1. `scripts/clean_lyrics.py` 호출 (argument 파싱 + X7 결정)
2. `data/source/곡정보.xlsx` 로드 (잠금 시 즉시 실패)
3. `가사` 시트 헤더 검증(`번호`·`가사`)
4. 대상 행 반복 → `clean_text()` 호출
5. 변경된 행만 셀 갱신 (wrap 서식 유지)
6. 변경이 1건 이상이면 xlsx 저장 (atomic, openpyxl)
7. 요약 출력 + rebuild 안내

## 파이프라인 권장 순서

```
crawl-lyrics  →  clean-lyrics  →  structure-lyrics  →  rebuild
 (본문 확보)     (오염 정리)      (절 구조 마커)     (JSON 재빌드)
```

## 후속 스킬

- `/structure-lyrics` — 정리된 본문에서 절/후렴 마커 부여 (DRAFT)
- `python scripts/rebuild.py` — xlsx 변경을 songs.json·songs_index.json에 반영

## 원칙

- **xlsx만 수정** — songs.json은 절대 직접 갱신하지 않음 (다음 rebuild에 덮어쓰여짐)
- **본문 정리 전용** — 절 구조는 건드리지 않는다
- 외부 호출 없음 (순수 로컬)
- 변경 추적: `git diff data/source/곡정보.xlsx` (textconv가 셀 단위 표시)
