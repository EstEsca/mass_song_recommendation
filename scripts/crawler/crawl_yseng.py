"""
yseng.kr (칸투스 파밀리아 / 청소년성가 게시판) 크롤러.

특성:
- XpressEngine 기반 게시판. 게시글에 가사 본문이 있는 곡이 있고,
  악보·유튜브 링크만 있고 가사가 없는 곡도 있다.
- 번호 매칭이 아닌 "제목 검색 → 결과 중 제목 완전 일치 게시글" 매칭.
- SSL 자체서명 인증서라 verify=False. http:// 로 요청.

입력:
  argv[1..]: 곡 번호 리스트 (songs.json의 번호). 예: `crawl_yseng.py 32 38 39 40 41 42 44 45 46 50`
  없으면 기본적으로 songs.json에서 `가사.확보여부=False`인 곡 전체 시도 (과수집 방지를 위해 권장 X).

출력:
  scripts/crawler/data/yseng_sungga.jsonl
  각 줄: {번호, 제목, 작곡자, document_srl, url, 가사, 매칭방식, 수집시각}
  또는 미스 기록: {번호, 제목, document_srl, 실패원인}
"""
from __future__ import annotations

import json
import re
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from _merge import (
    load_songs, save_songs, should_skip, apply_lyrics, print_report,
)

# 기본은 http (자체서명 인증서 때문). 프록시 환경 등에서 https가 필요하면
#   YSENG_BASE=https://yseng.kr YSENG_CAFILE=<서버 인증서 PEM> 으로 실행한다.
# YSENG_CAFILE이 주어지면 그 인증서에 **핀 고정**해 검증한다(CERT_NONE보다 안전).
BASE = os.environ.get("YSENG_BASE", "http://yseng.kr")
SEARCH_URL = BASE + "/xe/?mid=sungga&search_target=title&search_keyword={kw}&page={page}"
DOC_URL = BASE + "/xe/sungga/{srl}"
USER_AGENT = "SungaLiturgyBot/1.0 (Korean Catholic liturgy; non-commercial)"
DELAY_SEC = 1.2
MAX_SEARCH_PAGES = 3
MIN_KOREAN_CHARS = 60  # 가사 판별 임계치
SOURCE_ID = "yseng"

ROOT = Path(__file__).parent.parent.parent
SONGS_JSON = ROOT / "data" / "songs.json"
OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "yseng_sungga.jsonl"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# 인증서 핀 고정: YSENG_PIN_SHA256=<서버 인증서 SHA-256 지문(콜론 없이)> 를 주면
# 연결마다 서버 인증서 지문을 대조하고 불일치 시 연결을 끊는다.
# (서버 인증서가 CA 플래그 없는 자체서명 leaf라 cafile 방식은 쓸 수 없음)
_PIN = (os.environ.get("YSENG_PIN_SHA256") or "").replace(":", "").lower()
if _PIN:
    import hashlib
    import http.client

    class _PinnedHTTPSConnection(http.client.HTTPSConnection):
        def connect(self):
            super().connect()
            der = self.sock.getpeercert(binary_form=True)
            fp = hashlib.sha256(der).hexdigest()
            if fp != _PIN:
                self.close()
                raise ssl.SSLError(f"certificate pin mismatch: {fp[:16]}... != {_PIN[:16]}...")

    class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(lambda host, **kw: _PinnedHTTPSConnection(host, context=SSL_CTX, **kw), req)

    urllib.request.install_opener(urllib.request.build_opener(_PinnedHTTPSHandler()))


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def strip_html(html: str) -> str:
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</p>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", html)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&#39;", "'").replace("&quot;", '"'))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def search_candidates(title: str) -> list[tuple[str, str]]:
    """제목 검색. 모든 페이지에서 결과 수집. [(document_srl, result_title), ...]"""
    seen = set()
    out = []
    q = urllib.parse.quote(title)
    for page in range(1, MAX_SEARCH_PAGES + 1):
        html = fetch(SEARCH_URL.format(kw=q, page=page))
        rows = re.findall(
            r'href="/xe/\?mid=sungga&amp;[^"]*document_srl=(\d+)[^"]*"[^>]*>([^<]+)</a>',
            html,
        )
        new_this_page = 0
        for srl, rtitle in rows:
            rtitle = rtitle.strip()
            if srl in seen:
                continue
            # 공지성 링크 제거
            if "유튜브 공개 성가" in rtitle or "성가 목록" in rtitle:
                continue
            seen.add(srl)
            out.append((srl, rtitle))
            new_this_page += 1
        if new_this_page == 0:
            break
        time.sleep(0.3)
    return out


