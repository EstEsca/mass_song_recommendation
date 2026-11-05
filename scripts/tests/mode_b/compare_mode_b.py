"""모드 B 회귀 테스트 (#37): 고정 컨텍스트 4주를 filter_candidates.py에 돌려
모드 A 기준 선곡이 카테고리별 top_n 후보에 몇 번째로 노출되는지 측정한다.

사용: python scripts/tests/mode_b/compare_mode_b.py [--top-n 8]
출력: 16칸(4주×4카테고리) 각각의 순위, 노출률, 1위 일치율, 주일 간 후보 중복.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FILTER = ROOT / "scripts" / "filter_candidates.py"

def run(ctx_path: Path, top_n: int) -> dict:
    ctx = json.loads(ctx_path.read_text(encoding="utf-8")); ctx["top_n"] = top_n
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False); tmp = f.name
    out = subprocess.run([sys.executable, str(FILTER), "--input", tmp], capture_output=True, text=True, check=True).stdout
    return json.loads(out)["results"]

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--top-n", type=int, default=8); a = ap.parse_args()
    picks = json.loads((HERE / "mode_a_picks_2026-11.json").read_text(encoding="utf-8"))["picks"]
    exposed = top1 = total = 0; tops = {}
    print(f"{'주일':10} {'카테':4} {'A':>4} {'순위':>4}  상위3")
    for date, pk in picks.items():
        res = run(HERE / "contexts" / f"{date}.json", a.top_n)
        tops[date] = {c["번호"] for lst in res.values() for c in lst}
        for cat, n in pk.items():
            ids = [c["번호"] for c in res[cat]]
            rank = ids.index(n) + 1 if n in ids else None
            exposed += bool(rank); top1 += rank == 1; total += 1
            print(f"{date:10} {cat:4} {n:>4} {str(rank or '-'):>4}  {[(c['번호'], c['점수']) for c in res[cat][:3]]}")
    dates = list(picks)
    common = set.intersection(*(tops[d] for d in dates[:3]))
    print(f"\n노출(top{a.top_n}): {exposed}/{total}  1위 일치: {top1}/{total}  연중 3주일 공통 후보: {sorted(common)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
