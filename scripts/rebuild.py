"""
rebuild.py

xlsx → songs.json → songs_index.json을 일괄 재빌드.

사용자가 data/source/곡정보.xlsx를 편집한 뒤 실행:

    python scripts/rebuild.py

기본 모드는 무조건 둘 다 돌린다. --check 모드는 stale 여부만 확인하고
재빌드는 안 함 (CI나 사전 점검용).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "source" / "곡정보.xlsx"
SONGS = ROOT / "data" / "songs.json"
INDEX = ROOT / "data" / "songs_index.json"
SCRIPTS = ROOT / "scripts"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_sha(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return (data.get("metadata") or {}).get("built_from_sha256")
    except Exception:
        return None


def check_staleness() -> dict:
    """각 파생물이 상위 입력과 동기화돼 있는지 확인."""
    report: dict = {}

    xlsx_sha = sha256_of(XLSX) if XLSX.exists() else None
    songs_rec = load_sha(SONGS)
    songs_sha = sha256_of(SONGS) if SONGS.exists() else None
    index_rec = load_sha(INDEX)

    report["xlsx"] = {"exists": XLSX.exists(), "sha": xlsx_sha}
    report["songs.json"] = {
        "exists": SONGS.exists(),
        "built_from": songs_rec,
        "stale_vs_xlsx": xlsx_sha is not None and songs_rec != xlsx_sha,
    }
    report["songs_index.json"] = {
        "exists": INDEX.exists(),
        "built_from": index_rec,
        "stale_vs_songs": songs_sha is not None and index_rec != songs_sha,
    }
    return report


def print_report(report: dict) -> None:
    print("=== 동기화 상태 ===")
    for name, info in report.items():
        print(f"  {name}: {info}")


def run_script(script_name: str) -> None:
    script = SCRIPTS / script_name
    print(f"\n── {script_name} ──")
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"실패: {script_name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="재빌드하지 않고 동기화 상태만 확인",
    )
    args = parser.parse_args()

    if args.check:
        print_report(check_staleness())
        return

    if not XLSX.exists():
        raise SystemExit(f"xlsx 없음: {XLSX}")

    # Stage 1: xlsx → songs.json
    run_script("build_songs_json.py")
    # Stage 2: songs.json → songs_index.json
    run_script("build_song_index.py")

    print("\n=== 완료 ===")
    print_report(check_staleness())


if __name__ == "__main__":
    main()
