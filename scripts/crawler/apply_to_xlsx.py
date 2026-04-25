"""
apply_to_xlsx.py

크롤러가 만든 jsonl을 곡정보.xlsx의 '가사' 시트에 병합.

v2 SSoT 정책:
  - songs.json은 파생물 → 직접 수정 금지
  - 사용자 편집 SSoT는 data/source/곡정보.xlsx
  - 크롤러는 jsonl만 만들고, 이 스크립트가 사용자 검토 후 xlsx에 적용한다

매칭 정책 (소스별):
  - yseng: jsonl의 '번호' (청소년청년성가집 번호) 직접 매칭
  - maria: jsonl의 '제목' ↔ xlsx 곡목록 시트의 '제목' 정확 일치
           (jsonl '번호'는 가톨릭성가집 번호이므로 직접 매칭 불가)
  - 임의 경로: jsonl '번호'를 청소년청년성가집 번호로 가정해 직접 매칭

보호 정책 (기본):
  - 가사 셀이 비어있는 곡만 채움 (이미 가사가 있으면 skip)
  - 가사가 없는 jsonl 레코드(실패 레코드)는 skip
  - --force로 덮어쓰기 가능

사용:
    python scripts/crawler/apply_to_xlsx.py yseng
    python scripts/crawler/apply_to_xlsx.py maria
    python scripts/crawler/apply_to_xlsx.py path/to/custom.jsonl --source yseng
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment

ROOT = Path(__file__).resolve().parent.parent.parent
XLSX = ROOT / "data" / "source" / "곡정보.xlsx"
DATA_DIR = ROOT / "scripts" / "crawler" / "data"

DEFAULT_PATHS = {
    "yseng": DATA_DIR / "yseng_sungga.jsonl",
    "maria": DATA_DIR / "maria_sungga.jsonl",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def normalize_title(t: str) -> str:
    """제목 정규화: 공백·구두점·특수문자 제거."""
    return re.sub(r"[\s!?.,'\"\-_/()\[\]<>]+", "", t or "").lower()


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def read_xlsx_state(wb) -> tuple[dict[int, int], dict[str, int], dict[int, str]]:
    """
    곡목록 시트에서 (번호 → row, 정규화제목 → 번호) 매핑 + 가사 시트 (번호 → row) 매핑.
    """
    if "곡목록" not in wb.sheetnames or "가사" not in wb.sheetnames:
        raise SystemExit("'곡목록' 또는 '가사' 시트가 없습니다.")
    ws_list = wb["곡목록"]
    ws_lyrics = wb["가사"]

    title_to_num: dict[str, int] = {}
    duplicate_titles: set[str] = set()
    for ri in range(2, ws_list.max_row + 1):
        n = ws_list.cell(row=ri, column=1).value
        title = ws_list.cell(row=ri, column=2).value
        if n is None or n == "" or not title:
            continue
        try:
            num = int(float(str(n)))
        except (ValueError, TypeError):
            continue
        key = normalize_title(str(title))
        if key in title_to_num:
            duplicate_titles.add(key)
        else:
            title_to_num[key] = num
    # 중복 제목은 매칭 키에서 제거 (안전)
    for k in duplicate_titles:
        title_to_num.pop(k, None)

    num_to_lyrics_row: dict[int, int] = {}
    for ri in range(2, ws_lyrics.max_row + 1):
        n = ws_lyrics.cell(row=ri, column=1).value
        if n is None or n == "":
            continue
        try:
            num = int(float(str(n)))
        except (ValueError, TypeError):
            continue
        num_to_lyrics_row[num] = ri

    return num_to_lyrics_row, title_to_num, duplicate_titles  # type: ignore


def resolve_target_num(rec: dict, source: str, title_to_num: dict[str, int]) -> int | None:
    """jsonl 레코드 → 청소년청년성가집 번호."""
    if source == "yseng":
        n = rec.get("번호")
        if n is None:
            return None
        try:
            return int(float(str(n)))
        except (ValueError, TypeError):
            return None
    if source == "maria":
        title = rec.get("제목") or ""
        return title_to_num.get(normalize_title(title))
    # 임의: 번호 직접 매칭
    n = rec.get("번호")
    if n is None:
        return None
    try:
        return int(float(str(n)))
    except (ValueError, TypeError):
        return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("source_or_path", help="'yseng' | 'maria' | jsonl 경로")
    p.add_argument("--source", choices=["yseng", "maria"],
                   help="임의 jsonl 경로일 때 매칭 정책 지정")
    p.add_argument("--force", action="store_true",
                   help="가사가 이미 있어도 덮어쓰기")
    p.add_argument("--dry-run", action="store_true",
                   help="xlsx에 쓰지 않고 결과만 출력")
    args = p.parse_args()

    # 경로·소스 결정
    if args.source_or_path in DEFAULT_PATHS:
        source = args.source_or_path
        jsonl_path = DEFAULT_PATHS[source]
    else:
        jsonl_path = Path(args.source_or_path)
        source = args.source or "yseng"  # 기본: 번호 직접 매칭(yseng와 동일)

    if not jsonl_path.exists():
        raise SystemExit(f"jsonl 없음: {jsonl_path}")
    if not XLSX.exists():
        raise SystemExit(f"xlsx 없음: {XLSX}")

    records = load_jsonl(jsonl_path)
    print(f"[load] {len(records)}건 ← {jsonl_path}  (source={source})")

    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        raise SystemExit(
            f"xlsx 잠김 — 엑셀에서 곡정보.xlsx를 닫고 다시 시도하세요.\n  {XLSX}"
        )

    num_to_row, title_to_num, dup_titles = read_xlsx_state(wb)
    ws = wb["가사"]

    if dup_titles:
        print(f"  [경고] 중복 제목 {len(dup_titles)}건 — maria 매칭 제외")

    counts = dict(updated=0, skipped_existing=0, skipped_no_lyrics=0,
                  no_match=0, no_row=0)
    no_match_samples: list[str] = []

    for rec in records:
        text = rec.get("가사")
        if not text:
            counts["skipped_no_lyrics"] += 1
            continue

        num = resolve_target_num(rec, source, title_to_num)
        if num is None:
            counts["no_match"] += 1
            if len(no_match_samples) < 10:
                no_match_samples.append(
                    f"제목={rec.get('제목')!r} 번호={rec.get('번호')!r}"
                )
            continue

        row = num_to_row.get(num)
        if row is None:
            counts["no_row"] += 1
            continue

        cell = ws.cell(row=row, column=2)
        existing = (cell.value or "").strip() if isinstance(cell.value, str) else cell.value
        if existing and not args.force:
            counts["skipped_existing"] += 1
            continue

        if not args.dry_run:
            cell.value = text
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.number_format = "@"
        counts["updated"] += 1

    if counts["updated"] > 0 and not args.dry_run:
        try:
            wb.save(XLSX)
        except PermissionError:
            raise SystemExit(
                f"저장 실패 — xlsx가 잠긴 것 같습니다.\n  {XLSX}"
            )

    print("\n=== 적용 결과 ===")
    print(f"  적용:                {counts['updated']}건")
    print(f"  skip(이미 있음):     {counts['skipped_existing']}건")
    print(f"  skip(jsonl 가사 없음): {counts['skipped_no_lyrics']}건")
    print(f"  매칭 실패:           {counts['no_match']}건")
    print(f"  xlsx 행 없음:        {counts['no_row']}건")
    if args.dry_run:
        print("  모드: DRY-RUN (xlsx 미저장)")
    if no_match_samples:
        print("\n  [매칭 실패 샘플]")
        for s in no_match_samples:
            print(f"    - {s}")
    if counts["updated"] > 0 and not args.dry_run:
        print("\n  ⚠ xlsx만 수정됨. JSON 재빌드 필요:")
        print("     python scripts/rebuild.py")


if __name__ == "__main__":
    main()
