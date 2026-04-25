"""
악보 PDF 가사 추출기 v3.

개선점 (v2 대비):
1. 페이지 경계 검출: 곡 번호 + 제목 둘 다 사용
2. 코드 심볼 필터링 (A, Bb, Dm7 등)
3. 하이픈 세분 처리: 한글 사이 제거, 숫자/영문 사이 유지
4. 절 마커 ("1.", "2.") 활용
5. 로컬 신뢰도 평가 (점수 + 실패 원인)
6. 외부 호출 없음
7. songs.json 입출력

후렴 분리는 이 스킬에서 하지 않음 (별도 도구에서).
"""

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

import fitz


ROOT = Path(__file__).parent.parent.parent
PDF_PATH = ROOT / "source" / "청소년청년성가집.pdf"
SONGS_JSON = ROOT / "data" / "songs.json"
PAGE_MAPS_DIR = ROOT / "data" / "page_maps"


def load_page_map(pdf_path: Path) -> dict[int, int]:
    """PDF 파일명으로 수동 매핑 테이블 로드. {곡번호: 페이지번호(0-indexed)}."""
    map_file = PAGE_MAPS_DIR / f"{pdf_path.stem}.json"
    if not map_file.exists():
        return {}
    with map_file.open(encoding="utf-8") as f:
        data = json.load(f)
    # JSON의 페이지 번호는 1-indexed → 0-indexed로 변환
    return {int(k): v - 1 for k, v in data.get("mappings", {}).items()}


# ---------- 페이지 경계 검출 ----------

TITLE_FONT_MIN = 14.0
NUMBER_FONT_MIN = 20.0


def norm_title(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"[\s\-!.,']", "", s).lower()


def find_song_headers(page) -> list[dict]:
    """한 페이지에서 모든 '곡 헤더'(번호+제목 쌍)의 y 좌표를 찾는다."""
    numbers = []   # 큰 숫자 span
    titles = []    # 큰 한글 제목 span
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                size = span.get("size", 0)
                x0, y0 = span["bbox"][0], span["bbox"][1]
                if size >= NUMBER_FONT_MIN and text.isdigit():
                    numbers.append({"num": int(text), "x": x0, "y": y0, "size": size})
                elif size >= TITLE_FONT_MIN and re.search(r"[가-힣]", text):
                    titles.append({"text": text.strip(), "x": x0, "y": y0, "size": size})
    return {"numbers": numbers, "titles": titles}


def determine_song_ranges(page, song_titles_by_num: dict[int, str]) -> list[dict]:
    """페이지 내 각 곡의 y 범위 목록을 반환.

    Returns: [{"num": int, "title": str, "y_start": float, "y_end": float}, ...]
    """
    page_h = page.rect.height
    headers = find_song_headers(page)
    numbers = headers["numbers"]
    titles = headers["titles"]

    # 번호와 제목을 (y 좌표 근접) 기준으로 페어링
    pairings = []
    for n in numbers:
        expected = song_titles_by_num.get(n["num"], "")
        best_title = None
        best_dist = float("inf")
        for t in titles:
            # 같은 y 대 (30pt 이내)
            if abs(t["y"] - n["y"]) > 30:
                continue
            # 번호와 제목 매칭 (정규화)
            if norm_title(expected) == norm_title(t["text"]):
                dist = abs(t["y"] - n["y"])
                if dist < best_dist:
                    best_dist = dist
                    best_title = t
        if best_title is None and expected:
            # 제목만으로라도 찾기 (번호 fallback)
            for t in titles:
                if norm_title(expected) == norm_title(t["text"]):
                    best_title = t
                    break
        pairings.append({
            "num": n["num"],
            "title": (best_title["text"] if best_title else expected),
            "y_anchor": min(n["y"], best_title["y"]) if best_title else n["y"],
        })

    # 제목은 있는데 번호를 못 찾은 케이스 보충
    covered_titles = {p["title"] for p in pairings}
    for t in titles:
        if t["text"] in covered_titles:
            continue
        # 이 제목이 곡목록에 있는지
        matching_num = None
        for num, expected in song_titles_by_num.items():
            if norm_title(expected) == norm_title(t["text"]):
                matching_num = num
                break
        if matching_num:
            pairings.append({
                "num": matching_num,
                "title": t["text"],
                "y_anchor": t["y"],
            })

    pairings.sort(key=lambda p: p["y_anchor"])

    # 각 곡의 y 범위 결정
    ranges = []
    for i, p in enumerate(pairings):
        y_start = p["y_anchor"] - 5  # 헤더 포함 약간 위
        y_end = (pairings[i + 1]["y_anchor"] - 5) if i + 1 < len(pairings) else page_h
        ranges.append({
            "num": p["num"],
            "title": p["title"],
            "y_start": y_start,
            "y_end": y_end,
            "boundary_detected": True,  # 경계 검출 성공
        })
    return ranges


