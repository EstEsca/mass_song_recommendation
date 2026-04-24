"""
크롤러 결과를 songs.json에 in-place 병합.

병합 정책 (기본값):
  1. `사용자수정시각` 필드가 있으면 skip (사용자 수작업 보호)
  2. 기존 가사 출처의 우선순위가 신규 소스보다 높으면 skip
     (같거나 낮은 소스는 업그레이드 허용)
  3. 그 외는 덮어쓰기 (확보여부=True, 본문, 출처, 참조URL, 외부ID 갱신)

소스 우선순위 (높을수록 신뢰):
  maria (3) > yseng (2) > PDF추출 변형들 (1)

`force=True`면 1, 2를 무시하고 모두 덮어씀.

songs.json은 단일 진리 저장소이며, 본 모듈은 bootstrap하지 않는다.
(신규 곡 추가는 수작업으로 songs.json에 엔트리를 만든 뒤 크롤러 재실행.)
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SONGS_JSON = ROOT / "data" / "songs.json"

SOURCE_PRIORITY = {
    "maria": 3,
    "yseng": 2,
    "PDF추출(v3)": 1,
    "PDF추출(v3)+웹보정": 1,
    "PDF추출(v3)+웹스니펫교정": 1,
}


def source_priority(src: str | None) -> int:
    """등록되지 않은 소스는 0(알 수 없음)."""
    if not src:
        return 0
    return SOURCE_PRIORITY.get(src, 0)


def load_songs() -> dict:
    with SONGS_JSON.open(encoding="utf-8") as f:
        return json.load(f)


def save_songs(data: dict) -> None:
    data["metadata"]["updated"] = date.today().isoformat()
    data["metadata"]["lyrics_count"] = sum(
        1 for s in data["songs"].values() if s["가사"].get("확보여부")
    )
    with SONGS_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def should_skip(entry: dict, source_id: str, force: bool) -> str | None:
    """건너뛸 이유를 문자열로 반환. 진행 가능하면 None."""
    if force:
        return None
    if entry.get("사용자수정시각"):
        return "사용자수정시각 있음"
    if not entry["가사"].get("확보여부"):
        return None
    prior = entry["가사"].get("출처")
    if prior == source_id:
        return None  # 같은 소스 재수집은 업데이트 허용
    if source_priority(source_id) > source_priority(prior):
        return None  # 더 높은 우선순위 소스로 업그레이드 허용
    return f"더 높은 소스({prior})가 이미 확보"


def apply_lyrics(entry: dict, source_id: str, text: str, url: str | None,
                 external_id: tuple[str, object] | None = None) -> None:
    """가사 블록과 외부ID 갱신.
    새 본문이 도입되므로 본문에서 파생된 필드(절별/신뢰도/검증완료)는 리셋.
    재계산은 후속 스킬(fix-lyrics-format, structure-lyrics, validate-lyrics-format)이 담당."""
    entry["가사"]["확보여부"] = True
    entry["가사"]["본문"] = text
    entry["가사"]["출처"] = source_id
    entry["가사"]["참조URL"] = [url] if url else []
    entry["가사"]["수집시각"] = datetime.now().isoformat(timespec="seconds")

    # 파생 필드 리셋 — 본문 대비 재계산 필요
    entry["가사"]["절별"] = None
    entry["가사"]["절구조"] = None
    entry["신뢰도"] = {
        "점수": None,
        "등급": None,
        "세부지표": {},
        "실패원인": [],
    }
    entry.pop("검증완료", None)

    if external_id is not None:
        key, value = external_id
        entry.setdefault("외부ID", {})[key] = value


def print_report(source_id: str, counts: dict) -> None:
    prio = source_priority(source_id)
    print(f"\n[{source_id}(우선순위={prio}) → songs.json 병합]")
    print(f"  신규/갱신:         {counts.get('updated', 0)}")
    print(f"  skip(사용자수정):  {counts.get('skipped_user', 0)}")
    print(f"  skip(고우선 소스): {counts.get('skipped_other', 0)}")
    print(f"  매칭 실패:         {counts.get('no_match', 0)}")