def _norm_title_key(s: str) -> str:
    return (s.strip().replace(" ", "").replace("-", "").replace("!", "")
             .replace(".", "").replace(",", "").replace("'", "").lower())


def pick_best(title: str, candidates: list[tuple[str, str]],
              fuzzy: bool = False) -> tuple[str, str, str] | None:
    """제목 완전 일치 우선. fuzzy=True면 후보 제목이 1종(정규화 후)일 때만 근사 채택.
    반환: (srl, matched_title, 매칭방식) 또는 None."""
    exact = [c for c in candidates if c[1].strip() == title.strip()]
    if exact:
        return (*exact[0], "제목완전일치")
    if fuzzy and candidates:
        unique_keys = {_norm_title_key(c[1]) for c in candidates}
        if len(unique_keys) == 1:
            return (*candidates[0], "제목근사일치")
    return None


def extract_body(html: str) -> str:
    m = re.search(r"<!--BeforeDocument\(\d+,\d+\)-->(.*?)<!--AfterDocument", html, re.S)
    return strip_html(m.group(1)) if m else ""


def has_real_lyrics(text: str) -> bool:
    if len(re.findall(r"[가-힣]", text)) < MIN_KOREAN_CHARS:
        return False
    lyric_lines = [ln for ln in text.splitlines()
                   if ln.strip() and "http" not in ln and len(ln.strip()) >= 4]
    return sum(1 for ln in lyric_lines if len(re.findall(r"[가-힣]", ln)) >= 4) >= 4


def clean_lyrics(text: str) -> str:
    """악보/영상/카페 링크 섹션 제거, 본문만 남김."""
    lines = text.splitlines()
    kept = []
    for ln in lines:
        s = ln.strip()
        if not s:
            kept.append("")
            continue
        if "http" in s:  # 링크 줄 제거
            continue
        # 섹션 헤더(악보, 반주, 파트, 유튜브 등) 제거
        if re.fullmatch(r"(악보|반주 ?음원|파트 ?음원|유튜브|영상|노래|연주|.*카페|.*채널)\s*[:：]?", s):
            continue
        # "이 게시물을..." 꼬리
        if s.startswith("이 게시물을"):
            continue
        kept.append(s)
    out = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def load_targets(argv: list[str]) -> list[int]:
    if argv:
        nums = []
        for a in argv:
            if "-" in a:
                lo, hi = a.split("-")
                nums.extend(range(int(lo), int(hi) + 1))
            else:
                nums.append(int(a))
        return nums
    # 기본: 가사 미확보 전체 (비권장, 로그로 경고)
    print("[warn] 인자 없음 — 가사 미확보 곡 전체 시도 (권장: 번호 범위 지정)")
    with SONGS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)
    return [int(k) for k, v in data["songs"].items()
            if not v["가사"].get("확보여부")]


def merge_into_songs_json(force: bool = False) -> dict:
    """yseng_sungga.jsonl 전체를 songs.json에 번호 매칭으로 병합."""
    if not OUTPUT_FILE.exists():
        print(f"[merge] {OUTPUT_FILE} 없음 — 건너뜀")
        return {}
    data = load_songs()
    songs = data["songs"]
    counts = {"updated": 0, "skipped_user": 0, "skipped_other": 0, "no_match": 0}
    with OUTPUT_FILE.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            lyrics = rec.get("가사")
            if not lyrics:
                continue  # 실패 레코드
            num = str(rec.get("번호"))
            if num not in songs:
                counts["no_match"] += 1
                continue
            entry = songs[num]
            reason = should_skip(entry, SOURCE_ID, force)
            if reason == "사용자수정시각 있음":
                counts["skipped_user"] += 1
                continue
            if reason and "다른 소스" in reason:
                counts["skipped_other"] += 1
                continue
            ext = ("yseng_document_srl", rec.get("document_srl"))
            apply_lyrics(entry, SOURCE_ID, lyrics, rec.get("url"), ext)
            counts["updated"] += 1
    save_songs(data)
    print_report(SOURCE_ID, counts)
    return counts


