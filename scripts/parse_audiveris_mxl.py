"""Audiveris OMR 결과(MXL) 파싱 → 조표·박자 자동추정 CSV 갱신.

입력:
  data/raw/audiveris_out/sheet_NNN/*.mxl  (run_audiveris_full.py 산출)
  data/songs.json                          (번호 → 제목)

출력:
  data/raw/조표_자동추정.csv  (Audiveris 결과로 갱신, music21 병행 컬럼)
  data/raw/박자_자동추정.csv  (Audiveris 결과로 채움)

설계:
  - sheet 번호 → 곡 번호 매핑은 estimate_keysig.py와 동일 로직(find_page_for_song)
  - 같은 페이지의 첫 KeySignature·첫 TimeSignature를 채택
  - 다중 KeySig가 잡히면 first 외 alt에 기록 (전조 가능성 메모)
  - music21 결과(기존 csv)와 비교 컬럼 추가
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import fitz
from music21 import converter, key, meter

ROOT = Path(__file__).parent.parent
PDF_PATH = ROOT / "archive" / "source" / "청소년청년성가집.pdf"
SONGS_JSON = ROOT / "data" / "songs.json"
PAGE_MAP_JSON = ROOT / "data" / "page_maps" / "청소년청년성가집.json"
AUDIVERIS_OUT = ROOT / "data" / "raw" / "audiveris_out"
KEYSIG_CSV = ROOT / "data" / "raw" / "조표_자동추정.csv"
METER_CSV = ROOT / "data" / "raw" / "박자_자동추정.csv"

sys.stdout.reconfigure(encoding="utf-8")


def norm_title(s: str) -> str:
    return re.sub(r"[\s\-!.,']", "", s or "").lower()


def load_page_map() -> dict[int, int]:
    if not PAGE_MAP_JSON.exists():
        return {}
    d = json.loads(PAGE_MAP_JSON.read_text(encoding="utf-8"))
    return {int(k): v - 1 for k, v in d.get("mappings", {}).items()}


def find_page_for_song(doc, num: int, title: str, page_map: dict) -> int | None:
    """곡 번호 → PDF 페이지 인덱스 (0-based). estimate_keysig.py와 동일 로직."""
    if num in page_map:
        pi = page_map[num]
        if 0 <= pi < doc.page_count:
            return pi
    target = norm_title(title)
    for pi in range(doc.page_count):
        page = doc[pi]
        text = page.get_text()
        if target and target in norm_title(text):
            head = text[:300]
            if re.search(rf"\b{num}\b", head):
                return pi
    for pi in range(doc.page_count):
        if target and target in norm_title(doc[pi].get_text()):
            return pi
    for pi in range(doc.page_count):
        page = doc[pi]
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    if t == str(num) and span.get("size", 0) >= 18:
                        return pi
    return None


def parse_mxl(path: Path) -> dict:
    """MXL → {sharps, time_sig, sharps_alt, time_sig_alt, error}"""
    try:
        s = converter.parse(str(path))
    except Exception as e:
        return {"error": f"parse error: {e}"}
    keysigs = list(s.recurse().getElementsByClass(key.KeySignature))
    timesigs = list(s.recurse().getElementsByClass(meter.TimeSignature))
    out: dict = {"error": ""}
    if keysigs:
        out["sharps"] = int(keysigs[0].sharps)
        if len(keysigs) > 1:
            others = sorted({int(k.sharps) for k in keysigs} - {out["sharps"]})
            out["sharps_alt"] = ",".join(f"{s:+d}" for s in others)
        else:
            out["sharps_alt"] = ""
    else:
        out["sharps"] = ""
        out["sharps_alt"] = ""
    if timesigs:
        out["time_sig"] = timesigs[0].ratioString
        if len(timesigs) > 1:
            others = sorted({t.ratioString for t in timesigs} - {out["time_sig"]})
            out["time_sig_alt"] = ",".join(others)
        else:
            out["time_sig_alt"] = ""
    else:
        out["time_sig"] = ""
        out["time_sig_alt"] = ""
    return out


def load_existing_keysig() -> dict[int, dict]:
    """기존 조표 CSV 로드 (music21 결과)."""
    if not KEYSIG_CSV.exists():
        return {}
    res = {}
    for r in csv.DictReader(KEYSIG_CSV.open(encoding="utf-8-sig")):
        res[int(r["번호"])] = r
    return res


def main():
    songs = json.load(SONGS_JSON.open(encoding="utf-8"))["songs"]
    page_map = load_page_map()
    music21_prev = load_existing_keysig()

    doc = fitz.open(str(PDF_PATH))
    print(f"PDF: {doc.page_count} pages, {len(songs)} songs")

    # 곡 → 시트 → MXL 파싱
    keysig_rows = []
    meter_rows = []
    audiveris_count = 0
    cross_check = {"agree": 0, "disagree": 0, "music21_only": 0, "audiveris_only": 0}

    for num_str, song in songs.items():
        num = int(num_str)
        title = song["제목"]
        pi = find_page_for_song(doc, num, title, page_map)

        # Audiveris 시트 번호 = pi + 1 (1-based)
        audi = {"error": "no page"}
        if pi is not None:
            sheet_num = pi + 1
            sheet_dir = AUDIVERIS_OUT / f"sheet_{sheet_num:03d}"
            mxls = list(sheet_dir.glob("*.mxl")) if sheet_dir.exists() else []
            if mxls:
                audi = parse_mxl(mxls[0])
                if not audi.get("error"):
                    audiveris_count += 1
            else:
                audi = {"error": "mxl missing"}

        m21 = music21_prev.get(num, {})
        m21_sharps = m21.get("sharps", "")
        m21_conf = m21.get("conf", "")

        # 조표 결정
        a_sharps = audi.get("sharps", "")
        a_sharps_str = f"{a_sharps:+d}" if isinstance(a_sharps, int) else ""

        if a_sharps_str and m21_sharps:
            if a_sharps_str == m21_sharps:
                cross_check["agree"] += 1
                cross_note = "agree"
            else:
                cross_check["disagree"] += 1
                cross_note = f"disagree m21={m21_sharps}"
        elif a_sharps_str:
            cross_check["audiveris_only"] += 1
            cross_note = "audiveris only"
        elif m21_sharps:
            cross_check["music21_only"] += 1
            cross_note = "music21 only"
        else:
            cross_note = "neither"

        keysig_rows.append({
            "번호": num,
            "제목": title,
            "pdf_page": (pi + 1) if pi is not None else "",
            "sharps_audiveris": a_sharps_str,
            "sharps_alt_audiveris": audi.get("sharps_alt", ""),
            "sharps_music21": m21_sharps,
            "conf_music21": m21_conf,
            "교차검증": cross_note,
            "권장값": a_sharps_str or m21_sharps,
            "검토필요": "Y" if cross_note in ("disagree", "music21 only", "neither") or audi.get("sharps_alt") else "",
            "note": audi.get("error", ""),
        })

        meter_rows.append({
            "번호": num,
            "제목": title,
            "pdf_page": (pi + 1) if pi is not None else "",
            "박자": audi.get("time_sig", ""),
            "박자_alt": audi.get("time_sig_alt", ""),
            "출처": "audiveris" if audi.get("time_sig") else "",
            "검토필요": "Y" if not audi.get("time_sig") or audi.get("time_sig_alt") else "",
            "note": audi.get("error", ""),
        })

    doc.close()

    KEYSIG_CSV.parent.mkdir(parents=True, exist_ok=True)

    # 조표 csv 갱신
    with KEYSIG_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "번호", "제목", "pdf_page",
            "sharps_audiveris", "sharps_alt_audiveris",
            "sharps_music21", "conf_music21",
            "교차검증", "권장값", "검토필요", "note",
        ])
        w.writeheader()
        w.writerows(keysig_rows)

    with METER_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "번호", "제목", "pdf_page",
            "박자", "박자_alt", "출처", "검토필요", "note",
        ])
        w.writeheader()
        w.writerows(meter_rows)

    print()
    print("== Summary ==")
    print(f"  Audiveris 파싱 성공: {audiveris_count}/{len(songs)}")
    print(f"  교차검증:")
    for k, v in cross_check.items():
        print(f"    {k}: {v}")
    print(f"  meter 추출 성공: {sum(1 for r in meter_rows if r['박자'])}/{len(meter_rows)}")
    print()
    print(f"output:")
    print(f"  {KEYSIG_CSV}")
    print(f"  {METER_CSV}")


if __name__ == "__main__":
    main()
