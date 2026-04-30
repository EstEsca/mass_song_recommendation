"""
ADR-008 end-to-end 검증 (사용 경험 데이터 사이드카).

실행:
    python scripts/_verify_adr008.py

검증 항목:
  1. 초기화 — 사이드카 3개 존재 (song_impressions.json, impression_log.jsonl, 선곡표.xlsx)
  2. viewer 편집 — PUT /api/impressions/{num} → 사이드카 + audit 라인 + watermark
  3. 로그 API — POST /api/impression-log
  4. /log-impression 시뮬 — raw 3건 + 미사 1건 + reflect 1곡 (다른 곡은 미반영)
  5. /log-setlist 시뮬 — POST /api/setlist 4행 append
  6. GET /api/setlist — 재조회로 count 확인
  7. /recommend-hymns 통합 — GET /api/songs에 사용경험 머지 노출
  8. Validation — 잘못된 enum, 누락 필드 → 400

마지막에 사이드카 3개 모두 빈 상태로 복원.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from server.app import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

c = TestClient(app)
fail = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global fail
    mark = "✓" if cond else "✗"
    print(f"  {mark} {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        fail += 1


def reset_files() -> None:
    """모든 사이드카 초기 상태로."""
    impr_path = ROOT / "data" / "song_impressions.json"
    impr_path.write_text(
        json.dumps(
            {"metadata": {"updated": None}, "songs": {}}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    (ROOT / "data" / "impression_log.jsonl").write_text("", encoding="utf-8")
    xlsx = ROOT / "data" / "source" / "선곡표.xlsx"
    if xlsx.exists():
        xlsx.unlink()
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "init_setlist_xlsx.py")],
        check=True,
        capture_output=True,
    )


print("=== 검증 1: 초기화 ===")
reset_files()
check("song_impressions.json 존재", (ROOT / "data" / "song_impressions.json").exists())
check("impression_log.jsonl 존재", (ROOT / "data" / "impression_log.jsonl").exists())
check("선곡표.xlsx 존재", (ROOT / "data" / "source" / "선곡표.xlsx").exists())

print("\n=== 검증 2: viewer 편집 (PUT /api/impressions/123) ===")
r = c.put("/api/impressions/123", json={"떼창적합": True, "메모": "후렴 쉬움"})
body = r.json()
check("PUT 200", r.status_code == 200, f"status={r.status_code}")
check("ok=true", body.get("ok") is True)
check("audit_id 있음", body.get("audit_id") is not None)
check("떼창적합=True", body["사용경험"]["떼창적합"] is True)
check("최종갱신 채워짐", body["사용경험"]["최종갱신"] is not None)
audit_id = body["audit_id"]

impr = json.loads((ROOT / "data" / "song_impressions.json").read_text(encoding="utf-8"))
check("song_impressions.json에 123 곡", "123" in impr.get("songs", {}))
check(
    "last_reflected_id == audit_id",
    impr["songs"]["123"].get("last_reflected_id") == audit_id,
)

log_lines = (ROOT / "data" / "impression_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
check("log에 audit 1건", len(log_lines) == 1)
audit_entry = json.loads(log_lines[0])
check("audit 출처=viewer-edit", audit_entry["출처"] == "viewer-edit")
check("audit 곡번호=123", audit_entry["곡번호"] == 123)

print("\n=== 검증 3: 로그 API (POST /api/impression-log) ===")
r = c.post("/api/impression-log", json={"대상": "곡", "곡번호": 123, "코멘트": "스킬 호출"})
body = r.json()
check("POST 200", r.status_code == 200)
check("entry id 8자리 hex", len(body["entry"]["id"]) == 8)
check("출처=log-impression", body["entry"]["출처"] == "log-impression")

print("\n=== 검증 4: /log-impression 시뮬 — raw 3+1, reflect 1곡 ===")
ids: list[str] = []
for num, msg in [(123, "떼창 좋음 (2회차)"), (87, "음정 어려움"), (211, "회중 반응 좋음")]:
    r = c.post(
        "/api/impression-log",
        json={"대상": "곡", "곡번호": num, "미사": "테스트 미사", "코멘트": msg},
    )
    ids.append(r.json()["entry"]["id"])
r = c.post(
    "/api/impression-log",
    json={"대상": "미사", "곡번호": None, "미사": "테스트 미사", "코멘트": "전반적 매끄러움"},
)
mass_id = r.json()["entry"]["id"]
check("raw 4건 추가", len(ids) == 3 and mass_id is not None)

r = c.post(
    "/api/impressions/reflect",
    json={
        "곡번호": 123,
        "사용경험": {"난이도": "중", "메모": "회중 반응 좋음, 떼창 일관"},
        "last_log_id": ids[0],
    },
)
body = r.json()
check("reflect 200", r.status_code == 200)
check("watermark 이동", body["사용경험"]["last_reflected_id"] == ids[0])
check("난이도 갱신", body["사용경험"]["난이도"] == "중")

r = c.get("/api/impressions/87")
check(
    "87곡 집계 미생성 (미반영)",
    r.json()["사용경험"]["last_reflected_id"] is None,
)

print("\n=== 검증 5: /log-setlist 시뮬 (POST /api/setlist 4행) ===")
r = c.post(
    "/api/setlist",
    json={
        "rows": [
            {"주일": "2026-05-03", "전례명": "부활 제5주일", "카테고리": "입당", "곡번호": 12},
            {"주일": "2026-05-03", "전례명": "부활 제5주일", "카테고리": "봉헌", "곡번호": 87},
            {"주일": "2026-05-03", "전례명": "부활 제5주일", "카테고리": "성체", "곡번호": 234},
            {"주일": "2026-05-03", "전례명": "부활 제5주일", "카테고리": "파견", "곡번호": 49},
        ]
    },
)
check("setlist POST 200", r.status_code == 200)
check("appended=4", r.json()["appended"] == 4)

print("\n=== 검증 6: GET /api/setlist (재조회) ===")
r = c.get("/api/setlist")
body = r.json()
check("GET 200", r.status_code == 200)
check("count==4", body["count"] == 4)
check("입당 카테고리 있음", any(row["카테고리"] == "입당" for row in body["rows"]))

print("\n=== 검증 7: GET /api/songs 머지 (recommend-hymns 통합) ===")
r = c.get("/api/songs")
body = r.json()
check("GET 200", r.status_code == 200)
song_123 = body["songs"].get("123")
check("123곡 객체 존재", song_123 is not None)
if song_123:
    exp = song_123.get("사용경험") or {}
    check("사용경험 키 노출", "사용경험" in song_123)
    check("사용경험.난이도=중 (reflect 결과)", exp.get("난이도") == "중")
    check("사용경험.떼창적합=True (이전 PUT 결과)", exp.get("떼창적합") is True)

song_1 = body["songs"].get("1")
if song_1:
    check("1번 곡(미기록)도 사용경험 키 존재", "사용경험" in song_1)
    check("1번 사용경험.난이도=None", song_1["사용경험"].get("난이도") is None)

print("\n=== 검증 8: validation 에러 ===")
r = c.put("/api/impressions/123", json={"난이도": "WRONG"})
check("invalid 난이도 → 400", r.status_code == 400)
r = c.post("/api/impression-log", json={"대상": "곡", "코멘트": "곡번호 없음"})
check("missing 곡번호 → 400", r.status_code == 400)
r = c.post("/api/impression-log", json={"대상": "미사", "곡번호": 5, "코멘트": "x"})
check("미사+곡번호 → 400", r.status_code == 400)

print("\n=== 정리 ===")
reset_files()
print("  사이드카 3개 모두 빈 상태로 복원")

print(f"\n결과: {'✓ 모두 통과' if fail == 0 else f'✗ {fail}건 실패'}")
sys.exit(0 if fail == 0 else 1)
