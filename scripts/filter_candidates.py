"""
filter_candidates.py

recommend-hymns 스킬의 Stage 1 후보 필터 (experimental).

입력: 주일 컨텍스트 + 카테고리 (stdin JSON 또는 --input)
출력: 카테고리별 후보 곡 + 점수·근거 (stdout JSON 또는 --output)

처리 단계:
  1. data/songs_index.json 로드
  2. 카테고리·시기·대축일·가사 유무·최근 중복으로 hard filter
  3. 카테고리별 soft scoring (성경·시기·대축일·성월·키워드·요약·역할·느낌·boost_tags)
  4. diversity 감점 (작곡자/키워드 중복)
  5. 카테고리당 top_n 산출

LLM 미호출. 순수 Python.

입력 JSON 스키마:
{
  "date": "2026-04-26",
  "season": "부활" | null,
  "feast": "부활대축일" | null,
  "month": 5 | null,
  "readings": {
    "gospel": "요한10:27-30" | null,
    "1st": "사도13:14,43-52" | null,
    "2nd": "묵시7:9,14-17" | null,
    "keywords": ["목자", "양", "영원한생명"]
  },
  "categories": ["봉헌", "성체", "파견", "묵상"],
  "exclude_recent_days": 30,
  "top_n": 8,
  "boost_tags": []
}
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "data" / "songs_index.json"
RECORDS_PATH = ROOT / "data" / "선곡기록.csv"

# 가중치 (튜닝 가능)
W_SCRIPTURE_EXACT = 10
W_SCRIPTURE_OVERLAP = 7
W_SCRIPTURE_SAME_CHAPTER = 4
W_SCRIPTURE_SAME_BOOK = 1
W_SEASON = 3
W_FEAST = 8
W_MONTH = 3
W_KEYWORD_HIT = 2
W_SUMMARY_HIT = 1   # cap 3
SUMMARY_HIT_CAP = 3
W_ROLE_EXACT = 2     # 카테고리가 색인.역할에 명시 포함된 경우
W_FEELING_HIT = 2
W_BOOST_TAG = 3      # boost_tags 매치 (색인.키워드 또는 색인.느낌)
W_DIVERSITY_COMPOSER = -3
W_DIVERSITY_KEYWORD = -2
DIVERSITY_KEYWORD_THRESHOLD = 3


# ---- 유틸 ----

def parse_verse(key: str) -> tuple[str, int, int | None, int | None] | None:
    """'마태28:16-20' → ('마태', 28, 16, 20). 형식 위반 시 None."""
    if not key:
        return None
    m = re.match(r"^([1-2]?[가-힣]+)(\d+)(?::(\d+)(?:-(\d+))?)?$", key.strip())
    if not m:
        return None
    book, ch, vs, ve = m.groups()
    ch_i = int(ch)
    vs_i = int(vs) if vs else None
    ve_i = int(ve) if ve else vs_i
    return book, ch_i, vs_i, ve_i


def scripture_max_score(song_refs: list[str], gospel_refs: list[str]) -> int:
    """곡 색인.성경과 주일 독서 구절의 최대 매칭 점수 반환."""
    if not song_refs or not gospel_refs:
        return 0
    best = 0
    for s in song_refs:
        sp = parse_verse(s)
        if not sp:
            continue
        s_book, s_ch, s_vs, s_ve = sp
        for g in gospel_refs:
            gp = parse_verse(g)
            if not gp:
                continue
            g_book, g_ch, g_vs, g_ve = gp
            if sp == gp:
                return W_SCRIPTURE_EXACT
            if s_book == g_book and s_ch == g_ch:
                # 절 범위 겹침
                if s_vs is not None and g_vs is not None:
                    if max(s_vs, g_vs) <= min(s_ve or s_vs, g_ve or g_vs):
                        best = max(best, W_SCRIPTURE_OVERLAP)
                    else:
                        best = max(best, W_SCRIPTURE_SAME_CHAPTER)
                else:
                    best = max(best, W_SCRIPTURE_SAME_CHAPTER)
            elif s_book == g_book:
                best = max(best, W_SCRIPTURE_SAME_BOOK)
    return best


def korean_tokens(text: str | None) -> set[str]:
    """2자 이상 한글 토큰 집합."""
    if not text:
        return set()
    return set(re.findall(r"[가-힣]{2,}", text))


def normalize_refs(text: str | None) -> list[str]:
    """주일 readings 항목의 텍스트('사도13:14,43-52')를 ref 리스트로 분리."""
    if not text:
        return []
    out = []
    for line in re.split(r"[\n,]", text):
        line = line.strip()
        if not line:
            continue
        # "사도13:14"·"사도13:43-52" → 같이 출현하는 경우 split 후 책 이어붙임
        if not re.match(r"^[1-2]?[가-힣]+", line):
            # 앞에 책이 없는 단편 (ex: "43-52") — 직전 책을 알 수 없으므로 skip
            continue
        out.append(line)
    return out


# ---- 선곡 기록 ----

def load_recent_records(days: int) -> set[int]:
    """선곡기록.csv에서 최근 N일 이내 사용된 곡 번호 집합."""
    if not RECORDS_PATH.exists() or days <= 0:
        return set()
    threshold = date.today() - timedelta(days=days)
    out: set[int] = set()
    with RECORDS_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                d = datetime.strptime(row["날짜"], "%Y-%m-%d").date()
            except (KeyError, ValueError):
                continue
            if d < threshold:
                continue
            try:
                out.add(int(row["번호"]))
            except (KeyError, ValueError):
                continue
    return out


# ---- 필터링 ----

def hard_filter(songs: dict, ctx: dict, recent: set[int]) -> dict[str, dict]:
    """카테고리에 무관하게 통과한 곡들 반환."""
    out = {}
    season = ctx.get("season")
    feast = ctx.get("feast")
    for num, s in songs.items():
        n = int(num)
        if n in recent:
            continue
        가사 = s.get("가사")
        # songs_index.json은 가사 필드 없음 — 가사 유무는 별도 단계에서 확인
        idx = s.get("색인") or {}
        시기들 = idx.get("시기") or []
        대축일들 = idx.get("대축일") or []
        # 시기 충돌: 곡이 특정 시기에 속하는데 현재 시기와 다르면 제외
        if 시기들 and season and season not in 시기들:
            continue
        # 대축일 충돌
        if 대축일들 and feast and feast not in 대축일들:
            continue
        out[num] = s
    return out


def category_match(s: dict, category: str) -> tuple[bool, int]:
    """카테고리 충족 여부 + 역할 정확 일치 점수 (vs 빈 배열 통과)."""
    역할들 = (s.get("색인") or {}).get("역할") or []
    if not 역할들:
        # 범용 곡 — 통과는 하되 역할 정확 점수 없음
        return True, 0
    if category in 역할들:
        return True, W_ROLE_EXACT
    return False, 0


def score_song(s: dict, category: str, ctx: dict) -> tuple[int, list[str]]:
    """곡 1개의 점수와 근거 라벨 반환."""
    score = 0
    reasons: list[str] = []
    idx = s.get("색인") or {}

    # 카테고리 적합성
    ok, role_score = category_match(s, category)
    if not ok:
        return 0, []
    if role_score:
        score += role_score
        reasons.append(f"역할={category}(+{role_score})")

    # 성경
    gospel_refs = ctx.get("_all_refs", [])
    if gospel_refs:
        sc = scripture_max_score(idx.get("성경") or [], gospel_refs)
        if sc:
            score += sc
            reasons.append(f"성경(+{sc})")

    # 시기
    season = ctx.get("season")
    if season and season in (idx.get("시기") or []):
        score += W_SEASON
        reasons.append(f"시기={season}(+{W_SEASON})")

    # 대축일
    feast = ctx.get("feast")
    if feast and feast in (idx.get("대축일") or []):
        score += W_FEAST
        reasons.append(f"대축일={feast}(+{W_FEAST})")

    # 성월
    month = ctx.get("month")
    if month is not None:
        month_str = f"{int(month)}월"
        if month_str in (idx.get("성월") or []):
            score += W_MONTH
            reasons.append(f"성월={month_str}(+{W_MONTH})")

    # 키워드
    gospel_kws = set(ctx.get("readings", {}).get("keywords") or [])
    if gospel_kws:
        song_kws = set(idx.get("키워드") or [])
        hit = gospel_kws & song_kws
        if hit:
            inc = W_KEYWORD_HIT * len(hit)
            score += inc
            reasons.append(f"키워드={','.join(sorted(hit))}(+{inc})")

    # 요약 어휘 겹침
    if gospel_kws:
        s_tokens = korean_tokens(idx.get("요약") or "")
        overlap = s_tokens & gospel_kws
        if overlap:
            inc = min(W_SUMMARY_HIT * len(overlap), SUMMARY_HIT_CAP)
            score += inc
            reasons.append(f"요약겹침={','.join(sorted(overlap))}(+{inc})")

    # 느낌 (boost가 아닌 단순 분위기 매칭은 사용자 컨텍스트 의존이라 일단 boost로 처리)

    # boost_tags
    boost_tags = set(ctx.get("boost_tags") or [])
    if boost_tags:
        kws = set(idx.get("키워드") or [])
        feels = set(idx.get("느낌") or [])
        hit = boost_tags & (kws | feels)
        if hit:
            inc = W_BOOST_TAG * len(hit)
            score += inc
            reasons.append(f"강조태그={','.join(sorted(hit))}(+{inc})")

    return score, reasons


def diversity_adjust(
    candidates: list[dict],
    selected: list[dict],
) -> list[dict]:
    """선택된 곡들과의 중복을 감점해서 재정렬 후 반환."""
    if not selected:
        return candidates
    sel_composers = {c["작곡자"] for c in selected}
    sel_keywords: set[str] = set()
    for c in selected:
        sel_keywords |= set((c.get("색인") or {}).get("키워드") or [])

    out = []
    for c in candidates:
        adj = c["점수"]
        reasons = list(c["근거"])
        if c["작곡자"] in sel_composers:
            adj += W_DIVERSITY_COMPOSER
            reasons.append(f"작곡자중복({W_DIVERSITY_COMPOSER})")
        c_kws = set((c.get("색인") or {}).get("키워드") or [])
        overlap = c_kws & sel_keywords
        if len(overlap) >= DIVERSITY_KEYWORD_THRESHOLD:
            adj += W_DIVERSITY_KEYWORD
            reasons.append(f"키워드편중({W_DIVERSITY_KEYWORD})")
        if adj <= 0:
            continue
        out.append({**c, "점수": adj, "근거": reasons})
    out.sort(key=lambda x: -x["점수"])
    return out


def filter_for_category(
    pool: dict,
    category: str,
    ctx: dict,
    top_n: int,
) -> list[dict]:
    # 1) 카테고리 충족 + 점수
    initial: list[dict] = []
    for num, s in pool.items():
        score, reasons = score_song(s, category, ctx)
        if score <= 0:
            continue
        initial.append({
            "번호": int(num),
            "제목": s.get("제목", ""),
            "작곡자": s.get("작곡자", ""),
            "분류": s.get("분류", ""),
            "색인": s.get("색인") or {},
            "점수": score,
            "근거": reasons,
        })
    initial.sort(key=lambda x: -x["점수"])

    # 2) diversity-aware greedy 선택
    selected: list[dict] = []
    pool_dyn = list(initial)
    while pool_dyn and len(selected) < top_n:
        # 매번 diversity 재계산
        pool_dyn = diversity_adjust(pool_dyn, selected)
        if not pool_dyn:
            break
        pick = pool_dyn[0]
        selected.append(pick)
        pool_dyn = pool_dyn[1:]

    return selected


# ---- main ----

def main() -> None:
    p = argparse.ArgumentParser(description="recommend-hymns Stage 1 후보 필터")
    p.add_argument("--input", help="입력 JSON 파일 (없으면 stdin)")
    p.add_argument("--output", help="출력 JSON 파일 (없으면 stdout)")
    args = p.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            ctx = json.load(f)
    else:
        ctx = json.load(sys.stdin)

    # 입력 검증
    cats = ctx.get("categories") or ["봉헌", "성체", "파견", "묵상"]
    top_n = int(ctx.get("top_n", 8))
    exclude_days = int(ctx.get("exclude_recent_days", 30))

    # 모든 readings 구절을 평탄화
    readings = ctx.get("readings") or {}
    all_refs: list[str] = []
    for k in ("gospel", "1st", "2nd"):
        all_refs += normalize_refs(readings.get(k))
    ctx["_all_refs"] = all_refs

    # 데이터 로드
    if not INDEX_PATH.exists():
        raise SystemExit(f"songs_index.json 없음: {INDEX_PATH}")
    with INDEX_PATH.open(encoding="utf-8") as f:
        index_data = json.load(f)
    songs = index_data["songs"]

    # 최근 사용 곡
    recent = load_recent_records(exclude_days)

    # Hard filter
    pool = hard_filter(songs, ctx, recent)

    # 카테고리별 결과
    out: dict[str, Any] = {
        "meta": {
            "date": ctx.get("date"),
            "season": ctx.get("season"),
            "feast": ctx.get("feast"),
            "month": ctx.get("month"),
            "all_refs": all_refs,
            "keywords": readings.get("keywords") or [],
            "categories": cats,
            "exclude_recent_days": exclude_days,
            "boost_tags": ctx.get("boost_tags") or [],
            "pool_size_after_hard_filter": len(pool),
            "recent_excluded": len(recent),
        },
        "results": {},
    }

    for cat in cats:
        out["results"][cat] = filter_for_category(pool, cat, ctx, top_n)

    payload = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"[output] {args.output}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
