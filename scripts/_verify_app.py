"""server/app.py 헬퍼 함수 검증 (FastAPI 부팅 없이)."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# server.agent를 stub로 (실제 agent.py가 claude-agent-sdk 의존성 있을 수 있음)
import types
import importlib.util


# server/app.py에서 함수만 직접 import (모듈 import 시 사이드 이펙트 회피하기 위해 spec_from_file)
spec = importlib.util.spec_from_file_location(
    "_app_module", ROOT / "server" / "app.py"
)
# server.agent import를 우회하기 위해 server/agent.py가 있는지만 확인
agent_path = ROOT / "server" / "agent.py"
if not agent_path.exists():
    raise SystemExit("server/agent.py 없음")

# 정상 모듈 로드 시도 (FastAPI 인스턴스 생성까지 됨)
try:
    sys.path.insert(0, str(ROOT))
    from server.app import (  # type: ignore
        _adapt_v2_to_v1,
        _validate_patch,
        SONGS_PATH,
        XLSX_PATH,
    )
    print(f"[ok] server.app import 성공")
    print(f"  SONGS_PATH = {SONGS_PATH}")
    print(f"  XLSX_PATH  = {XLSX_PATH}")
except Exception as e:
    raise SystemExit(f"[FAIL] import: {type(e).__name__}: {e}")

# 1) 어댑터 검증
data_v2 = json.loads(SONGS_PATH.read_text(encoding="utf-8"))
adapted = _adapt_v2_to_v1(data_v2)

print(f"\n=== 어댑터 검증 ===")
print(f"v2 metadata: {data_v2.get('metadata')}")
print(f"v1 form keys: {sorted(adapted['songs']['1'].keys())}")
print()

s1 = adapted['songs']['1']
print(f"곡 1번 (v1 어댑트):")
print(f"  번호: {s1['번호']}")
print(f"  제목: {s1['제목']}")
print(f"  색인.전례별: {s1['색인']['전례별']!r}")
print(f"  색인.관련성경구절: {s1['색인']['관련성경구절']!r}")
print(f"  가사.확보여부: {s1['가사']['확보여부']}")
print(f"  가사.본문 길이: {len(s1['가사']['본문'])}자")
print(f"  외부ID: {s1['외부ID']}")
print(f"  신뢰도: {s1['신뢰도']}")
print(f"  _v2색인 (디버그): keys={list(s1['_v2색인'].keys())}")

# 2) patch 검증
print(f"\n=== _validate_patch 검증 ===")

# (a) 정상 가사 본문 patch
body, ignored = _validate_patch({"가사": {"본문": "[1절] 새 가사"}})
preview = (body or "")[:30]
print(f"  (a) 가사 본문만:    body={preview!r}..., ignored={ignored}")
assert body == "[1절] 새 가사" and ignored == [], "case (a) 실패"

# (b) 가사 본문 + 무시되는 v1 필드
body, ignored = _validate_patch({
    "가사": {"본문": "[1절] X", "절별": {"1절": "X"}, "참조URL": ["http://x"]},
    "검증완료": True,
})
print(f"  (b) v1 필드 혼합:    body={body!r}, ignored={ignored}")
assert body == "[1절] X"
assert "검증완료" in ignored
assert "가사.절별" in ignored
assert "가사.참조URL" in ignored

# (c) 본문 없이 v1 필드만
body, ignored = _validate_patch({"가사": {"절별": {}}})
print(f"  (c) 본문 없음:      body={body!r}, ignored={ignored}")
assert body is None and ignored == ["가사.절별"]

# (d) 빈 patch
body, ignored = _validate_patch({})
print(f"  (d) 빈 patch:       body={body!r}, ignored={ignored}")
assert body is None and ignored == []

print("\n[ok] 모든 검증 통과")
