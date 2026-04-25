"""생성된 신뢰도 백업 xlsx 검증."""
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")

XLSX = Path("s:/song_recommendation/data/archive/신뢰도_스냅샷_2026-04-25.xlsx")

wb = load_workbook(XLSX)
print(f"시트 목록: {wb.sheetnames}")
ws = wb["신뢰도_외부ID"]

rows = list(ws.iter_rows(values_only=True))
headers = rows[0]
data_rows = rows[1:]

print(f"헤더: {headers}")
print(f"데이터 행 수: {len(data_rows)}")
print()

# 샘플 5행
print("=== 샘플 5행 ===")
for r in data_rows[:5]:
    print(f"  {r}")

print()

# 통계: 신뢰도 채움 vs 외부ID 채움
sin_only = 0
ext_only = 0
both = 0
for r in data_rows:
    has_sin = r[2] is not None and r[2] != ""
    has_ext = r[6] is not None and r[6] != ""
    if has_sin and has_ext:
        both += 1
    elif has_sin:
        sin_only += 1
    elif has_ext:
        ext_only += 1

print(f"신뢰도만 있음: {sin_only}")
print(f"외부ID만 있음: {ext_only}")
print(f"둘 다 있음: {both}")
print(f"합계: {sin_only + ext_only + both} (= {len(data_rows)})")
