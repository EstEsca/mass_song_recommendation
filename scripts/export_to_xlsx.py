"""
export_to_xlsx.py

v2 songs.json → data/source/곡정보.xlsx (4시트).

Stage A 초기 1회용. 이후에는 xlsx가 SSoT가 되므로 재실행 금지
(재실행은 사용자 편집을 덮어쓸 위험 → 기본적으로 파일이 이미 있으면 실행 거부).

시트 구성:
- 곡목록 (Wide): 번호·제목·작곡자·분류
- 요약   (Wide): 번호·요약
- 색인   (Tall/EAV): 번호·타입·값
- 가사   (Wide): 번호·가사

모든 셀은 텍스트 서식. 각 시트는 Excel Table로 등록되어 필터·정렬 기본 제공.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SONGS_JSON = ROOT / "data" / "songs.json"
OUT_XLSX = ROOT / "data" / "source" / "곡정보.xlsx"

# 색인 타입 순서 (색인 시트의 행 정렬 및 가독성)
INDEX_TYPE_ORDER = ["성경", "성월", "시기", "대축일", "역할", "느낌", "키워드", "곡모음집"]


# --- styling helpers ---------------------------------------------------------

def _style_header(ws, col_count: int) -> None:
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
    for c in range(1, col_count + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"


def _set_all_text(ws) -> None:
    for row in ws.iter_rows():
        for cell in row:
            cell.number_format = "@"


def _add_table(ws, name: str, col_count: int, data_row_count: int) -> None:
    """Excel Table로 등록. data_row_count는 헤더 제외 데이터 행 수."""
    last_col = get_column_letter(col_count)
    last_row = data_row_count + 1  # +1 for header
    ref = f"A1:{last_col}{last_row}"
    tab = Table(displayName=name, ref=ref)
    tab.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium9",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(tab)


def _set_col_widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# --- sheet writers -----------------------------------------------------------

def write_songs_sheet(wb: Workbook, songs: dict) -> None:
    ws = wb.create_sheet("곡목록")
    ws.append(["번호", "제목", "작곡자", "분류"])
    for num_key in sorted(songs.keys(), key=int):
        s = songs[num_key]
        ws.append([str(s["번호"]), s["제목"], s["작곡자"], s["분류"]])
    _style_header(ws, 4)
    _set_all_text(ws)
    _add_table(ws, "tbl_songs", 4, len(songs))
    _set_col_widths(ws, [8, 40, 20, 10])


def write_summary_sheet(wb: Workbook, songs: dict) -> None:
    ws = wb.create_sheet("요약")
    ws.append(["번호", "요약"])
    for num_key in sorted(songs.keys(), key=int):
        s = songs[num_key]
        ws.append([str(s["번호"]), s["색인"].get("요약", "")])
    _style_header(ws, 2)
    _set_all_text(ws)
    _add_table(ws, "tbl_summaries", 2, len(songs))
    _set_col_widths(ws, [8, 80])


def write_index_sheet(wb: Workbook, songs: dict) -> int:
    ws = wb.create_sheet("색인")
    ws.append(["번호", "타입", "값"])
    count = 0
    for num_key in sorted(songs.keys(), key=int):
        s = songs[num_key]
        num = str(s["번호"])
        idx = s["색인"]
        for type_name in INDEX_TYPE_ORDER:
            for val in idx.get(type_name, []):
                ws.append([num, type_name, val])
                count += 1
    _style_header(ws, 3)
    _set_all_text(ws)
    _add_table(ws, "tbl_index", 3, count)
    _set_col_widths(ws, [8, 10, 40])
    return count


def write_lyrics_sheet(wb: Workbook, songs: dict) -> None:
    ws = wb.create_sheet("가사")
    ws.append(["번호", "가사"])
    for num_key in sorted(songs.keys(), key=int):
        s = songs[num_key]
        ws.append([str(s["번호"]), s.get("가사") or ""])
        # 가사는 긴 셀이므로 줄바꿈 wrap
        ws.cell(row=ws.max_row, column=2).alignment = Alignment(
            vertical="top", wrap_text=True
        )
    _style_header(ws, 2)
    _set_all_text(ws)
    _add_table(ws, "tbl_lyrics", 2, len(songs))
    _set_col_widths(ws, [8, 100])


# --- main --------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="이미 존재하는 곡정보.xlsx를 덮어쓴다 (사용자 편집 손실 위험)",
    )
    args = parser.parse_args()

    with SONGS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)
    songs = data["songs"]
    print(f"[load] {len(songs)}곡 ← {SONGS_JSON}")

    if OUT_XLSX.exists() and not args.force:
        raise SystemExit(
            f"이미 존재: {OUT_XLSX}\n"
            f"덮어쓰려면 --force (사용자 편집 손실 위험)."
        )

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    # 기본 시트 제거
    wb.remove(wb.active)

    write_songs_sheet(wb, songs)
    write_summary_sheet(wb, songs)
    tag_count = write_index_sheet(wb, songs)
    write_lyrics_sheet(wb, songs)

    wb.save(OUT_XLSX)
    print(f"[export] → {OUT_XLSX}")
    print(f"시트 4개: {[ws.title for ws in wb.worksheets]}")
    print(f"색인 태그 총 {tag_count}건")


if __name__ == "__main__":
    main()
