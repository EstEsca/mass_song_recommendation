"""songs_index.json 검증."""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path("s:/song_recommendation")
SONGS = ROOT / "data" / "songs.json"
INDEX = ROOT / "data" / "songs_index.json"


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


with SONGS.open(encoding="utf-8") as f:
    songs_data = json.load(f)
with INDEX.open(encoding="utf-8") as f:
    index_data = json.load(f)

# 1) metadata.built_from_sha256 일치 확인
expected_sha = sha256_of(SONGS)
actual_sha = index_data["metadata"]["built_from_sha256"]
print(f"songs.json 현재 sha: {expected_sha[:16]}…")
print(f"index 기록 sha:      {actual_sha[:16]}…")
print(f"일치: {expected_sha == actual_sha}")
print()

# 2) 곡 수 일치
print(f"songs.json 곡 수: {len(songs_data['songs'])}")
print(f"index 곡 수:      {len(index_data['songs'])}")
print(f"일치: {len(songs_data['songs']) == len(index_data['songs'])}")
print()

# 3) 가사 필드 제외 확인
sample = next(iter(index_data["songs"].values()))
print(f"곡 1번 최상위 필드: {sorted(sample.keys())}")
print(f"가사 필드 제거 확인: {'가사' not in sample}")
print()

# 4) 나머지 필드는 songs.json과 동일한지
diffs = []
for num, idx_song in index_data["songs"].items():
    orig_song = songs_data["songs"][num]
    for k, v in idx_song.items():
        if k == "가사":
            continue
        if orig_song.get(k) != v:
            diffs.append(f"번호 {num} / {k}: mismatch")
            if len(diffs) >= 5:
                break
    if len(diffs) >= 5:
        break

print(f"필드 불일치: {len(diffs)}건")
for d in diffs:
    print(f"  {d}")

# 5) 샘플 출력
print()
print("=== 곡 1번 (index) ===")
print(json.dumps(index_data["songs"]["1"], ensure_ascii=False, indent=2))
