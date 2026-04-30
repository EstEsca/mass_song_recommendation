"""1회성: data/raw/박자_조표_검수표.xlsx → data/source/곡정보.xlsx 곡목록 시트의 조표·박자 컬럼 반영.

검수표는 사용자가 수동으로 만든 진리표(495행 전수). 빈 셀·밀림 입력 검수가 핵심.

검수 항목:
  1. 번호 1..495 누락·중복
  2. 제목 정확히 일치 (밀림 감지)
  3. 조표 정수 -7..+7 / 박자 'm/n' 형식
  4. 빈 셀 — 진리표인데 빠진 곡

검수 실패 시 종료. --force-apply는 마스터 덮어쓰기 강제(--apply 와 함께).
기본은 dry-run (검수 보고만).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
TRUTH = ROOT / "data" / "raw" / "박자_조표_검수표.xlsx"
TRUTH_SHEET = "박자_자동추정"
MASTER = ROOT / "data" / "source" / "곡정보.xlsx"
MASTER_SHEET = "곡목록"

METER_RE = re.compile(r"^\d+/\d+$")


def fmt_keysig(v) -> str | None:
    if v is None or v == "":
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    if not -7 <= n <= 7:
        return None
    return "0" if n == 0 else f"{n:+d}"


def fmt_meter(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return s if METER_RE.match(s) else None


def load_truth() -> list[dict]:
    wb = load_workbook(TRUTH, data_only=True)
    ws = wb[TRUTH_SHEET]
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    idx = {h: i for i, h in enumerate(headers)}
    for need in ("번호", "제목", "박자", "조표"):
        if need not in idx:
            raise SystemExit(f"검수표에 '{need}' 컬럼 없음. 헤더={headers}")
    out = []
    for r in range(2, ws.max_row + 1):
        row = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        num = row[idx["번호"]]
        if num is None or str(num).strip() == "":
            continue
        out.append(
            {
                "row": r,
                "번호": int(num),
                "제목": (row[idx["제목"]] or "").strip(),
                "박자_raw": row[idx["박자"]],
                "조표_raw": row[idx["조표"]],
            }
        )
    return out


def load_master():
    wb = load_workbook(MASTER)
    ws = wb[MASTER_SHEET]
    headers = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
    for need in ("번호", "제목", "조표", "박자"):
        if need not in headers:
            raise SystemExit(f"곡정보.xlsx에 '{need}' 컬럼 없음. 헤더={list(headers)}")
    by_num = {}
    for r in range(2, ws.max_row + 1):
        v = ws.cell(row=r, column=headers["번호"]).value
        if v in (None, ""):
            continue
        try:
            n = int(float(str(v)))
        except ValueError:
            continue
        title = (ws.cell(row=r, column=headers["제목"]).value or "").strip()
        by_num[n] = {"row": r, "제목": title}
    return wb, ws, headers, by_num


def main():
    apply = "--apply" in sys.argv
    force = "--force-apply" in sys.argv

    truth = load_truth()
    wb, ws, h, master_by_num = load_master()

    issues: list[str] = []

    # 1. 번호 누락/중복
    nums = [t["번호"] for t in truth]
    if len(nums) != len(set(nums)):
        from collections import Counter

        dups = [n for n, c in Counter(nums).items() if c > 1]
        issues.append(f"진리표 번호 중복: {dups}")
    expected = set(range(1, max(len(master_by_num), max(nums)) + 1))
    missing_in_truth = sorted(set(master_by_num.keys()) - set(nums))
    extra_in_truth = sorted(set(nums) - set(master_by_num.keys()))
    if missing_in_truth:
        issues.append(f"진리표에 빠진 번호({len(missing_in_truth)}): {missing_in_truth[:20]}")
    if extra_in_truth:
        issues.append(f"마스터에 없는 번호가 진리표에 있음: {extra_in_truth}")

    # 2. 제목 일치 + 3. 형식 + 4. 빈 셀
    title_mismatch: list[tuple[int, str, str]] = []
    bad_keysig: list[tuple[int, object]] = []
    bad_meter: list[tuple[int, object]] = []
    empty_keysig: list[int] = []
    empty_meter: list[int] = []

    plan: list[tuple[int, int, str, str]] = []  # (번호, master_row, keysig_str, meter_str)

    for t in truth:
        n = t["번호"]
        m = master_by_num.get(n)
        if m is None:
            continue
        if t["제목"] != m["제목"]:
            title_mismatch.append((n, t["제목"], m["제목"]))

        ks = fmt_keysig(t["조표_raw"])
        mt = fmt_meter(t["박자_raw"])

        if t["조표_raw"] is None or str(t["조표_raw"]).strip() == "":
            empty_keysig.append(n)
        elif ks is None:
            bad_keysig.append((n, t["조표_raw"]))

        if t["박자_raw"] is None or str(t["박자_raw"]).strip() == "":
            empty_meter.append(n)
        elif mt is None:
            bad_meter.append((n, t["박자_raw"]))

        if ks is not None and mt is not None:
            plan.append((n, m["row"], ks, mt))

    if title_mismatch:
        issues.append(f"제목 불일치 (밀림 가능성) {len(title_mismatch)}건:")
        for n, t_title, m_title in title_mismatch[:30]:
            issues.append(f"  번호 {n}: 진리표='{t_title}' / 마스터='{m_title}'")
    if bad_keysig:
        issues.append(f"조표 형식 오류 {len(bad_keysig)}: {bad_keysig[:20]}")
    if bad_meter:
        issues.append(f"박자 형식 오류 {len(bad_meter)}: {bad_meter[:20]}")
    if empty_keysig:
        issues.append(f"조표 빈 셀 {len(empty_keysig)}: {empty_keysig[:30]}")
    if empty_meter:
        issues.append(f"박자 빈 셀 {len(empty_meter)}: {empty_meter[:30]}")

    print("=== 검수 결과 ===")
    print(f"진리표 행: {len(truth)} / 마스터 행: {len(master_by_num)}")
    print(f"적용 가능 (조표·박자 둘 다 유효): {len(plan)}")
    if issues:
        print("\n[문제]")
        for s in issues:
            print(s)
    else:
        print("문제 없음.")

    if not apply:
        print("\n(dry-run — 적용하려면 --apply, 문제 있어도 진행하려면 --force-apply 추가)")
        return

    if issues and not force:
        print("\n검수 문제 있음. --force-apply 없이는 적용 안 함.")
        sys.exit(2)

    keysig_col = h["조표"]
    meter_col = h["박자"]
    for _, r, ks, mt in plan:
        c1 = ws.cell(row=r, column=keysig_col)
        c1.value = ks
        c1.number_format = "@"
        c2 = ws.cell(row=r, column=meter_col)
        c2.value = mt
        c2.number_format = "@"
    wb.save(MASTER)
    print(f"\n적용 완료: {len(plan)}곡 → {MASTER}")
    print("→ python scripts/build_songs_json.py 로 songs.json 재빌드 권장")


if __name__ == "__main__":
    main()
