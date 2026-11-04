"""
PDF 텍스트 레이어에서 성가 가사를 추출하고 절별로 재조립.

PDF 자체의 텍스트 레이어를 사용하므로 OCR 불필요.
악보 순서대로 텍스트가 추출되므로, 절 마커(1. 2. 3.)를 기준으로 분리.
"""

import fitz

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / 'source' / '청소년청년성가집.pdf'
DATA_DIR = ROOT / 'scripts' / 'crawler' / 'data'
import re
import json
from pathlib import Path


def find_song_page(doc, song_num: int, title: str) -> int | None:
    """주어진 곡 번호와 제목에 해당하는 PDF 페이지를 찾는다."""
    # 곡 번호는 PDF 페이지에서 큰 숫자로 등장. 제목도 함께 매칭.
    # 다절 곡은 여러 페이지에 걸침 → 제목 등장 페이지를 우선.
    target_title_norm = title.strip().replace(' ', '')
    best_page = None
    best_score = -1

    for page_idx in range(doc.page_count):
        text = doc[page_idx].get_text()
        text_norm = text.replace(' ', '').replace('\n', '')
        # 제목이 통째로 들어있는지
        if target_title_norm in text_norm:
            # 페이지 상단에 번호가 있으면 더 확실
            score = 1
            # 페이지 첫 100자에 곡 번호가 있으면 가점
            head = text[:200]
            if re.search(rf'\b{song_num}\b', head):
                score += 2
            if score > best_score:
                best_score = score
                best_page = page_idx
    return best_page


def split_by_verses(raw_text: str) -> dict:
    """텍스트에서 절 마커(1. 2. 3. ...)를 찾아 절별로 분리."""
    lines = raw_text.split('\n')

    # 절 마커 위치 찾기: "1.", "2." 등으로 시작하는 청크
    verse_markers = []  # [(verse_num, line_idx), ...]
    for idx, line in enumerate(lines):
        # 공백/특수문자 제거 후 "1." "2." 시작 체크
        clean = line.strip()
        m = re.match(r'^(\d+)\.', clean)
        if m:
            verse_markers.append((int(m.group(1)), idx))

    # 절 마커가 없으면 통절로 처리
    if len(verse_markers) < 2:
        return {'통절': raw_text.strip()}

    # 절 마커 사이의 텍스트를 각 절로 분류
    verses = {}
    for i, (vnum, start) in enumerate(verse_markers):
        end = verse_markers[i + 1][1] if i + 1 < len(verse_markers) else len(lines)
        chunk = '\n'.join(lines[start:end])
        verses[f'{vnum}절'] = chunk.strip()

    return verses


def clean_lyrics(text: str) -> str:
    """가사 정리: 하이픈/단음절 분리 정비, 공백 정규화."""
    # 음표 사이 분리된 하이픈 제거 ("빛-나게-하" → "빛나게하")
    text = re.sub(r'-+', '', text)
    # 연속 공백을 하나로
    text = re.sub(r'[ \t]+', ' ', text)
    # 너무 짧은 줄은 다음 줄과 합치기 시도는 안전하게 생략
    # 빈 줄 정리
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()


def extract_song(doc, song_num: int, title: str) -> dict:
    """한 곡에 대해 PDF 페이지를 찾고 절별로 분리한 가사를 반환."""
    page_idx = find_song_page(doc, song_num, title)
    result = {
        '번호': song_num,
        '제목': title,
        'pdf_page': page_idx + 1 if page_idx is not None else None,
    }
    if page_idx is None:
        result['error'] = '페이지 찾을 수 없음'
        return result

    # 이 페이지와 혹시 다음 페이지도 (다절 곡 대응)
    text = doc[page_idx].get_text()
    # 다음 페이지에 곡 번호 바뀌기 전까지 이어질 수 있음
    if page_idx + 1 < doc.page_count:
        next_text = doc[page_idx + 1].get_text()
        # 다음 페이지에 다른 곡 번호가 시작되지 않으면 합침
        next_head = next_text[:200]
        has_new_song = bool(re.search(rf'\b{song_num + 1}\b', next_head))
        if not has_new_song:
            text += '\n' + next_text

    result['원본_텍스트'] = text
    result['절별_원본'] = split_by_verses(text)
    result['절별_정리'] = {k: clean_lyrics(v) for k, v in result['절별_원본'].items()}
    return result


def main(target_songs: list[tuple[int, str]], output_path: str):
    doc = fitz.open(str(PDF_PATH))
    results = []
    for num, title in target_songs:
        print(f"[{num:>3}] {title} 처리 중...")
        r = extract_song(doc, num, title)
        results.append(r)
    doc.close()

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_path}")


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    # 샘플 대상: 미매칭 첫 10곡
    samples = [
        (1, '가서 내 형제들에게 전하여라'),
        (2, '가자 갈릴래아로!'),
        (3, '감사해'),
        (4, '감사해요'),
        (8, '고백'),
        (11, '공동체송'),
        (12, '교사의 기도'),
        (13, '광야에서의 유혹'),
        (16, '구원자 예수 너의 사랑'),
        (19, '그 길'),
    ]
    main(samples, str(DATA_DIR / 'pdf_sample_10.json'))
