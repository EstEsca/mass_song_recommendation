"""박자(time signature) 추정 — oemer 미지원이라 현 시점은 빈 스켈레톤 생성.

oemer의 symbol_extraction.py는 sfn(샤프/플랫/내추럴), clef, barline, rest만 추출하고
time signature 클래스가 없어 MusicXML 출력에 <time> 요소가 누락된다.
(학습 데이터·모델 한계. 향후 Audiveris로 교체 시 이 스크립트의 입력만 바꾸면 됨.)

산출:
  - data/raw/박자_자동추정.csv
    컬럼: 번호, 제목, pdf_page, 박자(추정), 출처, 검토필요
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
SONGS_JSON = ROOT / "data" / "songs.json"
KEYSIG_CSV = ROOT / "data" / "raw" / "조표_자동추정.csv"
OUTPUT_CSV = ROOT / "data" / "raw" / "박자_자동추정.csv"


def main():
    songs = json.load(SONGS_JSON.open(encoding="utf-8"))["songs"]

    # 조표 CSV에서 pdf_page 매핑 재사용
    page_map = {}
    if KEYSIG_CSV.exists():
        for row in csv.DictReader(KEYSIG_CSV.open(encoding="utf-8-sig")):
            page_map[row["번호"]] = row["pdf_page"]

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for num_str, song in songs.items():
        rows.append({
            "번호": int(num_str),
            "제목": song["제목"],
            "pdf_page": page_map.get(num_str, ""),
            "박자(추정)": "",
            "출처": "",
            "검토필요": "Y",
        })

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["번호", "제목", "pdf_page", "박자(추정)", "출처", "검토필요"])
        w.writeheader()
        w.writerows(rows)

    print(f"output: {OUTPUT_CSV}")
    print(f"total rows: {len(rows)}")
    print()
    print("주의: 이 파일은 빈 스켈레톤이다.")
    print("  - oemer는 박자를 추출하지 못함 (symbol_extraction.py 한계)")
    print("  - 채우는 방법:")
    print("    A) Audiveris 설치 후 OMR 재실행 — JRE + Audiveris 약 350MB")
    print("    B) 사용자가 xlsx에서 직접 입력 — 495곡 × ~3초 ≈ 25분")
    print("    C) 페이지 이미지 보면서 입력 (data/raw/박자_자동추정.csv 직접)")


if __name__ == "__main__":
    main()
