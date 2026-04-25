"""
serialize_candidates.py

filter_candidates.py의 JSON 출력을 LLM 프롬프트에 넣을 **Wide TSV**로 변환.

입력 JSON: {meta, results: {<카테고리>: [후보, ...]}}
출력 TSV: 헤더 1줄 + 곡당 1줄.
  컬럼: 카테고리, 번호, 제목, 작곡자, 분류, 요약, 성경, 시기, 대축일, 성월, 역할, 느낌, 키워드, 곡모음집, 점수, 근거

배열 필드는 '|' 구분, 근거는 ';' 구분. 마지막에 meta 요약을 주석으로 첨부.

토큰 효율: JSON 원본 대비 약 1/3 수준.

사용:
    python scripts/serialize_candidates.py --input cand.json
    python scripts/filter_candidates.py < ctx.json | python scripts/serialize_candidates.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

INDEX_FIELDS = ["성경", "시기", "대축일", "성월", "역할", "느낌", "키워드", "곡모음집"]


def join_arr(values) -> str:
    if not values:
        return ""
    return "|".join(str(v) for v in values)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", help="filter_candidates 출력 JSON 파일")
    p.add_argument("--output", help="출력 TSV 파일")
    args = p.parse_args()

    raw = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
    data = json.loads(raw)

    meta = data.get("meta") or {}
    results = data.get("results") or {}

    out_lines: list[str] = []

    # 헤더
    cols = ["카테고리", "번호", "제목", "작곡자", "분류", "요약"] + INDEX_FIELDS + ["점수", "근거"]
    out_lines.append("\t".join(cols))

    for category in meta.get("categories") or list(results.keys()):
        for c in results.get(category, []):
            idx = c.get("색인") or {}
            row = [
                category,
                str(c.get("번호", "")),
                str(c.get("제목", "")),
                str(c.get("작곡자", "")),
                str(c.get("분류", "")),
                str(idx.get("요약", "") or ""),
            ]
            for f in INDEX_FIELDS:
                row.append(join_arr(idx.get(f) or []))
            row.append(str(c.get("점수", 0)))
            row.append(";".join(c.get("근거") or []))
            # 탭·줄바꿈 escape (TSV 안전)
            row = [v.replace("\t", " ").replace("\n", " ").replace("\r", " ") for v in row]
            out_lines.append("\t".join(row))

    # meta 주석
    out_lines.append("")
    out_lines.append(f"# date={meta.get('date')} season={meta.get('season')} feast={meta.get('feast')} month={meta.get('month')}")
    refs = "|".join(meta.get("all_refs") or [])
    kws = "|".join(meta.get("keywords") or [])
    boost = "|".join(meta.get("boost_tags") or [])
    out_lines.append(f"# refs={refs}")
    out_lines.append(f"# keywords={kws}")
    out_lines.append(f"# boost_tags={boost}")
    out_lines.append(f"# pool_after_hard={meta.get('pool_size_after_hard_filter')} recent_excluded={meta.get('recent_excluded')}")

    text = "\n".join(out_lines) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"[output] {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
