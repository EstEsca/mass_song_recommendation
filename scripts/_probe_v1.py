"""v1 songs.json의 가사.출처 · 가사.참조URL 값 분포 확인 (곡모음집 힌트용)."""
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

with open("s:/song_recommendation/data/songs.json", encoding="utf-8") as f:
    d = json.load(f)

c_src = Counter()
c_ext = 0
c_src_and_ext = 0
yahweh_candidates = []

for num, s in d["songs"].items():
    lyrics = s.get("가사") or {}
    src = lyrics.get("출처")
    c_src[src] += 1

    ext_id = (s.get("외부ID") or {}).get("가톨릭성가번호")
    if ext_id is not None:
        c_ext += 1
        if src:
            c_src_and_ext += 1

    # 야훼이레 흔적 탐색 (제목 / 비고 / 참조URL)
    refs = lyrics.get("참조URL") or []
    title = s.get("제목", "")
    bigo = (s.get("색인") or {}).get("비고", "")
    hay = (title + " " + bigo + " " + " ".join(refs) + " " + (src or "")).lower()
    if "야훼" in hay or "yahweh" in hay or "jireh" in hay or "이레" in hay:
        yahweh_candidates.append((num, title, src, bigo, refs))

print("=== 가사.출처 분포 ===")
for k, v in c_src.most_common():
    print(f"  {k!r}: {v}")

print()
print(f"외부ID.가톨릭성가번호 채움: {c_ext}")
print(f"가사.출처 + 외부ID 둘 다 있음: {c_src_and_ext}")

print()
print(f"=== '야훼이레' 흔적 후보 ({len(yahweh_candidates)}건) ===")
for num, title, src, bigo, refs in yahweh_candidates[:20]:
    print(f"  [{num}] {title!r} / src={src!r} / 비고={bigo!r} / refs={refs}")
