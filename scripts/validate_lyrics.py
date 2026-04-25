"""
가사 형식 검증 스크립트 (validate-lyrics-format).

docs/spec/lyrics_format.md 기준으로 songs.json의 가사를 검증한다.
검증만 하고 수정하지 않는다.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).parent.parent
SONGS_JSON = ROOT / "data" / "songs.json"

# --- 절 마커 패턴 ---
VALID_MARKERS = re.compile(
    r"^\[(\d+절|후렴|브릿지|코다|전후렴|후후렴)\]\s"
)

# --- 코드 심볼 ---
CHORD_RE = re.compile(
    r"^[A-G][#b♯♭]?(m|M|maj|min|sus|dim|aug|add)?(2|4|5|6|7|9|11|13)?(sus[0-9]?)?(/[A-G][#b♯♭]?)?$"
)

# --- Copyright ---
COPYRIGHT_KW = [
    "Copyright", "All rights reserved", "Used by permission",
    "Administered", "Allrightsreserved", "Usedbyper",
]


def check_f1_marker(lines: list[str]) -> list[str]:
    """F1: 모든 줄이 절 마커로 시작하는가."""
    issues = []
    for i, line in enumerate(lines):
        if not VALID_MARKERS.match(line):
            issues.append(f"F1: 줄 {i+1} — 절 마커 없음: '{line[:40]}...'")
    return issues


def check_f2_order(lines: list[str]) -> list[str]:
    """F2: 절 번호가 순차적인가."""
    nums = []
    for line in lines:
        m = re.match(r"^\[(\d+)절\]", line)
        if m:
            nums.append(int(m.group(1)))
    issues = []
    for i, n in enumerate(nums):
        expected = i + 1
        if n != expected:
            issues.append(f"F2: {expected}절 예상, {n}절 발견")
    return issues


def check_f3_single_line(text: str) -> list[str]:
    """F3: 본문 내 절 사이만 줄바꿈. 절 내부 불필요 줄바꿈 없는가."""
    lines = text.split("\n")
    issues = []
    for i, line in enumerate(lines):
        # 빈 줄 체크
        if not line.strip():
            issues.append(f"F3: 줄 {i+1} — 빈 줄 (절 사이 빈 줄 불필요)")
    return issues


def check_f4_contamination(text: str) -> list[str]:
    """F4: Copyright, 코드 심볼, 깨진 영문 없는가."""
    issues = []
    # Copyright
    for kw in COPYRIGHT_KW:
        if kw.lower() in text.lower():
            issues.append(f"F4: Copyright 문구 감지 — '{kw}'")
            break  # 하나만 보고

    # 코드 심볼 (공백으로 분리된 토큰 중)
    tokens = re.findall(r"[A-Za-z#b♯♭/0-9]+", text)
    chord_count = sum(1 for t in tokens if CHORD_RE.match(t))
    if chord_count >= 3:
        issues.append(f"F4: 코드 심볼 {chord_count}개 감지")

    # 깨진 영문 (한글 아닌 토큰 3개 연속)
    words = text.split()
    streak = 0
    for w in words:
        has_korean = bool(re.search(r"[가-힣]", w))
        if not has_korean and len(w) > 2:
            streak += 1
            if streak >= 3:
                issues.append(f"F4: 깨진 영문/특수문자 연속 감지")
                break
        else:
            streak = 0

    # 슬래시 구분자
    if " / " in text:
        issues.append(f"F4: 슬래시 구분자 감지 (절 내부에 ' / ')")

    return issues


def check_f5_korean_ratio(lines: list[str]) -> list[str]:
    """F5: 각 절의 한글 비율 ≥ 70%."""
    issues = []
    for i, line in enumerate(lines):
        # 마커 제거 후 체크
        content = re.sub(r"^\[[^\]]+\]\s*", "", line)
        if not content:
            continue
        total = len(content)
        korean = len(re.findall(r"[가-힣]", content))
        ratio = korean / max(total, 1)
        if ratio < 0.7:
            issues.append(f"F5: 줄 {i+1} — 한글 비율 {ratio:.0%} (<70%)")
    return issues


def check_f6_min_length(lines: list[str]) -> list[str]:
    """F6: 각 절 ≥ 10자."""
    issues = []
    for i, line in enumerate(lines):
        content = re.sub(r"^\[[^\]]+\]\s*", "", line)
        if len(content.strip()) < 10:
            issues.append(f"F6: 줄 {i+1} — {len(content.strip())}자 (최소 10자)")
    return issues


def check_f7_structure(song: dict) -> list[str]:
    """F7: 절구조 필드와 절별 키 목록이 일치하는가."""
    절구조 = song["가사"].get("절구조")
    절별 = song["가사"].get("절별")
    if not 절구조 or not 절별:
        return []

    # 절구조에서 예상 키 목록
    if 절구조 == "통절":
        expected_keys = {"1절"}
    else:
        expected_keys = set()
        for part in 절구조.split("-"):
            if part.isdigit():
                expected_keys.add(f"{part}절")
            else:
                expected_keys.add(part)

    actual_keys = set(절별.keys())
    issues = []
    if expected_keys != actual_keys:
        issues.append(f"F7: 절구조 '{절구조}' ↔ 실제 키 {sorted(actual_keys)} 불일치")
    return issues


def validate_song(num: int, song: dict) -> dict:
    """한 곡 검증. 결과 dict 반환."""
    title = song["제목"]
    lyrics = song["가사"]

    if not lyrics.get("확보여부") or not lyrics.get("본문"):
        return {"번호": num, "제목": title, "상태": "스킵", "위반": []}

    text = lyrics["본문"]
    lines = [l for l in text.split("\n") if l.strip()]

    all_issues = []
    all_issues.extend(check_f1_marker(lines))
    all_issues.extend(check_f2_order(lines))
    all_issues.extend(check_f3_single_line(text))
    all_issues.extend(check_f4_contamination(text))
    all_issues.extend(check_f5_korean_ratio(lines))
    all_issues.extend(check_f6_min_length(lines))
    all_issues.extend(check_f7_structure(song))

    return {
        "번호": num,
        "제목": title,
        "상태": "통과" if not all_issues else "위반",
        "위반": all_issues,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="가사 형식 검증 (수정 안 함)")
    parser.add_argument("target", nargs="?", default="전부",
                        help="곡 번호/범위/전부 (예: 5, 1-10, 전부)")
    parser.add_argument("--detail", action="store_true",
                        help="곡별 상세 위반 표시")
    args = parser.parse_args()

    with SONGS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)

    songs = data["songs"]
    all_nums = sorted(int(k) for k in songs.keys())

    # 대상 파싱
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

    # 검증 실행
    results = []
    for num in targets:
        if str(num) not in songs:
            continue
        r = validate_song(num, songs[str(num)])
        results.append(r)

    # 통계
    passed = sum(1 for r in results if r["상태"] == "통과")
    failed = sum(1 for r in results if r["상태"] == "위반")
    skipped = sum(1 for r in results if r["상태"] == "스킵")

    violation_types = Counter()
    for r in results:
        for issue in r["위반"]:
            vtype = issue.split(":")[0]
            violation_types[vtype] += 1

    # 출력
    print(f"\n{'='*60}")
    print(f"  validate-lyrics-format 결과")
    print(f"{'='*60}")
    print(f"  대상: {len(results)}곡 (스킵: {skipped}곡)")
    print(f"  통과: {passed}곡 ✅")
    print(f"  위반: {failed}곡 ⚠️")
    print()
    if violation_types:
        print("  위반 유형별:")
        labels = {
            "F1": "절 마커 형식",
            "F2": "절 번호 순서",
            "F3": "빈 줄/줄바꿈",
            "F4": "오염(Copyright/코드/깨짐)",
            "F5": "한글 비율",
            "F6": "최소 길이",
            "F7": "절구조 불일치",
        }
        for vtype, cnt in violation_types.most_common():
            label = labels.get(vtype, vtype)
            print(f"    {vtype} {label}: {cnt}곡")

    if args.detail:
        print(f"\n{'='*60}")
        print(f"  곡별 상세 (위반 곡만)")
        print(f"{'='*60}")
        for r in results:
            if r["상태"] != "위반":
                continue
            print(f"\n  [{r['번호']}] {r['제목']}")
            for issue in r["위반"]:
                print(f"    ⚠️  {issue}")


if __name__ == "__main__":
    main()
