"""사용자 검토 통과한 조표 CSV → 곡정보.xlsx의 곡목록 시트 조표 컬럼에 병합.

사용:
  python scripts/apply_keysig.py [--from data/raw/조표_자동추정.csv] [--dry-run]

동작:
  - CSV의 '권장값' 컬럼을 곡목록 시트 '조표' 컬럼에 쓴다
  - 빈 권장값은 건너뜀
  - 검토필요=Y인 행은 기본 적용 안 함 (--include-needs-review로 강제)
  - 이미 xlsx에 값이 있으면 덮어쓰지 않음 (--overwrite로 강제)
  - 입력 형식 검증: 정수 -7~+7
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "source" / "곡정보.xlsx"
DEFAULT_CSV = ROOT / "data" / "raw" / "조표_자동추정.csv"


def parse_keysig(s: str) -> int | None:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        v = int(s)
    except ValueError:
        return None
    if not -7 <= v <= 7:
        return None
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default=str(DEFAULT_CSV))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-needs-review", action="store_true",
                    help="검토필요=Y인 행도 적용")
    ap.add_argument("--overwrite", action="store_true",
                    help="xlsx에 기존 값이 있어도 덮어쓰기")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"CSV 없음: {src}")
    if not XLSX.exists():
        raise SystemExit(f"xlsx 없음: {XLSX}")

    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))

    # CSV 컬럼: '권장값', '검토필요' 사용
    if "권장값" not in rows[0]:
        raise SystemExit(f"CSV에 '권장값' 컬럼 없음. 형식: {list(rows[0].keys())}")

    wb = load_workbook(XLSX)
    ws = wb["곡목록"]

    # 헤더에서 조표 컬럼 위치 찾기
    headers = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
    if "조표" not in headers:
        raise SystemExit("xlsx에 조표 컬럼이 없음. migrate_add_keysig_meter_columns.py 먼저 실행.")
    keysig_col = headers["조표"]
    num_col = headers["번호"]

    # 번호 → row 인덱스 매핑
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

    for row in rows:
        try:
            num = int(row["번호"])
        except (ValueError, KeyError):
            continue

        rec_str = row.get("권장값", "").strip()
        if not rec_str:
            skipped_empty += 1
            continue

        ks = parse_keysig(rec_str)
        if ks is None:
            skipped_invalid += 1
            print(f"  invalid keysig 번호={num}: {rec_str!r}")
            continue

        if row.get("검토필요", "").strip() == "Y" and not args.include_needs_review:
            skipped_review += 1
            continue

        if num not in num_to_row:
            print(f"  xlsx에 번호 {num} 없음 — skip")
            continue

        cell = ws.cell(row=num_to_row[num], column=keysig_col)
        existing = cell.value
        if existing not in (None, "") and not args.overwrite:
            skipped_existing += 1
            continue

        if not args.dry_run:
            cell.value = f"{ks:+d}" if ks != 0 else "0"
            cell.number_format = "@"
        applied += 1

    print(f"적용: {applied}")
    print(f"skip (검토필요=Y): {skipped_review}")
    print(f"skip (기존 값 있음): {skipped_existing}")
    print(f"skip (빈 권장값): {skipped_empty}")
    print(f"skip (잘못된 형식): {skipped_invalid}")

    if not args.dry_run and applied > 0:
        wb.save(XLSX)
        print(f"\nxlsx 저장 완료: {XLSX}")
        print("→ python scripts/build_songs_json.py 로 songs.json 재빌드 권장")
    elif args.dry_run:
        print("\n(--dry-run: 저장 안 함)")


if __name__ == "__main__":
    main()
