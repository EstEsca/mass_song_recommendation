"""
가사 형식 교정 스크립트 (fix-lyrics-format).

⚠️  DEPRECATED — 본 스크립트는 본문 정리와 절 구성 재조립이 섞여 있어 둘로 쪼개졌다.
   - 본문 정리(X2/X3/X4/X7/X8)  → scripts/clean_lyrics.py (/clean-lyrics)
   - 절 구성 추론              → scripts/structure_lyrics.py (/structure-lyrics, 미구현)
   호환성을 위해 이 파일과 CLI는 유지하지만, 신규 자동화는 위 두 스킬을 사용하라.

songs.json의 가사를 lyrics_format.md 스펙에 맞게 교정:
- X1: 절 마커 통일 (1) → [1절], 후렴 : → [후렴])
- X2: 슬래시 제거 (절 내부 / → 공백)                  [_lyrics_cleanup]
- X3: 오염 제거 (Copyright, 코드 심볼, 깨진 영문)      [_lyrics_cleanup]
- X4: 빈 줄 제거
- X5: 절구조 재생성
- X6: 절별 dict 재생성
- X7: 영문 잔존 제거                                    [_lyrics_cleanup]
- X8: 짧은 절 병합                                      [_lyrics_cleanup]
- X9: 절 번호 재정렬
- X10: 마커 없는 줄 강제 마커
"""

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import date

from _lyrics_cleanup import (
    CHORD_RE,  # noqa: F401  (재노출 호환)
    COPYRIGHT_KW,  # noqa: F401
    merge_short_verses,
    remove_contamination,
    remove_slashes,
    strip_english_residue,
)

ROOT = Path(__file__).parent.parent
SONGS_JSON = ROOT / "data" / "songs.json"


def fix_maria_markers(text: str) -> str:
    """maria 출처의 마커를 스펙 형식으로 변환."""
    # "1) 가사..." → "[1절] 가사..."
    text = re.sub(r"^(\d+)\)\s*", lambda m: f"[{m.group(1)}절] ", text, flags=re.MULTILINE)
    # "후렴 : 가사..." → "[후렴] 가사..."
    text = re.sub(r"^후렴\s*:\s*", "[후렴] ", text, flags=re.MULTILINE)
    return text


def fix_pdf_markers(text: str) -> str:
    """PDF 추출의 마커를 정리."""
    lines = text.split("\n")
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # [N절] 이 단독 줄이고 다음 줄에 본문이 있으면 합치기
        marker_match = re.match(r"^\[(\d+절|후렴|브릿지|코다|전후렴|후후렴)\]$", line)
        if marker_match and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line:
                merged.append(f"[{marker_match.group(1)}] {next_line}")
                i += 2
                continue
        # "N. " 으로 시작하는 경우 (절 마커)
        num_match = re.match(r"^(\d+)\.\s*(.+)", line)
        if num_match:
            merged.append(f"[{num_match.group(1)}절] {num_match.group(2)}")
            i += 1
            continue
        if line:
            merged.append(line)
        i += 1
    return "\n".join(merged)


def ensure_markers(text: str) -> str:
    """마커가 없는 줄에 마커 추가 (통절 등)."""
    lines = text.split("\n")
    result = []
    has_any_marker = any(re.match(r"^\[", l) for l in lines if l.strip())

    if not has_any_marker and lines:
        # 마커가 전혀 없으면 → 통절로 [1절] 추가
        combined = " ".join(l.strip() for l in lines if l.strip())
        result.append(f"[1절] {combined}")
    else:
        for line in lines:
            if line.strip():
                result.append(line)
    return "\n".join(result)


def rebuild_verse_dict(text: str) -> dict:
    """본문에서 절별 dict 재생성."""
    verses = {}
    for line in text.split("\n"):
        m = re.match(r"^\[([^\]]+)\]\s*(.*)", line)
        if m:
            key = m.group(1)
            content = m.group(2).strip()
            if content:
                verses[key] = content
    return verses if verses else None


def renumber_verses(text: str) -> tuple[str, int]:
    """X9: 절 번호를 순차로 재정렬. 후렴/브릿지 등은 그대로."""
    lines = text.split("\n")
    renumbered = []
    changes = 0
    verse_idx = 0
    for line in lines:
        m = re.match(r"^\[(\d+)절\](.*)", line)
        if m:
            verse_idx += 1
            new_marker = f"[{verse_idx}절]"
            original_marker = f"[{m.group(1)}절]"
            if new_marker != original_marker:
                changes += 1
            renumbered.append(new_marker + m.group(2))
        else:
            renumbered.append(line)
    return "\n".join(renumbered), changes


def force_add_markers(text: str) -> tuple[str, int]:
    """X10: 마커 없는 줄에 강제로 마커 추가."""
    lines = text.split("\n")
    result = []
    added = 0
    verse_num = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\[[^\]]+\]", stripped):
            m = re.match(r"^\[(\d+)절\]", stripped)
            if m:
                verse_num = max(verse_num, int(m.group(1)))
            result.append(stripped)
        else:
            # 마커 없는 줄: 다음 절 번호 부여
            verse_num += 1
            result.append(f"[{verse_num}절] {stripped}")
            added += 1
    return "\n".join(result), added