# ---------- 코드 심볼 필터 ----------

# 예: A, Am, Bb, C#7, Dm7, F#m, G7/D, Asus4, Bbm7sus4
CHORD_RE = re.compile(
    r"^[A-G][#b♯♭]?(m|M|maj|min|sus|dim|aug|add)?(2|4|5|6|7|9|11|13)?(sus[0-9]?)?(/[A-G][#b♯♭]?)?$"
)


def is_chord_symbol(text: str) -> bool:
    t = text.strip()
    if not t or len(t) > 10:
        return False
    return bool(CHORD_RE.match(t))


# ---------- 텍스트 추출 & 클러스터링 ----------

def extract_spans_in_range(page, y_start: float, y_end: float) -> list[dict]:
    """지정된 y 범위 내 span만 수집."""
    items = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"]
                if not text.strip():
                    continue
                bbox = span["bbox"]
                x, y = bbox[0], bbox[1]
                if y < y_start or y > y_end:
                    continue
                items.append({
                    "text": text,
                    "x": x,
                    "y": y,
                    "w": bbox[2] - bbox[0],
                    "h": bbox[3] - bbox[1],
                    "font_size": span.get("size", 0),
                })
    return items


def cluster_y_bands(items: list[dict], gap: float = 7.0) -> list[list[dict]]:
    if not items:
        return []
    sorted_items = sorted(items, key=lambda a: a["y"])
    bands = [[sorted_items[0]]]
    for item in sorted_items[1:]:
        last_y = bands[-1][-1]["y"]
        if item["y"] - last_y <= gap:
            bands[-1].append(item)
        else:
            bands.append([item])
    return bands


def cluster_staves(bands: list[list[dict]], staff_gap: float = 35.0) -> list[list[list[dict]]]:
    if not bands:
        return []
    staves = [[bands[0]]]
    for band in bands[1:]:
        prev_y = max(b["y"] for b in staves[-1][-1])
        cur_y = min(b["y"] for b in band)
        if cur_y - prev_y <= staff_gap:
            staves[-1].append(band)
        else:
            staves.append([band])
    return staves


def filter_lyrics_bands(staff: list[list[dict]]) -> list[list[dict]]:
    """스태프 내에서 가사로 보이는 밴드만.

    - 한글 포함
    - 작은 폰트 (≤ 15pt, 제목/타이틀 제외)
    - 항목 수 ≥ 3
    """
    result = []
    for band in staff:
        if len(band) < 3:
            continue
        has_korean = any(re.search(r"[가-힣]", s["text"]) for s in band)
        if not has_korean:
            continue
        avg_font = sum(s["font_size"] for s in band) / len(band)
        if avg_font > 15:
            continue
        result.append(band)
    return result


def remove_chord_spans(band: list[dict]) -> list[dict]:
    """밴드에서 코드 심볼 span 제거."""
    return [s for s in band if not is_chord_symbol(s["text"])]


def filter_lyrics_bands_relaxed(staff: list[list[dict]]) -> list[list[dict]]:
    """완화된 가사 밴드 필터. span ≥ 1, 폰트 ≤ 20, 한글 1자 이상."""
    result = []
    for band in staff:
        if len(band) < 1:
            continue
        has_korean = any(re.search(r"[가-힣]", s["text"]) for s in band)
        if not has_korean:
            continue
        avg_font = sum(s["font_size"] for s in band) / len(band)
        if avg_font > 20:
            continue
        result.append(band)
    return result


COPYRIGHT_PATTERNS = re.compile(
    r"(Copyright|All\s*rights?\s*reserved|Used\s*by\s*perm|Administered|Holymusic|CopyCare|Copylght)",
    re.IGNORECASE,
)


