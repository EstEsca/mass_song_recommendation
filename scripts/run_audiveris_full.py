"""Audiveris 풀 코퍼스 OMR 실행 — sheet 단위 루프 + 체크포인팅.

PDF의 모든 시트를 1장씩 Audiveris로 OMR하여 MXL을 생성한다.
이미 처리된 시트는 건너뛴다 (재실행 안전).

산출:
  data/raw/audiveris_out/sheet_NNN/청소년청년성가집.mxl  (per sheet)
  data/raw/audiveris_out/run.log                         (진행 로그)
  data/raw/audiveris_out/_progress.json                  (체크포인트)

후속:
  scripts/parse_audiveris_mxl.py 가 위 결과를 파싱해 조표/박자 CSV를 갱신.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import fitz

ROOT = Path(__file__).parent.parent
PDF_PATH = ROOT / "archive" / "source" / "청소년청년성가집.pdf"
OUT_DIR = ROOT / "data" / "raw" / "audiveris_out"
PROGRESS_JSON = OUT_DIR / "_progress.json"
LOG_FILE = OUT_DIR / "run.log"
AUDIVERIS = "C:/Program Files/Audiveris/Audiveris.exe"

sys.stdout.reconfigure(encoding="utf-8")


def load_progress() -> dict:
    if PROGRESS_JSON.exists():
        return json.loads(PROGRESS_JSON.read_text(encoding="utf-8"))
    return {"completed": [], "failed": [], "started": None}


def save_progress(p: dict):
    PROGRESS_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_JSON.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def process_sheet(sheet_num: int) -> tuple[bool, str]:
    """Returns (success, message)."""
    sheet_dir = OUT_DIR / f"sheet_{sheet_num:03d}"
    sheet_dir.mkdir(parents=True, exist_ok=True)

    # 이미 .mxl 있으면 skip
    existing = list(sheet_dir.glob("*.mxl"))
    if existing:
        return True, f"already done ({existing[0].name})"

    cmd = [
        AUDIVERIS,
        "-batch", "-transcribe", "-export",
        "-output", str(sheet_dir),
        "-sheets", str(sheet_num),
        "--", str(PDF_PATH),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300)
    except subprocess.TimeoutExpired:
        return False, "timeout (>5min)"

    mxl_files = list(sheet_dir.glob("*.mxl"))
    if not mxl_files:
        # 마지막 stderr 일부만 로그
        tail = (r.stderr or r.stdout or "").splitlines()[-3:]
        return False, "no mxl: " + " | ".join(tail)
    return True, mxl_files[0].name


def main():
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        sys.exit(1)
    if not Path(AUDIVERIS).exists():
        print(f"ERROR: Audiveris not found at {AUDIVERIS}")
        sys.exit(1)

    doc = fitz.open(str(PDF_PATH))
    total_pages = doc.page_count
    doc.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    progress = load_progress()
    if progress["started"] is None:
        progress["started"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save_progress(progress)

    log(f"=== Audiveris full run (total {total_pages} sheets) ===")
    completed_set = set(progress["completed"])
    failed_set = set(progress["failed"])
    skip = len(completed_set)
    log(f"resuming: {skip} already done, {len(failed_set)} failed prev")

    t_start = time.time()
    for sheet_num in range(1, total_pages + 1):
        if sheet_num in completed_set:
            continue

        t0 = time.time()
        ok, msg = process_sheet(sheet_num)
        elapsed = time.time() - t0
        if ok:
            completed_set.add(sheet_num)
            failed_set.discard(sheet_num)
            log(f"  sheet {sheet_num:3d}/{total_pages}  OK  {elapsed:5.1f}s  {msg}")
        else:
            failed_set.add(sheet_num)
            log(f"  sheet {sheet_num:3d}/{total_pages}  FAIL {elapsed:5.1f}s  {msg}")

        # 5장마다 체크포인트
        if sheet_num % 5 == 0:
            progress["completed"] = sorted(completed_set)
            progress["failed"] = sorted(failed_set)
            save_progress(progress)
            done = len(completed_set)
            total_elapsed = time.time() - t_start
            avg = total_elapsed / max(done - skip, 1)
            eta = avg * (total_pages - done)
            log(f"  -- progress: {done}/{total_pages}  avg {avg:.1f}s/sheet  ETA {eta/60:.1f}min")

    progress["completed"] = sorted(completed_set)
    progress["failed"] = sorted(failed_set)
    progress["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_progress(progress)
    log(f"=== done. completed={len(completed_set)}  failed={len(failed_set)} ===")


if __name__ == "__main__":
    main()
