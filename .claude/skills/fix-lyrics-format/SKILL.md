---
name: fix-lyrics-format
description: "[DEPRECATED — v2 미대응] 본문 정리는 /clean-lyrics, 절 구성 추론은 /structure-lyrics 사용 권장. 기존 호환용으로만 유지."
argument-hint: "곡 번호/범위 또는 전부"
---

# 가사 형식 교정 스킬 (DEPRECATED)

> ⚠️ **DEPRECATED (2026-04-24~) + v2 스키마 미대응 (2026-04-25~)**
>
> 이 스킬은 두 가지 이유로 더 이상 호출하지 말 것:
>
> 1. **책임 분리**: 본문 정리 → [`/clean-lyrics`](../clean-lyrics/SKILL.md), 절 구성 추론 → [`/structure-lyrics`](../structure-lyrics/SKILL.md)로 이미 분리됨
> 2. **v2 스키마 비호환**: 교정 항목 X5(절구조 재생성)·X6(절별 dict 재생성)이 의존하는 `가사.절구조`·`가사.절별` 필드는 v2에서 폐기됨. 본 스크립트(`scripts/fix_lyrics_format.py`)는 v2에서 실행 시 KeyError 또는 잘못된 결과를 낸다.
>
> 신규 자동화는 `/clean-lyrics` + `/structure-lyrics`를 순서대로 사용하라.
> 본 스킬과 `scripts/fix_lyrics_format.py`는 호환성 유지용 표면만 남기며, **실행은 금지**.

songs.json의 가사를 `docs/spec/lyrics_format.md` 스펙에 맞게 자동 교정한다.
**validate-lyrics-format의 위반 사항을 한 번에 수정하는 레거시 역할.**

공용 정리 로직은 [scripts/_lyrics_cleanup.py](../../../scripts/_lyrics_cleanup.py)로 이관되어
`/clean-lyrics`와 함수를 공유한다. 이 스킬의 스크립트는 해당 모듈에서 import로 사용한다.

## 교정 항목

| ID | 교정 | 동작 |
|----|------|------|
| X1 | 절 마커 통일 | `1)` `2)` → `[1절]` `[2절]`, `후렴 :` → `[후렴]` |
| X2 | 슬래시 제거 | 절 내부 ` / ` → 공백 |
| X3 | 오염 제거 | Copyright, 코드 심볼, 깨진 영문 제거 |
| X4 | 빈 줄 제거 | 절 사이 불필요 빈 줄 제거 |
| X5 | 절구조 재생성 | 실제 절별 키 목록에서 재계산 |
| X6 | 절별 dict 재생성 | 본문에서 절별 dict 파싱 |

## 데이터

- 입력/출력: `data/songs.json` (직접 수정)
- 참조: `docs/spec/lyrics_format.md`

## 실행

```bash
python3 scripts/fix_lyrics_format.py 전부
python3 scripts/fix_lyrics_format.py 1-100
python3 scripts/fix_lyrics_format.py 5
```

## 원칙

- songs.json을 **직접 수정**한다 (validate와 다름)
- 수정 건수를 보고한다
- 수정 전후 비교 가능 (git diff)
- 외부 호출 없음 (순수 로컬)
