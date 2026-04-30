"""S-007: 곡정보.xlsx의 곡목록 시트에 '비고' 컬럼 추가 (1회 마이그레이션, idempotent).

기존 (4컬럼): 번호 · 제목 · 작곡자 · 분류
이후 (5컬럼): 번호 · 제목 · 작곡자 · 분류 · 비고

비고 셀은 모두 빈 채로 둠. 사용자가 에디터 또는 엑셀에서 직접 채움.

사용:
    python scripts/migrate_add_bigo_column.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openpyxl import load_workbook

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "source" / "곡정보.xlsx"
EXPECTED_HEADERS_BEFORE = ("번호", "제목", "작곡자", "분류")
NEW_HEADER = "비고"


def main() -> None:
    p = argparse.ArgumentParser(description="곡목록 시트에 '비고' 컬럼 추가")
    p.add_argument("--dry-run", action="store_true", help="실제 저장 없이 확인만")
    args = p.parse_args()

    if not XLSX.exists():
        raise SystemExit(f"xlsx 없음: {XLSX}")

    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        raise SystemExit(f"xlsx 잠김 — 엑셀에서 닫고 재시도: {XLSX}")

    if "곡목록" not in wb.sheetnames:
        raise SystemExit("'곡목록' 시트 없음")

    ws = wb["곡목록"]

    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    print(f"현재 헤더: {headers}")

    if NEW_HEADER in headers:
        print(f"이미 '{NEW_HEADER}' 컬럼 존재 — skip (idempotent)")
        return

    if tuple(headers[:4]) != EXPECTED_HEADERS_BEFORE:
        raise SystemExit(
            f"예상 헤더 불일치: {headers[:4]!r} vs {EXPECTED_HEADERS_BEFORE!r}"
        )

    new_col = len(headers) + 1
    ws.cell(row=1, column=new_col).value = NEW_HEADER
    ws.cell(row=1, column=new_col).number_format = "@"
    print(f"→ 헤더 셀 (1, {new_col}) = {NEW_HEADER!r}")

    if args.dry_run:
        print("\nDRY RUN — 저장 안 함")
        return

    try:
        wb.save(XLSX)
    except PermissionError:
        raise SystemExit(f"저장 실패 — xlsx 잠김: {XLSX}")

    print(f"\n[saved] {XLSX}")
    print("다음 단계: python scripts/rebuild.py")


if __name__ == "__main__":
    main()
