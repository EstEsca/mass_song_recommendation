"""
migrate_v1_to_v2.py

v1 songs.json(스키마 v1.0)을 v2.0으로 변환한다.

- 신뢰도·외부ID·가사.하위필드를 data/archive/신뢰도_스냅샷_YYYY-MM-DD.xlsx로 1회 백업
- 색인 7카테고리(요약·성경·성월·시기·대축일·역할·느낌·키워드)로 재구성
- 가사를 단일 문자열로 평탄화
- vocab 위반 값(작곡자 이름이 전례별에 들어간 오염 등) 정리

Usage:
    python scripts/migrate_v1_to_v2.py --backup-only   # 백업만
    python scripts/migrate_v1_to_v2.py --migrate-only  # 마이그레이션만
    python scripts/migrate_v1_to_v2.py                 # 둘 다
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SONGS_PATH = ROOT / "data" / "songs.json"
ARCHIVE_DIR = ROOT / "data" / "archive"
TODAY = datetime.now().strftime("%Y-%m-%d")
BACKUP_XLSX = ARCHIVE_DIR / f"신뢰도_스냅샷_{TODAY}.xlsx"

# ---- vocab (docs/spec/vocab.md와 동기화 필요) ----
ROLE_VOCAB = {"입당", "봉헌", "성체", "파견", "묵상", "감사", "찬미", "화답", "주님의기도", "마침"}
SEASON_VOCAB = {"대림", "성탄", "사순", "부활", "연중"}

# 책 약어 통일
BOOK_ALIASES = {
    "마태오": "마태",
}


# =============================================================================
# Step 1. 백업
# =============================================================================

def backup_to_xlsx(data: dict) -> int:
    """신뢰도 또는 외부ID가 채워진 곡을 xlsx로 백업."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "신뢰도_외부ID"

    headers = ["번호", "제목", "점수", "등급", "세부지표_JSON", "실패원인", "가톨릭성가번호"]
    ws.append(headers)

    count = 0
    for song in data["songs"].values():
        sin = song.get("신뢰도") or {}
        ext = song.get("외부ID") or {}

        has_sin = sin.get("점수") is not None
        has_ext = ext.get("가톨릭성가번호") is not None
        if not (has_sin or has_ext):
            continue

        details = sin.get("세부지표") or {}
        fails = sin.get("실패원인") or []
        row = [
            song.get("번호"),
            song.get("제목"),
            sin.get("점수"),
            sin.get("등급"),
            json.dumps(details, ensure_ascii=False) if details else None,
            "|".join(fails) if fails else None,
            ext.get("가톨릭성가번호"),
        ]
        ws.append(row)
        count += 1

    # 모든 셀을 텍스트 서식으로
    for row in ws.iter_rows():
        for cell in row:
            cell.number_format = "@"

    wb.save(BACKUP_XLSX)
    print(f"[backup] {count}곡 → {BACKUP_XLSX}")
    return count


# =============================================================================
# Step 2. 정규화 유틸
# =============================================================================

def normalize_scripture(text: str | None) -> list[str]:
    """
    '마태 28, 16-20' → '마태28:16-20'
    '마태 28, 16-20\n마르 16, 14-18' → ['마태28:16-20', '마르16:14-18']
    '시편 107' → '시편107'
    '요한 6, 51' → '요한6:51'
    """
    if not text or not text.strip():
        return []
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # 패턴: <책(한글+숫자 혼합)> <장>[, <절시작>[- <절끝>]]
        m = re.match(r"^([1-2]?[가-힣]+)\s*(\d+)(?:\s*,\s*(\d+)(?:\s*-\s*(\d+))?)?", line)
        if not m:
            # 파싱 실패 → 공백만 제거해 그대로
            out.append(line.replace(" ", ""))
            continue
        book = BOOK_ALIASES.get(m.group(1), m.group(1))
        chapter = m.group(2)
        v_start = m.group(3)
        v_end = m.group(4)
        if v_start is None:
            out.append(f"{book}{chapter}")
        elif v_end is None or v_end == v_start:
            out.append(f"{book}{chapter}:{v_start}")
        else:
            out.append(f"{book}{chapter}:{v_start}-{v_end}")
    return out


def normalize_month_multi(text: str | None) -> list[str]:
    """
    '5월 성모성월' → ['5월']
    '5월 성모성월\n10월 로사리오성월' → ['5월', '10월']
    """
    if not text:
        return []
    out = []
    for line in text.split("\n"):
        m = re.search(r"(\d{1,2})\s*월", line)
        if m:
            out.append(f"{int(m.group(1))}월")
    # 중복 제거하되 순서 유지
    seen = set()
    uniq = []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def normalize_feast_multi(text: str | None) -> list[str]:
    """'성령 강림 대축일' → ['성령강림대축일'], \\n 다중값 지원."""
    if not text:
        return []
    out = []
    for line in text.split("\n"):
        line = line.strip().replace(" ", "")
        if line:
            out.append(line)
    return out


