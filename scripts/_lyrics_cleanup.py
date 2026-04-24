"""
가사 본문 정리 공용 유틸.

본문 정리 전용. **절/후렴 구조는 건드리지 않는다.**
(마커 통일·생성·재정렬, 절별 dict/절구조 재생성은 호출부의 책임.)

제공 함수:
  - remove_slashes       : X2 슬래시 구분자 → 공백
  - remove_contamination : X3 Copyright·코드 심볼·깨진 영문 연속 제거
  - drop_blank_lines     : X4 빈 줄 제거
  - strip_english_residue: X7 영문 잔존 토큰 제거 (마커 유무와 무관)
  - merge_short_verses   : X8 짧은 절을 인접 절에 병합 (마커 필수)
  - strip_music_notation : X11 악보 메타(♩, 템포, 박자, 조표 단독) 제거

호출 순서 권장: strip_music_notation → remove_slashes → remove_contamination
 → drop_blank_lines → (선택) strip_english_residue → merge_short_verses
 (strip_music_notation은 remove_slashes보다 먼저 — 박자 `4/4`가 `4 4`로 쪼개지기 전에 잡아야 함)

사용처:
  - scripts/clean_lyrics.py   (/clean-lyrics 스킬)
  - scripts/fix_lyrics_format.py  (deprecated, 이 모듈을 import)
"""

from __future__ import annotations

import re

CHORD_RE = re.compile(
    r"^[A-G][#b♯♭]?(m|M|maj|min|sus|dim|aug|add)?(2|4|5|6|7|9|11|13)?(sus[0-9]?)?(/[A-G][#b♯♭]?)?$"
)

COPYRIGHT_KW = [
    "Copyright", "All rights reserved", "Used by permission",
    "Administered", "Allrightsreserved", "Usedbyper",
    "Holymusic", "Holymuse", "CopyCare", "Copylght",
]


def remove_slashes(text: str) -> str:
    """X2: 절 내부 슬래시 구분자를 공백으로."""
    return re.sub(r"\s*/\s*", " ", text)


def remove_contamination(text: str) -> tuple[str, list[str]]:
    """X3: Copyright, 코드 심볼, 깨진 영문 연속 제거. 제거 로그도 반환."""
    removed = []
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        # Copyright 줄 제거
        has_copyright = False
        for kw in COPYRIGHT_KW:
            if kw.lower() in line.lower():
                has_copyright = True
                break
        if has_copyright:
            for kw in COPYRIGHT_KW:
                idx = line.lower().find(kw.lower())
                if idx >= 0:
                    line = line[:idx].strip()
                    break
            if line:
                removed.append("Copyright 부분 제거")
            else:
                removed.append("Copyright 줄 전체 제거")
                continue

        # 코드 심볼 제거
        tokens = line.split()
        clean_tokens = []
        chord_removed = 0
        for token in tokens:
            clean_t = token.strip(".,;:!?")
            if CHORD_RE.match(clean_t) and len(clean_t) <= 6:
                chord_removed += 1
            else:
                clean_tokens.append(token)
        if chord_removed > 0:
            removed.append(f"코드 심볼 {chord_removed}개 제거")
            line = " ".join(clean_tokens)

        # 깨진 영문 연속 제거 (한글 비율 매우 낮은 토큰이 2개 이상 연속)
        tokens = line.split()
        final_tokens = []
        broken_streak = []
        for token in tokens:
            has_korean = bool(re.search(r"[가-힣]", token))
            is_broken = not has_korean and len(token) > 3 and re.search(r"[A-Za-z0-9▇]", token)
            if is_broken:
                broken_streak.append(token)
            else:
                if len(broken_streak) >= 2:
                    removed.append(f"깨진 영문 {len(broken_streak)}개 제거")
                else:
                    final_tokens.extend(broken_streak)
                broken_streak = []
                final_tokens.append(token)
        if len(broken_streak) >= 2:
            removed.append(f"깨진 영문 {len(broken_streak)}개 제거")
        else:
            final_tokens.extend(broken_streak)

        line = " ".join(final_tokens)
        if line.strip():
            cleaned.append(line.strip())

    return "\n".join(cleaned), removed