def parse_args(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("numbers", nargs="*", help="곡 번호 또는 범위 (예: 30-50 32 38)")
    p.add_argument("--legacy-merge", action="store_true",
                   help="[DEPRECATED — v2 미대응] 옛 v1 _merge 경로로 songs.json에 병합. v2에서는 결과가 망가지므로 사용 금지.")
    p.add_argument("--merge-only", action="store_true",
                   help="[DEPRECATED] 크롤링 없이 옛 병합만. v2 미대응.")
    p.add_argument("--force", action="store_true",
                   help="(legacy-merge용) 보호 무시")
    p.add_argument("--fuzzy", action="store_true",
                   help="제목 완전 일치 실패 시, 후보가 1종(정규화 후)이면 근사 채택")
    return p.parse_args(argv)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args(sys.argv[1:])
    OUTPUT_DIR.mkdir(exist_ok=True)

    if args.legacy_merge or args.merge_only:
        print(
            "⚠ --legacy-merge / --merge-only는 v2 미대응 (v1 스키마로 songs.json을 망친다).\n"
            "  v2에서는 jsonl 생성 후 다음 명령으로 곡정보.xlsx에 적용:\n"
            "      python scripts/crawler/apply_to_xlsx.py yseng\n"
            "  그 후 `python scripts/rebuild.py`로 JSON 재빌드.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    targets = load_targets(args.numbers)

    with SONGS_JSON.open(encoding="utf-8") as f:
        songs = json.load(f)["songs"]

    # resume
    already = set()
    if OUTPUT_FILE.exists():
        with OUTPUT_FILE.open(encoding="utf-8") as f:
            for ln in f:
                try:
                    d = json.loads(ln)
                    if d.get("가사"):
                        already.add(int(d["번호"]))
                except Exception:
                    pass
        print(f"[resume] 이미 수집된 {len(already)}곡 skip")

    hits = misses = errors = 0
    with OUTPUT_FILE.open("a", encoding="utf-8") as out:
        for n in targets:
            if n in already:
                continue
            s = songs.get(str(n))
            if not s:
                print(f"[{n}] songs.json에 없음")
                continue
            title = s["제목"]
            composer = s.get("작곡자") or ""
            print(f"[{n:>3}] {title} / {composer}")
            try:
                cands = search_candidates(title)
                if not cands:
                    print("      · 검색 결과 없음")
                    out.write(json.dumps({"번호": n, "제목": title,
                                          "실패원인": "검색결과없음"},
                                         ensure_ascii=False) + "\n")
                    misses += 1
                    time.sleep(DELAY_SEC)
                    continue
                pick = pick_best(title, cands, fuzzy=args.fuzzy)
                if not pick:
                    sample = ", ".join(f"{c[0]}:{c[1]}" for c in cands[:3])
                    print(f"      · 완전 일치 없음 — 후보: {sample}")
                    out.write(json.dumps({"번호": n, "제목": title,
                                          "실패원인": "제목 완전 일치 없음",
                                          "후보": cands[:5]},
                                         ensure_ascii=False) + "\n")
                    misses += 1
                    time.sleep(DELAY_SEC)
                    continue
                srl, matched_title, match_mode = pick
                body = extract_body(fetch(DOC_URL.format(srl=srl)))
                if not has_real_lyrics(body):
                    print(f"      · srl={srl} 가사 본문 없음 (링크만)")
                    out.write(json.dumps({"번호": n, "제목": title,
                                          "document_srl": srl,
                                          "실패원인": "가사본문없음(링크만)"},
                                         ensure_ascii=False) + "\n")
                    misses += 1
                    time.sleep(DELAY_SEC)
                    continue
                lyrics = clean_lyrics(body)
                rec = {
                    "번호": n,
                    "제목": title,  # 색인 표 제목 (songs.json 기준)
                    "작곡자": composer,
                    "document_srl": srl,
                    "yseng_matched_title": matched_title,  # 실제 yseng 제목
                    "url": DOC_URL.format(srl=srl),
                    "매칭방식": match_mode,
                    "가사": lyrics,
                    "수집시각": datetime.now().isoformat(timespec="seconds"),
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                print(f"      ✓ srl={srl} 가사 {len(lyrics)}자")
                hits += 1
            except Exception as e:
                print(f"      × error: {e}")
                errors += 1
            time.sleep(DELAY_SEC)

    print(f"\n완료. 성공 {hits} / 실패 {misses} / 에러 {errors} → {OUTPUT_FILE}")

    print(
        "\n✅ jsonl 생성 완료. v2 적용 흐름:\n"
        "   1) python scripts/crawler/apply_to_xlsx.py yseng    # 곡정보.xlsx 가사 시트에 반영\n"
        "   2) python scripts/rebuild.py                         # songs.json/songs_index.json 재빌드"
    )


if __name__ == "__main__":
    main()
