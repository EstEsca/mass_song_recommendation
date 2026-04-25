"""생성된 곡정보.xlsx 검증."""
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")

XLSX = Path("s:/song_recommendation/data/source/곡정보.xlsx")

wb = load_workbook(XLSX)
print(f"시트 목록: {wb.sheetnames}")
print()

for sheet_name in wb.sheetnames:
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]
    data_rows = rows[1:]
    print(f"=== 시트 '{sheet_name}' ===")
    print(f"  헤더: {headers}")
    print(f"  데이터 행: {len(data_rows)}")
    # Table 등록 여부
    tables = list(ws.tables)
    print(f"  테이블: {tables}")
    # 샘플 3행
    print("  샘플:")
    for r in data_rows[:3]:
        # 긴 텍스트는 자르기
        r = tuple(
            (v[:60] + "…") if isinstance(v, str) and len(v) > 60 else v
            for v in r
        )
        print(f"    {r}")
    print()

# 색인 시트 타입별 분포 재확인
print("=== '색인' 시트 타입별 분포 ===")
ws = wb["색인"]
rows = list(ws.iter_rows(values_only=True))[1:]
from collections import Counter
c = Counter(r[1] for r in rows)
for k, v in sorted(c.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

# 곡 1번과 2번의 색인 태그 보기
print()
print("=== 곡 1번 색인 태그 ===")
for r in rows:
    if r[0] == "1":
        print(f"  {r[1]}: {r[2]}")

print()
print("=== 곡 2번 색인 태그 ===")
for r in rows:
    if r[0] == "2":
        print(f"  {r[1]}: {r[2]}")

# 가톨릭성가 태깅된 곡 수
print()
gatholic = [r[0] for r in rows if r[1] == "곡모음집" and r[2] == "가톨릭성가"]
print(f"곡모음집='가톨릭성가' 태깅 곡 수: {len(gatholic)}")
