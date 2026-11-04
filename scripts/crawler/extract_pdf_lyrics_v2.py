"""
PDF 텍스트 레이어에서 성가 가사를 위치 기반으로 추출 (v2).

핵심 알고리즘:
1. PyMuPDF로 각 글자의 (x, y) 위치를 추출
2. y 좌표로 '스태프 시스템(staff group)' 클러스터링 (큰 간격으로 분리)
3. 각 스태프 내에서 y 좌표별로 '절(verse row)' 구분 (작은 간격)
4. 각 절 행은 x 좌표 순으로 정렬하여 이어붙이기
5. 모든 스태프의 1절을 이어붙이면 1절 완성
"""

import fitz

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / 'source' / '청소년청년성가집.pdf'
DATA_DIR = ROOT / 'scripts' / 'crawler' / 'data'
import re
import json
from pathlib import Path


def extract_with_positions(page) -> list[dict]:
    """페이지의 모든 텍스트 span을 위치와 함께 반환."""
    items = []
    for block in page.get_text("dict")['blocks']:
        if block['type'] != 0:
            continue
        for line in block['lines']:
            for span in line['spans']:
                text = span['text']
                if not text.strip():
                    continue
                bbox = span['bbox']
                items.append({
                    'text': text,
                    'x': bbox[0],
                    'y': bbox[1],
                    'w': bbox[2] - bbox[0],
                    'h': bbox[3] - bbox[1],
                    'font_size': span.get('size', 0),
                })
    return items


def cluster_y_bands(items: list[dict], gap_threshold: float = 7.0) -> list[list[dict]]:
    """y 좌표가 비슷한 항목들을 같은 행(verse row)으로 묶는다."""
    if not items:
        return []
    sorted_items = sorted(items, key=lambda a: a['y'])
    bands = [[sorted_items[0]]]
    for item in sorted_items[1:]:
        last_y = bands[-1][-1]['y']
        if item['y'] - last_y <= gap_threshold:
            bands[-1].append(item)
        else:
            bands.append([item])
    return bands


def cluster_staves(bands: list[list[dict]], staff_gap: float = 35.0) -> list[list[list[dict]]]:
    """y 밴드들을 '스태프 시스템' 단위로 묶는다. 스태프 간 간격이 크다."""
    if not bands:
        return []
    staves = [[bands[0]]]
    for band in bands[1:]:
        prev_y = max(b['y'] for b in staves[-1][-1])
        cur_y = min(b['y'] for b in band)
        if cur_y - prev_y <= staff_gap:
            staves[-1].append(band)
        else:
            staves.append([band])
    return staves


def filter_lyrics_bands(staff: list[list[dict]]) -> list[list[dict]]:
    """스태프 내에서 가사로 보이는 밴드만 남기기.

    가사 밴드 특징:
    - 작은 폰트 (코드/타이틀/박자 제외)
    - 항목 수가 많음 (3개 이상, 음절 단위 배치)
    - 한글 포함
    """
    result = []
    for band in staff:
        if len(band) < 3:
            continue
        # 한글 포함 여부
        text = ''.join(s['text'] for s in band)
        has_korean = bool(re.search(r'[가-힣]', text))
        if not has_korean:
            continue
        # 폰트 크기 체크 (가사는 보통 9~11pt)
        avg_font = sum(s['font_size'] for s in band) / len(band)
        if avg_font > 15:  # 너무 크면 제목
            continue
        result.append(band)
    return result


def sort_band_by_x(band: list[dict]) -> str:
    """밴드 내 항목을 x 순으로 정렬하여 이어붙이기."""
    sorted_items = sorted(band, key=lambda a: a['x'])
    text = ''.join(s['text'] for s in sorted_items)
    # 하이픈/특수기호 정리
    text = re.sub(r'-+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def reconstruct_verses(page) -> dict:
    """페이지에서 절별 가사를 재조립."""
    items = extract_with_positions(page)
    bands = cluster_y_bands(items)
    staves = cluster_staves(bands)

    # 각 스태프에서 가사 밴드만 추출
    lyric_staves = []
    for staff in staves:
        lyric_bands = filter_lyrics_bands(staff)
        if lyric_bands:
            lyric_staves.append(lyric_bands)

    # 각 스태프 내에서 가사 밴드 수가 곧 절 수
    # 예: 1,2,3절이 있는 곡은 각 스태프에 3개 가사 밴드
    # 첫 번째 밴드 = 1절, 두 번째 = 2절, 세 번째 = 3절
    verses = {}
    max_verses = max((len(s) for s in lyric_staves), default=0)

    for v_idx in range(max_verses):
        verse_parts = []
        for staff in lyric_staves:
            if v_idx < len(staff):
                band = staff[v_idx]
                verse_parts.append(sort_band_by_x(band))
        if verse_parts:
            verses[f'{v_idx + 1}절'] = ' / '.join(verse_parts)

    return verses


def find_song_page(doc, song_num: int, title: str) -> int | None:
    target_title_norm = title.strip().replace(' ', '')
    best_page = None
    best_score = -1
    for page_idx in range(doc.page_count):
        text = doc[page_idx].get_text()
        text_norm = text.replace(' ', '').replace('\n', '')
        if target_title_norm in text_norm:
            score = 1
            head = text[:200]
            if re.search(rf'\b{song_num}\b', head):
                score += 2
            if score > best_score:
                best_score = score
                best_page = page_idx
    return best_page


def extract_song(doc, song_num: int, title: str) -> dict:
    page_idx = find_song_page(doc, song_num, title)
    result = {'번호': song_num, '제목': title, 'pdf_page': (page_idx + 1) if page_idx is not None else None}
    if page_idx is None:
        result['error'] = 'page not found'
        return result
    verses = reconstruct_verses(doc[page_idx])
    # 다음 페이지가 같은 곡의 연속일 수 있음
    if page_idx + 1 < doc.page_count:
        next_text = doc[page_idx + 1].get_text()
        head = next_text[:200]
        if not re.search(rf'\b{song_num + 1}\b', head):
            next_verses = reconstruct_verses(doc[page_idx + 1])
            for k, v in next_verses.items():
                if k in verses:
                    verses[k] = verses[k] + ' / ' + v
                else:
                    verses[k] = v
    result['절별'] = verses
    return result


def main(samples, output_path):
    doc = fitz.open(str(PDF_PATH))
    results = []
    for num, title in samples:
        print(f"[{num:>3}] {title} 처리 중...")
        r = extract_song(doc, num, title)
        results.append(r)
    doc.close()
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n결과: {output_path}")


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
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
    main(samples, str(DATA_DIR / 'pdf_sample_10_v2.json'))
