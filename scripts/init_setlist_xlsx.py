"""
init_setlist_xlsx.py — 선곡표.xlsx 초기 생성 (1회 실행).

ADR-008 사이드카 4개 중 선곡표 시트 헤더만 만든다.
이미 파일이 있으면 덮어쓰지 않고 종료.

    python scripts/init_setlist_xlsx.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "source" / "선곡표.xlsx"

COLUMNS = ["주일", "전례명", "카테고리", "곡번호", "곡명", "선정이유", "비고"]


def main() -> None:
    if XLSX.exists():
        print(f"이미 존재: {XLSX} — 덮어쓰지 않음")
        return

    XLSX.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "선곡"

    header_font = Font(bold=True)
    header_fill = PatternFill("solid", fgColor="EEEEEE")

    for col_idx, name in enumerate(COLUMNS, start=1):
        c = ws.cell(row=1, column=col_idx, value=name)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center")

    widths = {1: 12, 2: 18, 3: 10, 4: 8, 5: 28, 6: 40, 7: 24}
    for col_idx, w in widths.items():
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = w

    for col_idx in range(1, len(COLUMNS) + 1):
        ws.cell(row=1, column=col_idx).number_format = "@"

    ws.freeze_panes = "A2"

    wb.save(XLSX)
    print(f"생성: {XLSX}")


if __name__ == "__main__":
    main()
