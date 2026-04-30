"""조표 자동 추정 — PDF 코드 심볼 추출 + music21 키 분석.

입력:
  - data/songs.json (번호 → 제목)
  - archive/source/청소년청년성가집.pdf
  - data/page_maps/청소년청년성가집.json (수동 매핑 보조)

출력:
  - data/raw/조표_자동추정.csv
    컬럼: 번호, 제목, pdf_page, sharps, mode, conf, chord_count, first_chord, last_chord, note

설계:
  - 신뢰도 conf < 0.85 또는 chord_count < 4 → 사용자 검수 권장
  - sharps는 정수: +N(샤프 N개), -N(플랫 N개), 0(다장조/가단조)
  - mode는 'major' / 'minor'
  - 추출 실패 곡(코드 0개)은 chord_count=0, sharps=빈칸으로 출력
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import fitz
from music21 import harmony, stream, duration as m21duration

ROOT = Path(__file__).parent.parent
PDF_PATH = ROOT / "archive" / "source" / "청소년청년성가집.pdf"
SONGS_JSON = ROOT / "data" / "songs.json"
PAGE_MAP_JSON = ROOT / "data" / "page_maps" / "청소년청년성가집.json"
OUTPUT_CSV = ROOT / "data" / "raw" / "조표_자동추정.csv"

# 같은 prefix가 우선 매칭되도록 길이 내림차순으로 ordered. 다만 \b 사용으로 "B"가 "Bb"로 흡수됨에 주의.
CHORD_RE = re.compile(
    r"\b("
    r"[A-G][#b♯♭]?"          # root + accidental
    r"(?:m|maj|min|sus|dim|aug|°)?"  # quality (소문자 m으로 minor)
    r"(?:\d{1,2})?"           # 7, 9, 11, 13
    r")\b"
)

# 명백히 코드가 아닌 단어를 걸러내기 위한 후처리 필터
NON_CHORD_WORDS = {"A", "I"}  # 영어 단음 a, I 같은 단어는 단독으로 등장 시 제외 (대소문자 구분)
sys.stdout.reconfigure(encoding="utf-8")


def normalize_for_music21(token: str) -> str:
    """ChordSymbol 입력 정규화.

    - 'Bb' → 'B-' (music21은 b 대신 -을 플랫으로 사용)
    - '♯'/'♭' → '#'/'-'
    - 'M' → 'maj' 변환은 ChordSymbol이 알아서 함
    """
    t = token.replace("♯", "#").replace("♭", "b")
    # Bb → B- (root 직후 b만)
    if len(t) >= 2 and t[0] in "ABCDEFG" and t[1] == "b":
        t = t[0] + "-" + t[2:]
    return t


def extract_chord_tokens(text: str) -> list[str]:
    """페이지 텍스트에서 코드 심볼 후보를 순서대로 추출."""
    raw = []
    for m in CHORD_RE.finditer(text):
        tok = m.group(1)
        if tok in NON_CHORD_WORDS:
            continue
        # 'M'으로 끝나는 maj 코드 표기는 그대로 유지
        raw.append(tok)
    return raw


def analyze_key(tokens: list[str]) -> dict:
    """코드 토큰 시퀀스 → music21 키 분석 결과."""
    if len(tokens) < 4:
        return {"ok": False, "reason": f"chord_count<4 ({len(tokens)})"}
    s = stream.Stream()
    accepted = 0
    for tok in tokens:
        try:
            ch = harmony.ChordSymbol(normalize_for_music21(tok))
            ch.duration = m21duration.Duration(1.0)
            s.append(ch)
            accepted += 1
        except Exception:
            continue
    if accepted < 4:
        return {"ok": False, "reason": f"accepted<4 ({accepted}/{len(tokens)})"}
    try:
        k = s.analyze("key")
    except Exception as e:
        return {"ok": False, "reason": f"analyze error: {e}"}
    return {
        "ok": True,
        "sharps": int(k.sharps),
        "mode": k.mode,
        "tonic": k.tonic.name,
        "conf": float(k.correlationCoefficient),
        "accepted": accepted,
    }


def norm_title(s: str) -> str:
    return re.sub(r"[\s\-!.,']", "", s or "").lower()


def find_page_for_song(doc, num: int, title: str, page_map: dict) -> int | None:
    """곡 번호 → PDF 페이지 인덱스 (0-based)."""
    if num in page_map:
        pi = page_map[num]
        if 0 <= pi < doc.page_count:
            return pi

    target = norm_title(title)

    # 제목 + 큰 폰트 번호
    for pi in range(doc.page_count):
        page = doc[pi]
        text = page.get_text()
        if target and target in norm_title(text):
            head = text[:300]
            if re.search(rf"\b{num}\b", head):
                return pi

    # 제목만
    for pi in range(doc.page_count):
        if target and target in norm_title(doc[pi].get_text()):
            return pi

    # 큰 폰트 곡 번호
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


def load_page_map() -> dict:
    if not PAGE_MAP_JSON.exists():
        return {}
    with PAGE_MAP_JSON.open(encoding="utf-8") as f:
        d = json.load(f)
    # JSON은 1-indexed → 0-indexed
    return {int(k): v - 1 for k, v in d.get("mappings", {}).items()}


def main():
    songs = json.load(SONGS_JSON.open(encoding="utf-8"))["songs"]
    page_map = load_page_map()
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(PDF_PATH))
    print(f"PDF: {PDF_PATH.name}  ({doc.page_count} pages)")
    print(f"Songs: {len(songs)}")
    print(f"Manual page map: {len(page_map)} entries")

    results = []
    progress_every = 50
    for i, (num_str, song) in enumerate(songs.items(), 1):
        num = int(num_str)
        title = song["제목"]
        pi = find_page_for_song(doc, num, title, page_map)
        if pi is None:
            results.append({
                "번호": num, "제목": title, "pdf_page": "",
                "sharps": "", "mode": "", "conf": "",
                "chord_count": 0, "first_chord": "", "last_chord": "",
                "note": "page not found",
            })
            continue

        text = doc[pi].get_text()
        tokens = extract_chord_tokens(text)

        if not tokens:
            results.append({
                "번호": num, "제목": title, "pdf_page": pi + 1,
                "sharps": "", "mode": "", "conf": "",
                "chord_count": 0, "first_chord": "", "last_chord": "",
                "note": "no chord symbols",
            })
            continue

        analysis = analyze_key(tokens)
        if not analysis["ok"]:
            results.append({
                "번호": num, "제목": title, "pdf_page": pi + 1,
                "sharps": "", "mode": "", "conf": "",
                "chord_count": len(tokens),
                "first_chord": tokens[0], "last_chord": tokens[-1],
                "note": analysis["reason"],
            })
            continue

        results.append({
            "번호": num, "제목": title, "pdf_page": pi + 1,
            "sharps": f"{analysis['sharps']:+d}",
            "mode": analysis["mode"],
            "conf": f"{analysis['conf']:.2f}",
            "chord_count": len(tokens),
            "first_chord": tokens[0],
            "last_chord": tokens[-1],
            "note": "" if analysis["conf"] >= 0.85 else "low confidence",
        })

        if i % progress_every == 0:
            print(f"  {i}/{len(songs)} processed...")

    doc.close()

    # CSV 저장
    fieldnames = ["번호", "제목", "pdf_page", "sharps", "mode", "conf",
                  "chord_count", "first_chord", "last_chord", "note"]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)

    # 요약
    n_ok = sum(1 for r in results if r["sharps"])
    n_lowconf = sum(1 for r in results if r["note"] == "low confidence")
    n_nochord = sum(1 for r in results if r["note"] == "no chord symbols")
    n_nopage = sum(1 for r in results if r["note"] == "page not found")
    n_other = sum(1 for r in results
                  if r["note"] not in ("", "low confidence", "no chord symbols", "page not found"))

    print()
    print(f"== Summary ==")
    print(f"  total:       {len(results)}")
    print(f"  estimated:   {n_ok}  ({n_ok/len(results)*100:.1f}%)")
    print(f"    high conf: {n_ok - n_lowconf}")
    print(f"    low conf:  {n_lowconf}")
    print(f"  no chords:   {n_nochord}")
    print(f"  no page:     {n_nopage}")
    print(f"  other err:   {n_other}")
    print(f"output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