def extract_raw_fallback(page, y_start: float = 0, y_end: float = 9999) -> dict:
    """페이지 전체 텍스트에서 가사를 추출하는 최종 fallback."""
    text = page.get_text()
    lines = text.split("\n")
    lyrics_lines = []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue
        # 제목, 작곡자, Copyright, 코드만 있는 줄 제거
        if COPYRIGHT_PATTERNS.search(line):
            continue
        # 순수 숫자/영문만인 줄 제거
        if not re.search(r"[가-힣]", line):
            continue
        # 코드 심볼만 있는 줄 제거
        tokens = line.split()
        non_chord = [t for t in tokens if not CHORD_RE.match(t.strip(".,;:!?"))]
        if not non_chord:
            continue
        lyrics_lines.append(" ".join(non_chord))

    if lyrics_lines:
        combined = " ".join(lyrics_lines)
        return {"verses": {"1절": smart_hyphen_cleanup(combined)}, "marker_count": 0}
    return {"verses": {}, "marker_count": 0}


# ---------- 하이픈 처리 ----------

def smart_hyphen_cleanup(text: str) -> str:
    """한글 음절 사이 하이픈은 제거, 숫자/영문 사이는 유지."""
    # 한글-한글 사이 하이픈 제거
    text = re.sub(r"([가-힣])-+([가-힣])", r"\1\2", text)
    # 한글-공백-한글 패턴의 하이픈(공백 포함 표기) 처리
    text = re.sub(r"([가-힣])\s*-\s*([가-힣])", r"\1\2", text)
    # 연속 공백 축소
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------- 밴드 → 텍스트 ----------

def band_to_text(band: list[dict]) -> str:
    """밴드 내 span을 x 좌표 순으로 이어붙이되, x-gap이 크면 띄어쓰기 삽입."""
    if not band:
        return ""
    filtered = remove_chord_spans(band)
    if not filtered:
        return ""
    filtered.sort(key=lambda s: s["x"])

    # 평균 글자 폭 계산 (띄어쓰기 기준으로 사용)
    char_widths = []
    for s in filtered:
        text_len = max(len(s["text"]), 1)
        char_widths.append(s["w"] / text_len)
    avg_char_w = sum(char_widths) / len(char_widths) if char_widths else 5.0

    # span 간 x-gap이 평균 글자 폭의 1.5배 이상이면 띄어쓰기 삽입
    parts = [filtered[0]["text"]]
    for i in range(1, len(filtered)):
        prev = filtered[i - 1]
        curr = filtered[i]
        gap = curr["x"] - (prev["x"] + prev["w"])
        if gap > avg_char_w * 1.5:
            parts.append(" ")
        parts.append(curr["text"])

    raw = "".join(parts)
    return smart_hyphen_cleanup(raw)


# ---------- 절 마커 활용 ----------

VERSE_MARKER_RE = re.compile(r"^(\d+)\s*\.")


def detect_verse_number(band: list[dict]) -> int | None:
    """밴드 첫 span이 '1.', '2.' 형태면 해당 절 번호 반환."""
    if not band:
        return None
    first = sorted(band, key=lambda s: s["x"])[0]["text"].strip()
    m = VERSE_MARKER_RE.match(first)
    if m:
        return int(m.group(1))
    return None


# ---------- 곡 범위 → 절별 재조립 ----------

def reconstruct_verses_in_range(page, y_start: float, y_end: float) -> dict:
    items = extract_spans_in_range(page, y_start, y_end)
    bands = cluster_y_bands(items)
    staves = cluster_staves(bands)

    # 각 스태프의 가사 밴드만 추출
    lyric_staves = []
    for staff in staves:
        lb = filter_lyrics_bands(staff)
        if lb:
            lyric_staves.append(lb)

    if not lyric_staves:
        # Fallback: 완화된 필터로 재시도
        for staff in staves:
            lb = filter_lyrics_bands_relaxed(staff)
            if lb:
                lyric_staves.append(lb)

    if not lyric_staves:
        return {"verses": {}, "marker_count": 0}

    # 절 마커로 절 번호 추정
    marker_count = 0
    for staff in lyric_staves:
        for band in staff:
            if detect_verse_number(band) is not None:
                marker_count += 1

    # 각 스태프에서 n번째 가사 밴드 = n절
    # (마커가 있으면 마커 우선, 없으면 순서대로)
    max_verses = max(len(s) for s in lyric_staves)
    verses = {}
    for v_idx in range(max_verses):
        verse_parts = []
        for staff in lyric_staves:
            if v_idx < len(staff):
                band = staff[v_idx]
                # 마커가 있으면 그 절 번호 확인 (충돌 시 마커 우선)
                detected = detect_verse_number(band)
                text = band_to_text(band)
                verse_parts.append((detected, text))
        # 마커로 그룹핑 (있으면)
        marker_nums = [d for d, _ in verse_parts if d is not None]
        if marker_nums:
            # 대표 마커 번호 사용
            verse_num = statistics.mode(marker_nums)
        else:
            verse_num = v_idx + 1
        combined = " / ".join(t for _, t in verse_parts if t.strip())
        key = f"{verse_num}절"
        if key in verses:
            verses[key] += " / " + combined
        else:
            verses[key] = combined

    return {"verses": verses, "marker_count": marker_count}