def drop_blank_lines(text: str) -> str:
    """X4: 빈 줄 제거."""
    return "\n".join(l for l in text.split("\n") if l.strip())


def strip_english_residue(text: str) -> tuple[str, int]:
    """X7: 영문 잔존 토큰 강제 제거 (한글/구두점/숫자가 아닌 토큰).
    마커가 있으면 마커는 보존하고 뒤 content만 처리; 마커가 없으면 줄 전체를 content로 취급.

    주의: 'Oh Father', 'Kumbaya' 같은 영문 원제/가사도 제거되므로 신중히 사용.
    clean_lyrics CLI는 실행 시 이 단계 적용 여부를 사용자에게 확인한다."""
    lines = text.split("\n")
    cleaned_lines = []
    removed_count = 0
    for line in lines:
        m = re.match(r"^(\[[^\]]+\]\s*)(.*)", line)
        if m:
            marker, content = m.group(1), m.group(2)
        else:
            marker, content = "", line
        tokens = content.split()
        kept = []
        for t in tokens:
            if re.search(r"[가-힣]", t):
                kept.append(t)
            elif re.match(r"^[\d.,!?;:]+$", t):
                kept.append(t)
            else:
                removed_count += 1
        cleaned_lines.append(marker + " ".join(kept))
    return "\n".join(cleaned_lines), removed_count


# X11: 악보 메타 패턴 (remove_slashes 이전에 호출해야 박자 패턴 보존)
_MUSIC_NOTATION_PATTERNS = [
    r"[♩♪♫♬♭♯♮𝄞𝄐𝄑]",            # 음표/조표/쉼표 기호
    r"=\s*\d+",                          # 템포 (=84, = 80, ♩=72)
    r"\b\d+\s*/\s*\d+\b",                # 박자 (4/4, 3/4, 6/8)
    r"(?:^|\s)[A-G][#b♯♭]?(?=\s|$)",     # 조표 단독 토큰 (G, F#, Bb) — 앞뒤 경계 필수
]


def strip_music_notation(text: str) -> tuple[str, int]:
    """X11: 악보 메타(음표·템포·박자·단독 조표) + BOM/제로폭 문자 제거.
    remove_slashes보다 먼저 호출해야 박자 `4/4`가 쪼개지기 전에 잡힌다."""
    removed = 0
    # BOM·제로폭 문자 먼저 (이후 조표 패턴의 경계 판정이 정확해짐)
    # U+FEFF BOM, U+200B ZWSP, U+200C ZWNJ, U+200D ZWJ
    new = re.sub("[﻿​‌‍]", "", text)
    if new != text:
        removed += 1
        text = new
    for pat in _MUSIC_NOTATION_PATTERNS:
        new, n = re.subn(pat, " ", text)
        if n:
            removed += n
            text = new
    # 공백/탭 축소 + 줄 양끝 공백 제거 (줄바꿈 보존)
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(l.strip() for l in text.split("\n"))
    return text, removed


def merge_short_verses(text: str, min_len: int = 10) -> tuple[str, int]:
    """X8: 짧은 절(min_len자 미만)을 인접 절에 병합."""
    lines = text.split("\n")
    result = []
    merged_count = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^\[([^\]]+)\]\s*(.*)", line)
        if not m:
            result.append(line)
            i += 1
            continue
        marker, content = m.group(1), m.group(2).strip()
        # 짧은 절이면 다음 줄과 병합
        if len(content) < min_len and i + 1 < len(lines):
            next_line = lines[i + 1]
            next_m = re.match(r"^\[([^\]]+)\]\s*(.*)", next_line)
            if next_m:
                next_content = next_m.group(2).strip()
                combined = f"[{next_m.group(1)}] {content} {next_content}".strip()
                result.append(combined)
                merged_count += 1
                i += 2
                continue
            else:
                result.append(f"[{marker}] {content} {next_line.strip()}")
                merged_count += 1
                i += 2
                continue
        # 이전 줄에 병합
        if len(content) < min_len and result:
            prev = result[-1]
            prev_m = re.match(r"^\[([^\]]+)\]\s*(.*)", prev)
            if prev_m:
                result[-1] = prev + " " + content
                merged_count += 1
                i += 1
                continue
        result.append(line)
        i += 1

    return "\n".join(result), merged_count
