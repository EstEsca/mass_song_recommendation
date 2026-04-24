"""
/clean-lyrics 스킬 실행 스크립트.

가사 본문에서 다음 항목만 정리한다:
  X11: 악보 메타(♩, 템포, 박자, 단독 조표, BOM) 제거 ← 항상 실행 (remove_slashes 전)
  X2:  슬래시 구분자 제거
  X3:  Copyright/코드 심볼/깨진 영문 연속 제거
  X4:  빈 줄 제거
  X7:  영문 잔존 토큰 제거  ← opt-in (영문 원제가 제거될 위험)
  X8:  짧은 절 인접 병합 (마커 필수)

절/후렴 구조(마커 통일·생성·재정렬, 절별 dict/절구조 재생성)는 건드리지 않는다.
본문이 바뀐 곡은 파생 필드(절별/절구조/신뢰도/검증완료)를 리셋한다.
절 구조 재계산은 후속 /structure-lyrics의 몫.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from _lyrics_cleanup import (
    drop_blank_lines,
    merge_short_verses,
    remove_contamination,
    remove_slashes,
    strip_english_residue,
    strip_music_notation,
)

ROOT = Path(__file__).parent.parent
SONGS_JSON = ROOT / "data" / "songs.json"


def clean_song(song: dict, apply_x7: bool = False) -> tuple[bool, list[str]]:
    """한 곡 cleanup. (수정됨 여부, 교정 로그) 반환.
    apply_x7=True면 영문 잔존 제거(마커 유무 무관)도 수행."""
    lyrics = song.get("가사", {})
    if not lyrics.get("확보여부") or not lyrics.get("본문"):
        return False, []

    text = lyrics["본문"]
    original = text
    log: list[str] = []

    # X11: 악보 메타 제거 (remove_slashes보다 먼저!)
    new_text, meta = strip_music_notation(text)
    if meta:
        log.append(f"X11: 악보 메타 {meta}개 제거")
        text = new_text

    new_text = remove_slashes(text)
    if new_text != text:
        log.append("X2: 슬래시 제거")
        text = new_text

    new_text, rm = remove_contamination(text)
    if rm:
        log.extend(f"X3: {r}" for r in rm)
        text = new_text

    new_text = drop_blank_lines(text)
    if new_text != text:
        log.append("X4: 빈 줄 제거")
        text = new_text

    if apply_x7:
        new_text, removed = strip_english_residue(text)
        if removed:
            log.append(f"X7: 영문 토큰 {removed}개 제거")
            text = new_text

    new_text, merged = merge_short_verses(text, min_len=10)
    if merged:
        log.append(f"X8: 짧은 절 {merged}건 병합")
        text = new_text

    if text == original and not log:
        return False, []

    lyrics["본문"] = text
    # 본문이 바뀌면 파생 필드는 stale — 리셋 (structure-lyrics가 재계산)
    lyrics["절별"] = None
    lyrics["절구조"] = None
    song["신뢰도"] = {
        "점수": None,
        "등급": None,
        "세부지표": {},
        "실패원인": [],
    }
    song.pop("검증완료", None)
    return True, log


def parse_targets(raw: str, all_nums: list[int]) -> list[int]:
    raw = raw.strip()
    if raw in ("전부", "all"):
        return all_nums
    if "-" in raw or "~" in raw:
        raw = raw.replace("~", "-")
        a, b = raw.split("-", 1)
        return list(range(int(a), int(b) + 1))
    if "," in raw:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    return [int(raw)]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="가사 본문 정리 (절 구조 불변)"
    )
    parser.add_argument("target", nargs="?", default="전부",
                        help="곡 번호/범위/'전부' (예: 5, 1-100, 32,38,50)")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--yes-x7", action="store_true",
                   help="X7(영문 잔존 제거)을 프롬프트 없이 적용. 영문 원제가 지워질 수 있음")
    g.add_argument("--no-x7", action="store_true",
                   help="X7을 프롬프트 없이 건너뜀 (기본 안전)")
    args = parser.parse_args()

    # X7 opt-in 결정
    if args.yes_x7:
        apply_x7 = True
    elif args.no_x7:
        apply_x7 = False
    else:
        # 인터랙티브 프롬프트 — X7 설명
        bar = "━" * 60
        msg = f"""
{bar}
X7: 영문 잔존 토큰 강제 제거 (선택 단계)
{bar}
[동작]
  본문을 공백으로 쪼갠 각 토큰을 검사해, 아래 조건 중 하나를 만족하는 토큰만
  남기고 나머지는 전부 삭제합니다:
    • 한글 글자가 1개 이상 포함된 토큰
    • 순수 숫자·구두점만으로 이루어진 토큰 (0-9, . , ! ? ; :)

  마커([1절], [후렴] 등)는 보존되며, 줄 단위는 유지됩니다.

[효과 — 대개 원하는 결과]
  • OCR·크롤링 잔재에서 가사에 끼어든 코드/영문 조각 정리
    "1절 Am G7 주님을 찬양" → "1절 주님을 찬양"
  • X11이 놓친 미세 잔재 (단독 로마자, 섞여 들어간 기호 조각) 제거

[부작용 — 실제 영어·라틴 가사가 본문에 있으면 함께 지워짐]
  • "Oh Father"          → ""  (전부 삭제)
  • "Nada te turbe"      → ""  (전부 삭제)
  • "Bless the Lord"     → ""  (전부 삭제)
  • "Kumbaya my Lord"    → ""  (my·Lord 모두 영문으로 판정)

[언제 적용하면 좋은가]
  • 본문이 거의 전부 한글인 곡 (대부분의 청소년청년성가집 곡)
  • PDF OCR 출처로 화성·영문 조각이 남은 곡

[언제 적용하지 말 것]
  • 떼제(Taizé), Kumbaya, Nada te turbe 등 원어 찬양 — 본문 자체가 라틴/영어
  • 영문 원제가 본문에 의도적으로 병기된 경우
{bar}
"""
        print(msg, file=sys.stderr)
        ans = input("X7을 적용할까요? [y/N]: ").strip().lower()
        apply_x7 = ans in ("y", "yes")
        print(f"→ X7 {'적용' if apply_x7 else '건너뜀'}", file=sys.stderr)

    with SONGS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)
    songs = data["songs"]
    all_nums = sorted(int(k) for k in songs.keys())
    targets = parse_targets(args.target, all_nums)

    total = 0
    modified_count = 0
    fix_types: Counter[str] = Counter()
    detail: list[tuple[int, str, list[str]]] = []

    for num in targets:
        if str(num) not in songs:
            continue
        total += 1
        song = songs[str(num)]
        modified, log = clean_song(song, apply_x7=apply_x7)
        if modified:
            modified_count += 1
            detail.append((num, song.get("제목", ""), log))
            for entry in log:
                fix_types[entry.split(":")[0]] += 1

    data["metadata"]["updated"] = date.today().isoformat()
    data["metadata"]["lyrics_count"] = sum(
        1 for s in songs.values() if s["가사"].get("확보여부")
    )

    with SONGS_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("  clean-lyrics 결과")
    print("=" * 60)
    print(f"  대상:   {total}곡")
    print(f"  교정:   {modified_count}곡")
    print(f"  미변경: {total - modified_count}곡")
    print(f"  X7:     {'적용' if apply_x7 else '건너뜀'}")

    if fix_types:
        print("\n  교정 유형별:")
        for ft, cnt in fix_types.most_common():
            print(f"    {ft}: {cnt}건")


if __name__ == "__main__":
    main()
