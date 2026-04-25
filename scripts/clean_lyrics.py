"""
/clean-lyrics 스킬 실행 스크립트 (v2 스키마).

가사 본문에서 다음 항목만 정리한다:
  X11: 악보 메타(♩, 템포, 박자, 단독 조표, BOM) 제거 ← 항상 실행
  X2:  슬래시 구분자 제거
  X3:  Copyright/코드 심볼/깨진 영문 연속 제거
  X4:  빈 줄 제거
  X7:  영문 잔존 토큰 제거  ← opt-in (영문 원제가 제거될 위험)
  X8:  짧은 절 인접 병합 (마커 필수)

절/후렴 구조(마커 통일·생성·재정렬)는 건드리지 않는다.
구조 재구성은 후속 /structure-lyrics의 몫.

v2 스키마: 가사는 단일 문자열. SSoT는 data/source/곡정보.xlsx의 '가사' 시트.
이 스크립트는 xlsx의 가사 시트만 수정하며, songs.json은 손대지 않는다.
변경 후 사용자가 `python scripts/rebuild.py`로 JSON을 재빌드해야 한다.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment

from _lyrics_cleanup import (
    drop_blank_lines,
    merge_short_verses,
    remove_contamination,
    remove_slashes,
    strip_english_residue,
    strip_music_notation,
)

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "source" / "곡정보.xlsx"
SHEET = "가사"


def clean_text(text: str, apply_x7: bool = False) -> tuple[str, list[str]]:
    """본문 텍스트 정리. (정리된 텍스트, 교정 로그) 반환.

    apply_x7=True면 영문 잔존 토큰 강제 제거 추가 (영문 원제도 사라질 수 있음).
    """
    log: list[str] = []

    # X11: 악보 메타 (remove_slashes 전에!)
    new, n = strip_music_notation(text)
    if n:
        log.append(f"X11: 악보 메타 {n}개 제거")
        text = new

    new = remove_slashes(text)
    if new != text:
        log.append("X2: 슬래시 제거")
        text = new

    new, rm = remove_contamination(text)
    if rm:
        log.extend(f"X3: {r}" for r in rm)
        text = new

    new = drop_blank_lines(text)
    if new != text:
        log.append("X4: 빈 줄 제거")
        text = new

    if apply_x7:
        new, removed = strip_english_residue(text)
        if removed:
            log.append(f"X7: 영문 토큰 {removed}개 제거")
            text = new

    new, merged = merge_short_verses(text, min_len=10)
    if merged:
        log.append(f"X8: 짧은 절 {merged}건 병합")
        text = new

    return text, log


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


def _x7_prompt() -> bool:
    bar = "━" * 60
    msg = f"""
{bar}
X7: 영문 잔존 토큰 강제 제거 (선택 단계)
{bar}
[동작]
  공백으로 쪼갠 토큰 중 한글 1자 이상 또는 순수 숫자/구두점만 남기고 제거.
  마커([1절], [후렴] 등)와 줄 단위는 보존.

[부작용 — 영문 원제·라틴 가사도 함께 사라짐]
  • "Oh Father" → ""
  • "Nada te turbe" → ""
  • "Bless the Lord" → ""

[적용 권장]
  • 본문이 거의 전부 한글인 곡
  • OCR/크롤링 잔재가 남은 곡

[적용 비권장]
  • 떼제(Taizé), Kumbaya 등 원어 찬양
{bar}
"""
    print(msg, file=sys.stderr)
    ans = input("X7을 적용할까요? [y/N]: ").strip().lower()
    decided = ans in ("y", "yes")
    print(f"→ X7 {'적용' if decided else '건너뜀'}", file=sys.stderr)
    return decided


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="가사 본문 정리 (v2: 곡정보.xlsx의 '가사' 시트 직접 편집)"
    )
    parser.add_argument(
        "target", nargs="?", default="전부",
        help="곡 번호/범위/'전부' (예: 5, 1-100, 32,38,50)",
    )
    g = parser.add_mutually_exclusive_group()
    g.add_argument(
        "--yes-x7", action="store_true",
        help="X7(영문 잔존 제거)을 프롬프트 없이 적용 (영문 원제가 사라질 수 있음)",
    )
    g.add_argument(
        "--no-x7", action="store_true",
        help="X7을 프롬프트 없이 건너뜀 (안전 기본)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="xlsx에 쓰지 않고 결과만 출력",
    )
    args = parser.parse_args()

    if args.yes_x7:
        apply_x7 = True
    elif args.no_x7:
        apply_x7 = False
    else:
        apply_x7 = _x7_prompt()

    if not XLSX.exists():
        raise SystemExit(f"xlsx 없음: {XLSX}")

    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        raise SystemExit(
            f"xlsx 잠김 — 엑셀에서 곡정보.xlsx를 닫고 다시 시도하세요.\n  {XLSX}"
        )

    if SHEET not in wb.sheetnames:
        raise SystemExit(f"'{SHEET}' 시트가 없습니다.")
    ws = wb[SHEET]

    headers = [c.value for c in ws[1]]
    if headers[:2] != ["번호", "가사"]:
        raise SystemExit(
            f"'{SHEET}' 시트 헤더 불일치: {headers!r} (기대: ['번호', '가사', ...])"
        )

    # 행 수집: (row_idx, 번호, 가사텍스트)
    rows: list[tuple[int, int, str]] = []
    for ri in range(2, ws.max_row + 1):
        num_cell = ws.cell(row=ri, column=1).value
        text_cell = ws.cell(row=ri, column=2).value
        if num_cell is None or num_cell == "":
            continue
        try:
            num = int(float(str(num_cell)))
        except (ValueError, TypeError):
            continue
        rows.append((ri, num, str(text_cell or "")))

    all_nums = sorted(num for _, num, _ in rows)
    target_set = set(parse_targets(args.target, all_nums))

    total = 0
    modified_count = 0
    fix_types: Counter[str] = Counter()

    for ri, num, text in rows:
        if num not in target_set:
            continue
        if not text:
            continue
        total += 1
        new_text, log = clean_text(text, apply_x7=apply_x7)
        if new_text != text:
            modified_count += 1
            for entry in log:
                fix_types[entry.split(":")[0]] += 1
            if not args.dry_run:
                cell = ws.cell(row=ri, column=2)
                cell.value = new_text
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.number_format = "@"

    if modified_count > 0 and not args.dry_run:
        try:
            wb.save(XLSX)
        except PermissionError:
            raise SystemExit(
                f"저장 실패 — xlsx가 잠긴 것 같습니다. 엑셀에서 닫고 다시 시도.\n  {XLSX}"
            )

    print("\n" + "=" * 60)
    print("  clean-lyrics 결과")
    print("=" * 60)
    print(f"  대상:   {total}곡")
    print(f"  교정:   {modified_count}곡")
    print(f"  미변경: {total - modified_count}곡")
    print(f"  X7:     {'적용' if apply_x7 else '건너뜀'}")
    if args.dry_run:
        print(f"  모드:   DRY-RUN (xlsx 미저장)")
    if fix_types:
        print("\n  교정 유형별:")
        for ft, cnt in fix_types.most_common():
            print(f"    {ft}: {cnt}건")
    if modified_count > 0 and not args.dry_run:
        print()
        print("  ⚠ xlsx만 수정됨. songs.json/songs_index.json 재빌드 필요:")
        print("     python scripts/rebuild.py")


if __name__ == "__main__":
    main()
