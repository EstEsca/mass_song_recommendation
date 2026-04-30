"""v2.0 → v2.1 마이그레이션 — 곡목록 시트에 조표·박자 컬럼 추가.

기존 셀은 보존. 헤더만 추가 후 기존 비고 컬럼 뒤에 빈 컬럼 2개 삽입.
이미 컬럼이 있으면 idempotent 동작.

실행 후 build_songs_json.py가 새 컬럼을 인식.

산출:
  data/source/곡정보.xlsx (in-place 수정)
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "source" / "곡정보.xlsx"

EXPECTED_HEADERS = ["번호", "제목", "작곡자", "분류", "비고", "조표", "박자"]


def main():
    if not XLSX.exists():
        raise SystemExit(f"xlsx 없음: {XLSX}")

    wb = load_workbook(XLSX)
    if "곡목록" not in wb.sheetnames:
        raise SystemExit("곡목록 시트 없음")

    ws = wb["곡목록"]
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    headers = [h for h in headers if h is not None]
    print(f"현재 헤더: {headers}")

    if headers == EXPECTED_HEADERS:
        print("이미 v2.1 헤더 — 변경 없음")
        return

    if "조표" in headers and "박자" in headers:
        print("조표·박자 컬럼 이미 존재 — 변경 없음")
        return

    # 비고 다음 칸을 조표·박자로 채움
    if headers != ["번호", "제목", "작곡자", "분류", "비고"]:
        raise SystemExit(
            f"기대 v2.0 헤더(번호·제목·작곡자·분류·비고)와 다름: {headers}\n"
            "수동 검토 필요."
        )

    next_col = len(headers) + 1  # 6
    ws.cell(row=1, column=next_col, value="조표").alignment = Alignment(horizontal="center")
    ws.cell(row=1, column=next_col + 1, value="박자").alignment = Alignment(horizontal="center")

    # 모든 셀 텍스트 서식 (xlsx 정책)
    for row in range(2, ws.max_row + 1):
        for c in (next_col, next_col + 1):
            cell = ws.cell(row=row, column=c)
            cell.number_format = "@"

    wb.save(XLSX)
    print(f"컬럼 추가 완료: 조표(col {next_col}), 박자(col {next_col + 1})")


if __name__ == "__main__":
    main()
