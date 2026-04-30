"""사용자 검토 통과한 박자 CSV → 곡정보.xlsx의 곡목록 시트 박자 컬럼에 병합.

사용:
  python scripts/apply_meter.py [--from data/raw/박자_자동추정.csv] [--dry-run]

동작:
  - CSV의 '박자' 컬럼을 곡목록 시트 '박자' 컬럼에 쓴다
  - 빈 박자는 건너뜀
  - 검토필요=Y인 행은 기본 적용 안 함 (--include-needs-review로 강제)
  - 이미 xlsx에 값이 있으면 덮어쓰지 않음 (--overwrite로 강제)
  - 입력 형식 검증: 분수 (예: 4/4, 3/4, 6/8) — 비표준 vocab은 경고
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "source" / "곡정보.xlsx"
DEFAULT_CSV = ROOT / "data" / "raw" / "박자_자동추정.csv"

METER_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")
COMMON_METERS = {"2/4", "3/4", "4/4", "6/8", "9/8", "12/8", "2/2", "3/2", "3/8", "6/4"}


def parse_meter(s: str) -> str | None:
    """'4/4' 형식만 허용. 정규화해서 반환."""
    if not s:
        return None
    m = METER_RE.match(s)
    if not m:
        return None
    return f"{int(m.group(1))}/{int(m.group(2))}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default=str(DEFAULT_CSV))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-needs-review", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"CSV 없음: {src}")
    if not XLSX.exists():
        raise SystemExit(f"xlsx 없음: {XLSX}")

    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))

    if "박자" not in rows[0]:
        raise SystemExit(f"CSV에 '박자' 컬럼 없음. 형식: {list(rows[0].keys())}")

    wb = load_workbook(XLSX)
    ws = wb["곡목록"]

    headers = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
    if "박자" not in headers:
        raise SystemExit("xlsx에 박자 컬럼이 없음. migrate_add_keysig_meter_columns.py 먼저 실행.")
    meter_col = headers["박자"]
    num_col = headers["번호"]

    num_to_row = {}
    for r in range(2, ws.max_row + 1):
        v = ws.cell(row=r, column=num_col).value
        if v is None:
            continue
        try:
            num_to_row[int(float(str(v)))] = r
        except ValueError:
            continue

    applied = 0
    skipped_review = 0
    skipped_existing = 0
    skipped_invalid = 0
    skipped_empty = 0
    uncommon = []

    for row in rows:
        try:
            num = int(row["번호"])
        except (ValueError, KeyError):
            continue

        raw = row.get("박자", "").strip()
        if not raw:
            skipped_empty += 1
            continue

        meter = parse_meter(raw)
        if meter is None:
            skipped_invalid += 1
            print(f"  invalid meter 번호={num}: {raw!r}")
            continue

        if row.get("검토필요", "").strip() == "Y" and not args.include_needs_review:
            skipped_review += 1
            continue

        if num not in num_to_row:
            print(f"  xlsx에 번호 {num} 없음 — skip")
            continue

        cell = ws.cell(row=num_to_row[num], column=meter_col)
        existing = cell.value
        if existing not in (None, "") and not args.overwrite:
            skipped_existing += 1
            continue

        if meter not in COMMON_METERS:
            uncommon.append((num, meter))

        if not args.dry_run:
            cell.value = meter
            cell.number_format = "@"
        applied += 1

    print(f"적용: {applied}")
    print(f"skip (검토필요=Y): {skipped_review}")
    print(f"skip (기존 값 있음): {skipped_existing}")
    print(f"skip (빈 박자): {skipped_empty}")
    print(f"skip (잘못된 형식): {skipped_invalid}")
    if uncommon:
        print(f"\n비표준 박자 vocab 사용: {len(uncommon)}건 (vocab.md 보강 검토)")
        for num, m in uncommon[:10]:
            print(f"  번호 {num}: {m}")

    if not args.dry_run and applied > 0:
        wb.save(XLSX)
        print(f"\nxlsx 저장 완료: {XLSX}")
        print("→ python scripts/build_songs_json.py 로 songs.json 재빌드 권장")
    elif args.dry_run:
        print("\n(--dry-run: 저장 안 함)")


if __name__ == "__main__":
    main()
