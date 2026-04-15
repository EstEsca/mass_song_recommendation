"""
maria.catholic.or.kr 가톨릭성가 크롤러 (robots.txt 준수)

정책:
- robots.txt: /*.pdf$ 와 /root_file/ 만 차단. 성가 페이지는 허용.
- User-Agent 명시 (식별 가능)
- 요청 간 지연 (서버 부하 방지)
- 전례 사용 목적
"""

import requests
import time
import json
import re
import os
import sys
import io
from urllib.robotparser import RobotFileParser
from pathlib import Path

BASE = "https://maria.catholic.or.kr"
SEARCH_URL = f"{BASE}/sungga/search/sungga_view.asp?ctxtIndex={{num}}"
USER_AGENT = "SungaLiturgyBot/1.0 (Korean Catholic liturgy preparation; non-commercial)"
DELAY_SEC = 1.5  # 서버 부하 방지

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)


def check_robots():
    """requests로 robots.txt를 받아서 RobotFileParser에 주입 (SSL 이슈 회피)."""
    r = requests.get(f"{BASE}/robots.txt", timeout=10,
                     headers={'User-Agent': USER_AGENT})
    rp = RobotFileParser()
    rp.parse(r.text.splitlines())
    test_url = SEARCH_URL.format(num=1)
    allowed = rp.can_fetch(USER_AGENT, test_url)
    print(f"[robots.txt] Can fetch {test_url}: {allowed}")
    return allowed


def parse_page(html: str) -> dict:
    """페이지 HTML에서 성가 정보 추출."""
    def extract_td(label: str) -> str:
        # <th>label</th><td class="al">value</td> 패턴
        m = re.search(
            rf'<th[^>]*>\s*{re.escape(label)}\s*</th>\s*<td[^>]*>([^<]*)</td>',
            html
        )
        return m.group(1).strip() if m else ""

    def extract_lyrics() -> str:
        # <td class="al song_txt" colspan="5">...</td>
        m = re.search(
            r'<td[^>]*class="[^"]*song_txt[^"]*"[^>]*>(.*?)</td>',
            html, re.DOTALL
        )
        if not m:
            return ""
        raw = m.group(1)
        # HTML 엔티티와 <br> 처리
        raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.IGNORECASE)
        raw = re.sub(r'&nbsp;', ' ', raw)
        raw = re.sub(r'&amp;', '&', raw)
        raw = re.sub(r'<[^>]+>', '', raw)
        # 여러 공백/빈 줄 정리
        lines = [line.strip() for line in raw.split('\n')]
        lines = [line for line in lines if line]
        return '\n'.join(lines)

    return {
        "번호": extract_td("성가 번호"),
        "제목": extract_td("성가 제목"),
        "분류": extract_td("성가 분류"),
        "작곡가": extract_td("작곡가"),
        "작사가": extract_td("작사가"),
        "가사": extract_lyrics(),
    }


def fetch_song(session: requests.Session, num: int) -> dict | None:
    url = SEARCH_URL.format(num=num)
    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200:
            print(f"  [{num}] HTTP {r.status_code}")
            return None
        r.encoding = 'utf-8'
        data = parse_page(r.text)
        # 번호가 없으면 존재하지 않는 성가
        if not data.get("번호"):
            return None
        data["ctxtIndex"] = num
        data["url"] = url
        return data
    except Exception as e:
        print(f"  [{num}] error: {e}")
        return None


def crawl(start: int, end: int, resume: bool = True):
    # Windows 콘솔 UTF-8 출력
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    if not check_robots():
        print("robots.txt에서 금지합니다. 중단.")
        return

    session = requests.Session()
    session.headers.update({
        'User-Agent': USER_AGENT,
        'Accept-Language': 'ko-KR,ko;q=0.9',
    })

    output_file = OUTPUT_DIR / "maria_sungga.jsonl"
    existing = set()
    if resume and output_file.exists():
        with output_file.open('r', encoding='utf-8') as f:
            for line in f:
                try:
                    existing.add(json.loads(line)["ctxtIndex"])
                except:
                    pass
        print(f"[resume] 기존 {len(existing)}곡 발견, 건너뜀")

    with output_file.open('a', encoding='utf-8') as f:
        for num in range(start, end + 1):
            if num in existing:
                continue
            print(f"[{num:4d}/{end}] fetching...")
            data = fetch_song(session, num)
            if data:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
                f.flush()
                print(f"  ✓ {data.get('제목', '?')}")
            else:
                print(f"  · 없음/실패")
            time.sleep(DELAY_SEC)

    print(f"\n완료. 결과 파일: {output_file}")


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 550
    crawl(start, end)
