"""
Round-trip 검증:
  현재 songs.json (v2) ↔ 곡정보.xlsx ↔ build_songs_json.py 재빌드 결과

절차:
  1. 빌드 전 songs.json 로드 → before
  2. build_songs_json.py 실행
  3. 빌드 후 songs.json 로드 → after
  4. songs 필드 비교 (metadata는 built_at 등이 달라지므로 제외)
"""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SONGS = ROOT / "data" / "songs.json"

# 1) before
with SONGS.open(encoding="utf-8") as f:
    before = json.load(f)

# 2) build 실행
result = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "build_songs_json.py")],
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print(result.stdout)
if result.returncode != 0:
    print("STDERR:", result.stderr)
    raise SystemExit("build 실패")

# 3) after
with SONGS.open(encoding="utf-8") as f:
    after = json.load(f)

# 4) 비교
def compare(a: dict, b: dict, path: str = "", diffs: list = None) -> list:
    if diffs is None:
        diffs = []
    if type(a) != type(b):
        diffs.append(f"{path}: type {type(a).__name__} vs {type(b).__name__}")
        return diffs
    if isinstance(a, dict):
        keys = set(a.keys()) | set(b.keys())
        for k in keys:
            if k not in a:
                diffs.append(f"{path}.{k}: only in after")
            elif k not in b:
                diffs.append(f"{path}.{k}: only in before")
            else:
                compare(a[k], b[k], f"{path}.{k}", diffs)
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{path}: list len {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            compare(x, y, f"{path}[{i}]", diffs)
    elif a != b:
        diffs.append(f"{path}: {a!r} vs {b!r}")
    return diffs

diffs = compare(before["songs"], after["songs"], "songs")

print(f"\n=== Round-trip 결과 ===")
print(f"곡 수 before={len(before['songs'])}, after={len(after['songs'])}")
print(f"songs 필드 차이: {len(diffs)}건")
for d in diffs[:20]:
    print(f"  {d}")
if len(diffs) > 20:
    print(f"  ... +{len(diffs) - 20}건")

print()
print("=== metadata 비교 (built_at·updated는 달라짐이 정상) ===")
print("before.metadata:", {k: v for k, v in before["metadata"].items()})
print("after.metadata :", {k: v for k, v in after["metadata"].items()})