# ---------- 로컬 신뢰도 평가 ----------

COPYRIGHT_KEYWORDS = ["Copyright", "All rights reserved", "Used by permission", "Administered"]


def score_korean_ratio(text: str) -> float:
    if not text:
        return 0.0
    total = len(text)
    korean = len(re.findall(r"[가-힣]", text))
    return korean / max(total, 1)


def score_chord_residual(text: str) -> float:
    """가사에 남은 코드 심볼 잔존 비율 (낮을수록 좋음; 점수는 1-비율)."""
    tokens = re.findall(r"[A-Za-z#b♯♭/0-9]+", text)
    if not tokens:
        return 1.0
    chord_count = sum(1 for t in tokens if is_chord_symbol(t))
    return 1.0 - (chord_count / len(tokens))


def score_special_char(text: str) -> float:
    """특수문자 비율 (낮을수록 좋음; 점수는 1-비율)."""
    if not text:
        return 1.0
    special = len(re.findall(r"[^\w가-힣\s.,!?'-]", text))
    return 1.0 - (special / max(len(text), 1))


def score_copyright(text: str) -> float:
    for kw in COPYRIGHT_KEYWORDS:
        if kw.lower() in text.lower():
            return 0.0
    return 1.0


def compute_confidence(verses: dict, raw_text: str, marker_count: int,
                       expected_title: str, page_text: str, boundary_ok: bool) -> dict:
    """신뢰도 점수 + 등급 + 실패 원인."""
    indicators = {}

    # S 지표 (구조)
    n_verses = len(verses)
    indicators["S1_절개수"] = 1.0 if n_verses >= 2 else (0.7 if n_verses == 1 else 0.0)

    if n_verses >= 2:
        lens = [len(v) for v in verses.values()]
        mean = statistics.mean(lens)
        if mean > 0:
            stdev = statistics.stdev(lens) if len(lens) > 1 else 0
            ratio = stdev / mean
            indicators["S2_절길이편차"] = max(0.0, 1.0 - ratio)
        else:
            indicators["S2_절길이편차"] = 0.0
    else:
        indicators["S2_절길이편차"] = 1.0

    indicators["S3_마커일치"] = 1.0 if (marker_count == 0 or marker_count == n_verses) else 0.5
    indicators["S4_경계검출"] = 1.0 if boundary_ok else 0.5

    # C 지표 (내용)
    all_text = " ".join(verses.values())
    indicators["C1_한글비율"] = score_korean_ratio(all_text)
    indicators["C2_코드잔존"] = score_chord_residual(all_text)
    indicators["C3_특수문자"] = score_special_char(all_text)
    indicators["C4_저작권혼입"] = score_copyright(all_text)
    indicators["C5_제목일치"] = 1.0 if norm_title(expected_title) in norm_title(page_text) else 0.5

    # 가중 평균 (S: 0.4 / C: 0.6)
    s_keys = [k for k in indicators if k.startswith("S")]
    c_keys = [k for k in indicators if k.startswith("C")]
    s_avg = sum(indicators[k] for k in s_keys) / len(s_keys)
    c_avg = sum(indicators[k] for k in c_keys) / len(c_keys)
    score = round(0.4 * s_avg + 0.6 * c_avg, 3)

    if score >= 0.85:
        grade = "높음"
    elif score >= 0.70:
        grade = "중상"
    elif score >= 0.50:
        grade = "중"
    else:
        grade = "낮음"

    # 실패 원인: 값이 0.7 미만인 지표 상위 3개
    reasons = sorted(
        [(k, v) for k, v in indicators.items() if v < 0.7],
        key=lambda x: x[1],
    )[:3]
    reason_labels = {
        "S1_절개수": "절 개수 부족",
        "S2_절길이편차": "절 길이 편차 큼",
        "S3_마커일치": "절 마커 불일치",
        "S4_경계검출": "페이지 경계 감지 실패",
        "C1_한글비율": "한글 비율 낮음",
        "C2_코드잔존": "코드 심볼 잔존",
        "C3_특수문자": "특수문자 과다",
        "C4_저작권혼입": "Copyright 문구 혼입",
        "C5_제목일치": "제목 페이지 불일치",
    }
    failure_reasons = [reason_labels.get(k, k) for k, _ in reasons]

    return {
        "점수": score,
        "등급": grade,
        "세부지표": indicators,
        "실패원인": failure_reasons,
    }