def rebuild_structure(verses: dict | None) -> str:
    """절별 dict에서 절구조 문자열 재생성."""
    if not verses:
        return "통절"
    keys = list(verses.keys())
    if len(keys) == 1 and keys[0] == "1절":
        return "통절"
    parts = []
    for k in keys:
        m = re.match(r"(\d+)절", k)
        if m:
            parts.append(m.group(1))
        else:
            parts.append(k)
    return "-".join(parts)


def fix_song(song: dict) -> tuple[bool, list[str]]:
    """한 곡의 가사를 교정. (수정됨 여부, 교정 로그) 반환."""
    lyrics = song["가사"]
    if not lyrics.get("확보여부") or not lyrics.get("본문"):
        return False, []

    text = lyrics["본문"]
    source = lyrics.get("출처", "")
    log = []

    # X1: 마커 통일
    if source == "maria":
        new_text = fix_maria_markers(text)
    else:
        new_text = fix_pdf_markers(text)
    if new_text != text:
        log.append("X1: 절 마커 변환")
        text = new_text

    # X2: 슬래시 제거
    new_text = remove_slashes(text)
    if new_text != text:
        log.append("X2: 슬래시 제거")
        text = new_text

    # X3: 오염 제거
    new_text, removal_log = remove_contamination(text)
    if removal_log:
        log.extend([f"X3: {r}" for r in removal_log])
        text = new_text

    # X4: 빈 줄 제거
    lines = [l for l in text.split("\n") if l.strip()]
    new_text = "\n".join(lines)
    if new_text != text:
        log.append("X4: 빈 줄 제거")
        text = new_text

    # 마커 없는 줄 처리
    text = ensure_markers(text)

    # X10: 마커 없는 줄에 강제 마커 추가 (ensure_markers 이후 남은 것)
    new_text, added = force_add_markers(text)
    if added:
        log.append(f"X10: 마커 {added}개 강제 추가")
        text = new_text

    # X7: 영문 잔존 강제 제거
    new_text, removed = strip_english_residue(text)
    if removed:
        log.append(f"X7: 영문 토큰 {removed}개 제거")
        text = new_text

    # X8: 짧은 절 병합 (10자 미만)
    new_text, merged = merge_short_verses(text, min_len=10)
    if merged:
        log.append(f"X8: 짧은 절 {merged}건 병합")
        text = new_text

    # X9: 절 번호 순차 재정렬
    new_text, changes = renumber_verses(text)
    if changes:
        log.append(f"X9: 절 번호 {changes}개 재정렬")
        text = new_text

    # X6: 절별 dict 재생성
    verses = rebuild_verse_dict(text)

    # X5: 절구조 재생성
    structure = rebuild_structure(verses)

    # 적용
    modified = bool(log) or lyrics["본문"] != text
    if modified:
        lyrics["본문"] = text
        lyrics["절별"] = verses
        lyrics["절구조"] = structure

    return modified, log


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print(
        "[경고] fix_lyrics_format.py는 deprecated입니다. "
        "본문 정리만 필요하면 scripts/clean_lyrics.py(/clean-lyrics)를 사용하세요.",
        file=sys.stderr,
    )
    parser = argparse.ArgumentParser(description="가사 형식 교정 (deprecated)")
    parser.add_argument("target", nargs="?", default="전부")
    args = parser.parse_args()

    with SONGS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)

    songs = data["songs"]
    all_nums = sorted(int(k) for k in songs.keys())

    target = args.target.strip()
    if target in ("전부", "all"):
        targets = all_nums
    elif "-" in target or "~" in target:
        target = target.replace("~", "-")
        a, b = target.split("-", 1)
        targets = list(range(int(a), int(b) + 1))
    elif "," in target:
        targets = [int(x.strip()) for x in target.split(",")]
    else:
        targets = [int(target)]

    total = 0
    modified_count = 0
    all_logs = []

    for num in targets:
        if str(num) not in songs:
            continue
        total += 1
        song = songs[str(num)]
        modified, log = fix_song(song)
        if modified:
            modified_count += 1
            all_logs.append((num, song["제목"], log))

    # 저장
    data["metadata"]["updated"] = date.today().isoformat()
    lyrics_count = sum(1 for s in songs.values() if s["가사"]["확보여부"])
    data["metadata"]["lyrics_count"] = lyrics_count

    with SONGS_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 보고
    print(f"\n{'='*60}")
    print(f"  fix-lyrics-format 결과")
    print(f"{'='*60}")
    print(f"  대상: {total}곡")
    print(f"  교정: {modified_count}곡")
    print(f"  미변경: {total - modified_count}곡")

    from collections import Counter
    fix_types = Counter()
    for _, _, log in all_logs:
        for entry in log:
            ftype = entry.split(":")[0]
            fix_types[ftype] += 1

    if fix_types:
        print(f"\n  교정 유형별:")
        for ft, cnt in fix_types.most_common():
            print(f"    {ft}: {cnt}건")


if __name__ == "__main__":
    main()
