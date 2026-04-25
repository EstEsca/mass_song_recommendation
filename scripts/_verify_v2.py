"""v2 songs.json 검증."""
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

with open("s:/song_recommendation/data/songs.json", encoding="utf-8") as f:
    d = json.load(f)

meta = d.get("metadata", {})
print(f"schema_version: {meta.get('schema_version')}")
print(f"total_songs: {meta.get('total_songs')}")
print()

songs = d["songs"]
print(f"실제 곡 수: {len(songs)}")
print()

# 최상위 필드 검증
required_top = {"번호", "제목", "작곡자", "분류", "색인", "가사"}
top_keys = set(next(iter(songs.values())).keys())
print(f"최상위 필드 (곡 1번): {sorted(top_keys)}")
print(f"필수 필드 충족: {required_top.issubset(top_keys)}")
print(f"제거되어야 할 필드: {top_keys - required_top}")
print()

# 색인 카테고리 검증
required_idx = {"요약", "성경", "성월", "시기", "대축일", "역할", "느낌", "키워드", "곡모음집"}
idx_keys = set(songs["1"]["색인"].keys())
print(f"색인 카테고리: {sorted(idx_keys)}")
print(f"필수 카테고리 충족: {required_idx.issubset(idx_keys)}")
print()

# 타입 검증 — null이 있으면 안 됨
null_found = []
for num, s in songs.items():
    idx = s["색인"]
    for k in ["성경", "성월", "시기", "대축일", "역할", "느낌", "키워드", "곡모음집"]:
        if idx.get(k) is None or not isinstance(idx[k], list):
            null_found.append((num, k, idx.get(k)))
    if idx.get("요약") is None or not isinstance(idx["요약"], str):
        null_found.append((num, "요약", idx.get("요약")))
    if s.get("가사") is None or not isinstance(s["가사"], str):
        null_found.append((num, "가사", type(s.get("가사"))))

print(f"null/타입 위반: {len(null_found)}건")
for n, k, v in null_found[:5]:
    print(f"  [{n}] {k} = {v!r}")
print()

# 곡모음집 통계
c_coll = Counter()
for s in songs.values():
    for v in s["색인"]["곡모음집"]:
        c_coll[v] += 1
print(f"=== 곡모음집 분포 ===")
for k, v in c_coll.most_common():
    print(f"  {k!r}: {v}")
print()

# 역할 분포 (vocab 정화 결과 확인)
c_role = Counter()
for s in songs.values():
    for v in s["색인"]["역할"]:
        c_role[v] += 1
print(f"=== 역할 분포 ===")
for k, v in c_role.most_common():
    print(f"  {k!r}: {v}")
print()

# 시기 분포
c_season = Counter()
for s in songs.values():
    for v in s["색인"]["시기"]:
        c_season[v] += 1
print(f"=== 시기 분포 ===")
for k, v in c_season.most_common():
    print(f"  {k!r}: {v}")
print()

# 성경 구절 정규화 확인 (샘플)
print(f"=== 곡 1번 전체 ===")
print(json.dumps(songs["1"], ensure_ascii=False, indent=2))
print()

print(f"=== 곡 2번 전체 (외부ID 있었던 곡) ===")
print(json.dumps(songs["2"], ensure_ascii=False, indent=2))
print()

# 가사 확보 상태
with_lyrics = sum(1 for s in songs.values() if s["가사"])
print(f"가사 확보: {with_lyrics} / {len(songs)}")