# ---------- 곡 하나 추출 ----------

def find_page_for_song(doc, num: int, title: str,
                       page_map: dict[int, int] | None = None) -> tuple[int | None, str]:
    """곡이 시작되는 PDF 페이지 인덱스 + 페이지 전체 텍스트 반환.

    탐색 순서: 수동 매핑 → 제목+번호 → 제목만 → 번호 레이블 → 키워드
    """
    # 1) 수동 매핑 테이블
    if page_map and num in page_map:
        pi = page_map[num]
        if 0 <= pi < doc.page_count:
            return pi, doc[pi].get_text()

    # 2) 제목 정규화 + 번호 확인
    target = norm_title(title)
    for page_idx in range(doc.page_count):
        text = doc[page_idx].get_text()
        if target in norm_title(text):
            head = text[:300]
            if re.search(rf"\b{num}\b", head):
                return page_idx, text

    # 3) 제목만으로
    for page_idx in range(doc.page_count):
        text = doc[page_idx].get_text()
        if target in norm_title(text):
            return page_idx, text

    # 4) 곡 번호 레이블 (큰 폰트)로 탐색
    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    sz = span.get("size", 0)
                    if t == str(num) and sz >= 18:
                        return page_idx, page.get_text()

    # 5) 키워드 매칭 (제목의 핵심 단어 2개 이상)
    keywords = [w for w in title.split() if len(w) >= 2][:3]
    if keywords:
        for page_idx in range(doc.page_count):
            text = doc[page_idx].get_text()
            if all(kw in text for kw in keywords):
                return page_idx, text

    return None, ""


def extract_song(doc, num: int, title: str, song_titles_by_num: dict,
                 page_map: dict[int, int] | None = None) -> dict:
    page_idx, page_text = find_page_for_song(doc, num, title, page_map)
    if page_idx is None:
        return {
            "번호": num,
            "제목": title,
            "pdf_page": None,
            "error": "page not found",
            "가사": {
                "본문": None,
                "절별": None,
                "절구조": None,
            },
            "신뢰도": {
                "점수": 0.0,
                "등급": "낮음",
                "세부지표": {},
                "실패원인": ["페이지 찾기 실패"],
            },
        }

    page = doc[page_idx]
    ranges = determine_song_ranges(page, song_titles_by_num)
    my_range = next((r for r in ranges if r["num"] == num), None)
    boundary_ok = my_range is not None

    if my_range is None:
        # 경계 검출 실패 → 페이지 전체 사용
        my_range = {"y_start": 0, "y_end": page.rect.height}

    result = reconstruct_verses_in_range(page, my_range["y_start"], my_range["y_end"])
    verses = result["verses"]
    marker_count = result["marker_count"]

    # 3단계 fallback: 정상 필터 실패 시 → raw fallback
    if not verses:
        raw_result = extract_raw_fallback(page, my_range["y_start"], my_range["y_end"])
        verses = raw_result["verses"]
        marker_count = raw_result["marker_count"]

    # 다음 페이지로 이어지는지 확인 (같은 곡의 연속)
    if page_idx + 1 < doc.page_count:
        next_page = doc[page_idx + 1]
        next_ranges = determine_song_ranges(next_page, song_titles_by_num)
        # 다음 페이지 최상단이 다른 곡으로 시작하는지
        if next_ranges:
            first_song = next_ranges[0]
            if first_song["num"] != num:
                # 다음 곡이 시작됨 → 현재 곡은 여기서 끝
                pass
            else:
                # 같은 곡 연속 → 다음 페이지도 포함
                next_result = reconstruct_verses_in_range(
                    next_page, first_song["y_start"], first_song["y_end"]
                )
                for k, v in next_result["verses"].items():
                    if k in verses:
                        verses[k] += " / " + v
                    else:
                        verses[k] = v

    # 절구조 문자열
    verse_keys = sorted(verses.keys(), key=lambda k: (
        int(re.match(r"(\d+)", k).group(1)) if re.match(r"\d", k) else 99
    ))
    절구조 = "-".join(k.replace("절", "") for k in verse_keys) or "통절"

    # 본문 플레인텍스트 (절 간 공백줄)
    본문 = "\n\n".join(f"[{k}]\n{verses[k]}" for k in verse_keys) if verses else None

    신뢰도 = compute_confidence(
        verses=verses,
        raw_text=본문 or "",
        marker_count=marker_count,
        expected_title=title,
        page_text=page_text,
        boundary_ok=boundary_ok,
    )

    return {
        "번호": num,
        "제목": title,
        "pdf_page": page_idx + 1,
        "가사": {
            "본문": 본문,
            "절별": verses if verses else None,
            "절구조": 절구조,
        },
        "신뢰도": 신뢰도,
    }


