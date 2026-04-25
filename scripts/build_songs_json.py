"""
build_songs_json.py

data/source/곡정보.xlsx → data/songs.json

xlsx 4시트(곡목록·요약·색인·가사)를 읽어 v2 스키마로 합성한다.
xlsx 편집 후 매번 실행 (또는 scripts/rebuild.py 사용).

사람 편집은 xlsx에서만. songs.json은 이 스크립트가 덮어쓰는 파생물이다.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "source" / "곡정보.xlsx"
OUT_JSON = ROOT / "data" / "songs.json"

INDEX_KEYS = {"성경", "성월", "시기", "대축일", "역할", "느낌", "키워드", "곡모음집"}
TODAY = datetime.now().strftime("%Y-%m-%d")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _rows(ws):
    it = ws.iter_rows(values_only=True)
    next(it)  # skip header
    return it


def _num_str(v) -> str | None:
    """번호 셀 → 문자열 키. 숫자·문자열 둘 다 허용."""
    if v is None or v == "":
        return None
    # float("3.0") 같은 경우 처리, 숫자 정밀도 오염 방지
    try:
        return str(int(float(str(v))))
    except (ValueError, TypeError):
        return None


def _empty_song(num: int) -> dict:
    return {
        "번호": num,
        "제목": "",
        "작곡자": "",
        "분류": "",
        "색인": {
            "요약": "",
            "성경": [],
            "성월": [],
            "시기": [],
            "대축일": [],
            "역할": [],
            "느낌": [],
            "키워드": [],
            "곡모음집": [],
        },
        "가사": "",
    }


def build(xlsx_path: Path) -> tuple[dict, list[str]]:
    wb = load_workbook(xlsx_path, data_only=True)

    missing = [s for s in ("곡목록", "요약", "색인", "가사") if s not in wb.sheetnames]
    if missing:
        raise SystemExit(f"xlsx에 필수 시트가 없음: {missing}")

    songs: dict[str, dict] = {}
    warnings: list[str] = []

    # 1) 곡목록 — 기본 골격 생성
    for row in _rows(wb["곡목록"]):
        num_str = _num_str(row[0])
        if num_str is None:
            continue
        s = _empty_song(int(num_str))
        s["제목"] = str(row[1] or "")
        s["작곡자"] = str(row[2] or "")
        s["분류"] = str(row[3] or "")
        songs[num_str] = s

    # 2) 요약
    for row in _rows(wb["요약"]):
        num_str = _num_str(row[0])
        if num_str is None:
            continue
        if num_str not in songs:
            warnings.append(f"요약 시트에 미등록 번호 {num_str}")
            continue
        songs[num_str]["색인"]["요약"] = str(row[1] or "")

    # 3) 색인 (tall → 카테고리별 배열로 조립)
    for row in _rows(wb["색인"]):
        num_str = _num_str(row[0])
        if num_str is None:
            continue
        if num_str not in songs:
            warnings.append(f"색인 시트에 미등록 번호 {num_str}")
            continue
        type_name = str(row[1] or "").strip()
        value = str(row[2] or "").strip()
        if not type_name or not value:
            continue
        if type_name not in INDEX_KEYS:
            warnings.append(f"색인 타입 위반 [번호={num_str}]: {type_name!r}")
            continue
        arr = songs[num_str]["색인"][type_name]
        if value not in arr:  # 중복 제거 (입력 순서 유지)
            arr.append(value)

    # 4) 가사
    for row in _rows(wb["가사"]):
        num_str = _num_str(row[0])
        if num_str is None:
            continue
        if num_str not in songs:
            warnings.append(f"가사 시트에 미등록 번호 {num_str}")
            continue
        songs[num_str]["가사"] = str(row[1] or "")

    return songs, warnings


def main() -> None:
    if not XLSX.exists():
        raise SystemExit(f"xlsx 없음: {XLSX}")

    print(f"[load] {XLSX}")
    songs, warnings = build(XLSX)

    # 기존 songs.json의 metadata.created 유지
    existing_created = TODAY
    if OUT_JSON.exists():
        try:
            with OUT_JSON.open(encoding="utf-8") as f:
                old = json.load(f)
            existing_created = (old.get("metadata") or {}).get("created", TODAY)
        except Exception:
            pass

    sha = sha256_of(XLSX)
    data = {
        "metadata": {
            "schema_version": "2.0",
            "created": existing_created,
            "updated": TODAY,
            "total_songs": len(songs),
            "built_from_sha256": sha,
            "built_at": datetime.now().isoformat(timespec="seconds"),
        },
        "songs": {k: songs[k] for k in sorted(songs.keys(), key=int)},
    }

    OUT_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[build] → {OUT_JSON}")
    print(f"곡 수: {len(songs)}")
    print(f"sha256 (xlsx): {sha[:16]}…")

    if warnings:
        print(f"\n[warnings] {len(warnings)}건")
        for w in warnings[:10]:
            print(f"  - {w}")
        if len(warnings) > 10:
            print(f"  ... +{len(warnings) - 10}건")


if __name__ == "__main__":
    main()