def parse_role_and_keyword_overflow(text: str | None) -> tuple[list[str], list[str]]:
    """
    전례별 값 파싱.
    - vocab에 있으면 역할로
    - 없으면(작곡자 이름 등) 버림 → 두 번째 반환값은 빈 배열 (작곡자 이름은 보존 가치 없음)

    \\n 다중값 지원.
    """
    if not text:
        return [], []
    roles: list[str] = []
    for line in text.split("\n"):
        v = line.strip()
        if v in ROLE_VOCAB:
            roles.append(v)
    return roles, []


def parse_season_and_keyword_overflow(text: str | None) -> tuple[list[str], list[str]]:
    """
    전례시기 값 파싱.
    - vocab에 있으면 시기로
    - 없으면(미사곡 용도 등) 공백 제거해 키워드로 이전 (정보 보존)

    \\n 다중값 지원.
    """
    if not text:
        return [], []
    seasons: list[str] = []
    overflow: list[str] = []
    for line in text.split("\n"):
        v = line.strip()
        if not v:
            continue
        if v in SEASON_VOCAB:
            seasons.append(v)
        else:
            overflow.append(v.replace(" ", ""))
    return seasons, overflow


# =============================================================================
# Step 3. 마이그레이션
# =============================================================================

def migrate_song(v1: dict, stats: dict) -> dict:
    old_idx = v1.get("색인") or {}

    roles, _ = parse_role_and_keyword_overflow(old_idx.get("전례별"))
    seasons, season_overflow = parse_season_and_keyword_overflow(old_idx.get("전례시기"))

    # 오염된 전례별(작곡자 이름 등) 집계
    if old_idx.get("전례별") and not roles:
        stats["dropped_role"].append((v1["번호"], old_idx["전례별"]))

    keywords: list[str] = []
    # 시기 vocab 위반분을 키워드로 이전 (예: "청년미사곡")
    keywords.extend(season_overflow)

    # 곡모음집: v1.외부ID.가톨릭성가번호가 채워져 있으면 "가톨릭성가" 태깅
    collections: list[str] = []
    ext_id = (v1.get("외부ID") or {}).get("가톨릭성가번호")
    if ext_id is not None:
        collections.append("가톨릭성가")
        stats["collection_init"] += 1

    v2 = {
        "번호": v1["번호"],
        "제목": v1["제목"],
        "작곡자": v1["작곡자"],
        "분류": v1["분류"],
        "색인": {
            "요약": "",
            "성경": normalize_scripture(old_idx.get("관련성경구절")),
            "성월": normalize_month_multi(old_idx.get("성월별")),
            "시기": seasons,
            "대축일": normalize_feast_multi(old_idx.get("대축일별")),
            "역할": roles,
            "느낌": [],
            "키워드": keywords,
            "곡모음집": collections,
        },
        "가사": (v1.get("가사") or {}).get("본문") or "",
    }
    return v2


def migrate(data: dict) -> tuple[dict, dict]:
    stats = {"dropped_role": [], "collection_init": 0}
    new_songs = {num: migrate_song(song, stats) for num, song in data["songs"].items()}
    v2 = {
        "metadata": {
            "schema_version": "2.0",
            "created": (data.get("metadata") or {}).get("created", TODAY),
            "updated": TODAY,
            "total_songs": len(new_songs),
        },
        "songs": new_songs,
    }
    return v2, stats


# =============================================================================
# main
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup-only", action="store_true")
    parser.add_argument("--migrate-only", action="store_true")
    args = parser.parse_args()

    with SONGS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    print(f"[load] {len(data['songs'])}곡 로드 ({SONGS_PATH})")

    if not args.migrate_only:
        backup_to_xlsx(data)

    if not args.backup_only:
        v2_data, stats = migrate(data)

        # 안전 백업: 기존 songs.json을 .v1.bak.json으로 복사 (최초 1회만)
        safety_bak = SONGS_PATH.with_suffix(".v1.bak.json")
        if not safety_bak.exists():
            shutil.copy2(SONGS_PATH, safety_bak)
            print(f"[safety backup] {safety_bak}")
        else:
            print(f"[safety backup] 이미 존재 — 건너뜀: {safety_bak}")

        SONGS_PATH.write_text(
            json.dumps(v2_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[migrate] v2 스키마로 저장: {SONGS_PATH}")

        dropped = stats["dropped_role"]
        print(f"\n[stats] 전례별 vocab 위반으로 버린 값: {len(dropped)}건")
        for num, val in dropped[:10]:
            print(f"  - 번호={num}: {val!r}")
        if len(dropped) > 10:
            print(f"  ... +{len(dropped) - 10}건")

        print(f"\n[stats] 곡모음집=['가톨릭성가']로 초기화된 곡: {stats['collection_init']}곡")


if __name__ == "__main__":
    main()