# ---------- 메인 실행 ----------

def load_songs_json():
    with SONGS_JSON.open(encoding="utf-8") as f:
        return json.load(f)


def save_songs_json(data):
    from datetime import date
    data["metadata"]["updated"] = date.today().isoformat()
    with SONGS_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run(target_nums: list[int], write: bool = True):
    songs_data = load_songs_json()
    songs = songs_data["songs"]
    song_titles_by_num = {int(k): v["제목"] for k, v in songs.items()}

    doc = fitz.open(PDF_PATH)
    page_map = load_page_map(PDF_PATH)
    results = []
    for num in target_nums:
        if str(num) not in songs:
            print(f"[{num:>3}] 곡목록에 없음")
            continue
        title = songs[str(num)]["제목"]
        print(f"[{num:>3}] {title} ...", end=" ")
        r = extract_song(doc, num, title, song_titles_by_num, page_map)
        results.append(r)
        print(f"pdf_page={r['pdf_page']} / 신뢰도={r['신뢰도']['등급']} ({r['신뢰도']['점수']})")

        if write:
            entry = songs[str(num)]
            # 기존에 가사 확보된 곡이면 덮어쓰지 않음 (maria 가사 보호)
            if entry["가사"].get("확보여부"):
                continue
            if r["가사"]["본문"]:
                entry["가사"]["확보여부"] = True
                entry["가사"]["본문"] = r["가사"]["본문"]
                entry["가사"]["절별"] = r["가사"]["절별"]
                entry["가사"]["절구조"] = r["가사"]["절구조"]
                entry["가사"]["출처"] = "PDF추출(v3)"
            entry["신뢰도"] = r["신뢰도"]

    doc.close()

    if write:
        # lyrics_count 재집계
        lyrics_count = sum(1 for s in songs.values() if s["가사"]["확보여부"])
        songs_data["metadata"]["lyrics_count"] = lyrics_count
        save_songs_json(songs_data)
        print(f"\nsongs.json 갱신 완료. 가사 확보 곡: {lyrics_count}")
    return results


def parse_target(arg: str, all_nums: list[int]) -> list[int]:
    """인자 파싱: '1', '1-10', '1,5,7', '전부' 등."""
    arg = arg.strip()
    if arg in ("all", "전부"):
        return all_nums
    if "," in arg:
        nums = []
        for part in arg.split(","):
            nums.extend(parse_target(part, all_nums))
        return sorted(set(nums))
    if "-" in arg or "~" in arg:
        arg = arg.replace("~", "-")
        a, b = arg.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(arg)]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="곡 번호/범위/전부 (예: 5, 1-10, 전부)")
    parser.add_argument("--no-write", action="store_true", help="songs.json에 쓰지 않음")
    parser.add_argument("--output", help="별도 JSON 출력 경로")
    args = parser.parse_args()

    data = load_songs_json()
    all_nums = sorted(int(k) for k in data["songs"].keys())
    targets = parse_target(args.target, all_nums)

    results = run(targets, write=(not args.no_write))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"결과도 {args.output}에 저장")


if __name__ == "__main__":
    main()
