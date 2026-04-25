"""
build_song_index.py

data/songs.json → data/songs_index.json

songs.json에서 가사 본문을 제거한 경량 색인 파일을 생성.
recommend-hymns 스킬의 Stage 1 후보 필터에서 읽는 파일이며,
가사 본문이 필요할 때만 songs.json을 pinpoint 조회한다.

`_meta.built_from_sha256`에 songs.json의 해시를 박아 동기화 검증.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SONGS_JSON = ROOT / "data" / "songs.json"
OUT_JSON = ROOT / "data" / "songs_index.json"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_lyrics(song: dict) -> dict:
    """곡 객체에서 가사 필드를 제거한 복사본 반환."""
    return {k: v for k, v in song.items() if k != "가사"}


def main() -> None:
    if not SONGS_JSON.exists():
        raise SystemExit(f"songs.json 없음: {SONGS_JSON}")

    print(f"[load] {SONGS_JSON}")
    with SONGS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)

    songs = data["songs"]
    index_songs = {num: strip_lyrics(s) for num, s in songs.items()}

    sha = sha256_of(SONGS_JSON)
    now = datetime.now().isoformat(timespec="seconds")

    out = {
        "metadata": {
            "schema_version": "2.0",
            "built_from_sha256": sha,
            "built_at": now,
            "total_songs": len(index_songs),
        },
        "songs": index_songs,
    }

    OUT_JSON.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 크기 비교
    songs_size = SONGS_JSON.stat().st_size
    index_size = OUT_JSON.stat().st_size
    reduction = (1 - index_size / songs_size) * 100

    print(f"[build] → {OUT_JSON}")
    print(f"곡 수: {len(index_songs)}")
    print(f"sha256 (songs.json): {sha[:16]}…")
    print(f"크기: {songs_size:,} bytes → {index_size:,} bytes ({reduction:.1f}% 감소)")


if __name__ == "__main__":
    main()
