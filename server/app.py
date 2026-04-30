"""FastAPI 앱: 정적 파일 서빙 + SSE 기반 채팅 API + 가사 편집기 (v2).

v2 SSoT: data/source/곡정보.xlsx
- GET /api/songs: songs.json(v2) 로드 → viewer 호환을 위해 v1 형태로 어댑트해 반환
- PUT /api/songs/{num}: v1 patch 에서 '가사.본문'만 추출 → 곡정보.xlsx 가사 시트에 쓰기
                        → 자동 rebuild (build_songs_json + build_song_index)
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from pydantic import BaseModel

from . import agent

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROJECT_ROOT = BASE_DIR.parent
VIEWER_DIR = PROJECT_ROOT / "viewer"
SONGS_PATH = PROJECT_ROOT / "data" / "songs.json"
XLSX_PATH = PROJECT_ROOT / "data" / "source" / "곡정보.xlsx"
REBUILD_SCRIPT = PROJECT_ROOT / "scripts" / "rebuild.py"

# ADR-008 사이드카 4개
IMPRESSIONS_PATH = PROJECT_ROOT / "data" / "song_impressions.json"
IMPRESSION_LOG_PATH = PROJECT_ROOT / "data" / "impression_log.jsonl"
SETLIST_XLSX_PATH = PROJECT_ROOT / "data" / "source" / "선곡표.xlsx"

SONGS_LOCK = asyncio.Lock()
IMPRESSIONS_LOCK = asyncio.Lock()
SETLIST_LOCK = asyncio.Lock()

app = FastAPI(title="성가 선곡 어시스턴트")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/editor", StaticFiles(directory=VIEWER_DIR, html=True), name="editor")


# ────────────────────────────────────────────────────────────────
# 기본 페이지
# ────────────────────────────────────────────────────────────────


@app.get("/")
async def landing() -> FileResponse:
    return FileResponse(STATIC_DIR / "landing.html")


@app.get("/assistant")
@app.get("/assistant/")
async def assistant_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/skills")
async def api_skills() -> JSONResponse:
    return JSONResponse(agent.list_skills())


@app.get("/api/status")
async def api_status() -> JSONResponse:
    return JSONResponse(agent.STATE.snapshot())


# ────────────────────────────────────────────────────────────────
# 채팅 API
# ────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    prompt: str
    client_id: str = "anonymous"


def _sse_format(event: dict) -> bytes:
    data = json.dumps(event, ensure_ascii=False)
    return f"data: {data}\n\n".encode("utf-8")


@app.post("/api/chat")
async def api_chat(req: ChatRequest, request: Request) -> StreamingResponse:
    async def event_stream():
        try:
            gen = agent.run_chat(req.prompt, req.client_id)
            async for event in gen:
                if await request.is_disconnected():
                    break
                yield _sse_format(event)
        except asyncio.CancelledError:
            yield _sse_format({"type": "error", "message": "연결이 중단되었습니다."})
            raise

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=headers,
    )


@app.post("/api/interrupt")
async def api_interrupt() -> JSONResponse:
    ok = agent.interrupt_current()
    return JSONResponse({"cancelled": ok})


# ────────────────────────────────────────────────────────────────
# 가사 편집기 API (v2 어댑터)
#
# 백엔드는 v2 스키마(곡정보.xlsx, songs.json)를 SSoT로 쓰지만,
# viewer/index.html은 v1 곡 객체 구조를 가정한다.
# 이 어댑터가 v2 ↔ v1 변환을 담당하여 viewer를 수정하지 않고도 동작하게 한다.
#
# 편집 가능 범위 (v2):
#   - 가사 본문 (단일 문자열)만 실제 xlsx에 반영됨
#   - 절별/절구조/참조URL/검증완료 등 v1 필드는 PUT 시 무시
#   - 색인·요약·곡모음집 등 신규 v2 필드는 엑셀 또는 add-tag 스킬로 편집
# ────────────────────────────────────────────────────────────────


def _adapt_v2_to_v1(data_v2: dict, impressions: dict | None = None) -> dict:
    """v2 songs.json → v1 호환 형태 (viewer가 읽을 수 있는 구조).

    v2.1: 비고(곡 최상위) + 색인 9필드(요약·성경·성월·시기·대축일·역할·느낌·키워드·곡모음집)
    모두 v1 색인 객체 안에 평탄화하여 노출. v1 viewer는 색인 객체의 키만 읽으므로
    새 키를 추가해도 안전하다.

    ADR-008: `impressions` 사이드카(`song_impressions.json`)가 주어지면 곡 객체에
    `사용경험` 키를 추가해 viewer가 편집 블록을 그릴 수 있도록 노출한다.
    """
    impressions_songs = (impressions or {}).get("songs") or {}
    songs_out: dict[str, dict] = {}
    for num, s in (data_v2.get("songs") or {}).items():
        idx = s.get("색인") or {}
        성경 = idx.get("성경") or []
        역할 = idx.get("역할") or []
        시기 = idx.get("시기") or []
        성월 = idx.get("성월") or []
        대축일 = idx.get("대축일") or []
        느낌 = idx.get("느낌") or []
        키워드 = idx.get("키워드") or []
        곡모음집 = idx.get("곡모음집") or []
        요약 = idx.get("요약") or ""
        가사_text = s.get("가사") or ""

        songs_out[num] = {
            "번호": s.get("번호"),
            "제목": s.get("제목", ""),
            "작곡자": s.get("작곡자", ""),
            "분류": s.get("분류", ""),
            "비고": s.get("비고", ""),
            "조표": s.get("조표"),
            "박자": s.get("박자", ""),
            "색인": {
                "요약": 요약,
                "전례별": ", ".join(역할) if 역할 else None,
                "전례시기": ", ".join(시기) if 시기 else None,
                "성월별": ", ".join(성월) if 성월 else None,
                "대축일별": ", ".join(대축일) if 대축일 else None,
                "관련성경구절": "\n".join(성경) if 성경 else None,
                "느낌": ", ".join(느낌) if 느낌 else None,
                "키워드": ", ".join(키워드) if 키워드 else None,
                "곡모음집": ", ".join(곡모음집) if 곡모음집 else None,
                "비고": s.get("비고", ""),
            },
            # v2 원시 색인 (편집 UI가 배열 그대로 다루기 위함)
            "_v2색인": idx,
            "가사": {
                "확보여부": bool(가사_text),
                "본문": 가사_text,
                "절별": None,
                "절구조": None,
                "출처": None,
                "참조URL": [],
            },
            "외부ID": {"가톨릭성가번호": None},
            "신뢰도": {"점수": None, "등급": None, "세부지표": {}, "실패원인": []},
            # ADR-008 사용경험 사이드카 머지 (없으면 모든 필드 null/"" 기본)
            "사용경험": _impression_for_viewer(impressions_songs.get(str(num))),
        }
    return {
        "metadata": data_v2.get("metadata", {}),
        "songs": songs_out,
    }


@app.get("/api/songs")
async def api_get_songs() -> Response:
    try:
        data_v2 = json.loads(SONGS_PATH.read_text(encoding="utf-8"))
    except OSError as e:
        raise HTTPException(500, f"songs.json read failed: {e}")
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"songs.json parse failed: {e}")

    impressions = _load_impressions()
    adapted = _adapt_v2_to_v1(data_v2, impressions)
    body = json.dumps(adapted, ensure_ascii=False).encode("utf-8")
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


_METER_RE = re.compile(r"^\d+/\d+$")
EDITABLE_META_FIELDS = ("비고", "조표", "박자")


def _validate_patch(patch: dict) -> tuple[str | None, dict, list[str]]:
    """v1 patch에서 v2가 처리할 부분만 추출.

    반환: (가사 본문 신규값 또는 None, 곡목록 메타 패치 dict, 무시된 필드 목록)

    편집 가능 메타 필드(v2.1, ADR-007):
      - 비고: 자유 문자열 (빈 문자열 허용)
      - 조표: 정수 -7..+7 또는 None (미확인). 클라이언트는 문자열 "+1"·"-2"·"0" 또는 정수 가능.
      - 박자: 분수 문자열 "m/n". 빈 문자열 허용.
    """
    ignored: list[str] = []
    body: str | None = None
    meta: dict = {}

    if "검증완료" in patch:
        ignored.append("검증완료")

    lyrics = patch.get("가사")
    if isinstance(lyrics, dict):
        if "본문" in lyrics:
            v = lyrics["본문"]
            if not isinstance(v, str):
                raise HTTPException(400, "가사.본문은 문자열이어야 합니다")
            body = v
        for k in ("절별", "절구조", "참조URL", "출처", "확보여부"):
            if k in lyrics:
                ignored.append(f"가사.{k}")

    if "비고" in patch:
        v = patch["비고"]
        if v is None:
            meta["비고"] = ""
        elif isinstance(v, str):
            meta["비고"] = v
        else:
            raise HTTPException(400, "비고는 문자열이어야 합니다")

    if "조표" in patch:
        v = patch["조표"]
        if v is None or v == "":
            meta["조표"] = None
        else:
            try:
                n = int(str(v).strip().lstrip("+"))
            except (TypeError, ValueError):
                raise HTTPException(400, f"조표 형식 오류: {v!r} (정수 -7..+7 또는 null)")
            if not -7 <= n <= 7:
                raise HTTPException(400, f"조표 범위 오류: {n} (허용: -7..+7)")
            meta["조표"] = n

    if "박자" in patch:
        v = patch["박자"]
        if v is None:
            meta["박자"] = ""
        elif isinstance(v, str):
            s = v.strip()
            if s and not _METER_RE.match(s):
                raise HTTPException(400, f"박자 형식 오류: {v!r} (예: '4/4', '6/8' 또는 빈 문자열)")
            meta["박자"] = s
        else:
            raise HTTPException(400, "박자는 문자열이어야 합니다")

    return body, meta, ignored


def _write_lyrics_to_xlsx(num: str, body: str) -> None:
    """곡정보.xlsx의 '가사' 시트에서 해당 번호 행을 갱신."""
    if not XLSX_PATH.exists():
        raise FileNotFoundError(f"xlsx 없음: {XLSX_PATH}")
    try:
        wb = load_workbook(XLSX_PATH)
    except PermissionError:
        raise
    if "가사" not in wb.sheetnames:
        raise ValueError("'가사' 시트가 없습니다")
    ws = wb["가사"]

    target = int(num)
    for ri in range(2, ws.max_row + 1):
        val = ws.cell(row=ri, column=1).value
        if val is None or val == "":
            continue
        try:
            if int(float(str(val))) != target:
                continue
        except (ValueError, TypeError):
            continue
        cell = ws.cell(row=ri, column=2)
        cell.value = body
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        cell.number_format = "@"
        wb.save(XLSX_PATH)
        return
    raise ValueError(f"번호 {num}에 해당하는 가사 행을 찾을 수 없음")


def _write_meta_to_xlsx(num: str, meta: dict) -> list[str]:
    """곡정보.xlsx의 '곡목록' 시트에서 비고·조표·박자 컬럼을 갱신.

    meta dict의 키만 갱신(부분 패치). 빈 셀로 만들 때:
      - 비고/박자: "" 그대로 저장 → 셀 텍스트 빈 문자열
      - 조표: None → 셀 비우기
    반환: 실제 변경된 컬럼명 목록.
    """
    if not XLSX_PATH.exists():
        raise FileNotFoundError(f"xlsx 없음: {XLSX_PATH}")
    wb = load_workbook(XLSX_PATH)
    if "곡목록" not in wb.sheetnames:
        raise ValueError("'곡목록' 시트가 없습니다")
    ws = wb["곡목록"]

    headers = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
    for f in meta:
        if f not in headers:
            raise ValueError(f"곡목록 시트에 '{f}' 컬럼 없음")

    target = int(num)
    target_row = None
    num_col = headers.get("번호", 1)
    for ri in range(2, ws.max_row + 1):
        v = ws.cell(row=ri, column=num_col).value
        if v in (None, ""):
            continue
        try:
            if int(float(str(v))) == target:
                target_row = ri
                break
        except (ValueError, TypeError):
            continue
    if target_row is None:
        raise ValueError(f"번호 {num}에 해당하는 곡목록 행을 찾을 수 없음")

    changed: list[str] = []
    for field, value in meta.items():
        cell = ws.cell(row=target_row, column=headers[field])
        if field == "조표":
            new_val = None if value is None else ("0" if value == 0 else f"{value:+d}")
        else:
            new_val = value if value not in (None, "") else None
        if cell.value != new_val:
            cell.value = new_val
            cell.number_format = "@"
            changed.append(field)
    if changed:
        wb.save(XLSX_PATH)
    return changed


def _run_rebuild() -> None:
    """rebuild.py 실행 — xlsx → songs.json → songs_index.json."""
    if not REBUILD_SCRIPT.exists():
        raise RuntimeError(f"rebuild script 없음: {REBUILD_SCRIPT}")
    result = subprocess.run(
        [sys.executable, str(REBUILD_SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"rebuild 실패 (rc={result.returncode}): {result.stderr or result.stdout}"
        )


@app.put("/api/songs/{num}")
async def api_put_song(num: str, patch: dict) -> JSONResponse:
    body, meta, ignored = _validate_patch(patch)
    if body is None and not meta and not ignored:
        raise HTTPException(400, "편집 가능한 필드가 patch에 없습니다")
    if body is None and not meta:
        return JSONResponse(
            {
                "ok": False,
                "error": "v2.1에서는 '가사.본문'·비고·조표·박자만 편집 가능합니다",
                "무시된_필드": ignored,
                "안내": "색인·요약 등은 곡정보.xlsx에서 직접 편집하거나 /add-tag 스킬을 사용하세요",
            },
            status_code=400,
        )

    changed: list[str] = []
    async with SONGS_LOCK:
        try:
            if body is not None:
                _write_lyrics_to_xlsx(num, body)
                changed.append("가사.본문")
            if meta:
                meta_changed = _write_meta_to_xlsx(num, meta)
                changed.extend(meta_changed)
        except PermissionError:
            raise HTTPException(
                409,
                "곡정보.xlsx가 잠겼습니다 — 엑셀에서 파일을 닫고 재시도하세요.",
            )
        except FileNotFoundError as e:
            raise HTTPException(500, str(e))
        except ValueError as e:
            raise HTTPException(404, str(e))
        except Exception as e:
            raise HTTPException(500, f"xlsx write failed: {e}")

        try:
            _run_rebuild()
        except Exception as e:
            raise HTTPException(500, f"rebuild failed: {e}")

    now = datetime.now().isoformat(timespec="seconds")
    resp: dict[str, Any] = {
        "ok": True,
        "changed": changed,
        "사용자수정시각": now,
        "rebuilt": True,
    }
    if ignored:
        resp["무시된_필드"] = ignored
    return JSONResponse(resp)


# ────────────────────────────────────────────────────────────────
# 사용 경험 데이터 (ADR-008)
#
# 4개 사이드카 저장소: 선곡표.xlsx, song_impressions.json, impression_log.jsonl
# 모두 카탈로그 빌드(`rebuild.py`) 외부 — 직접 쓰기 안전.
# ────────────────────────────────────────────────────────────────

# 곡별 집계 enum 화이트리스트
DIFFICULTY_VALUES = ("상", "중", "하")
RANGE_VALUES = ("높음", "중간", "낮음")
IMPRESSION_FIELDS = ("난이도", "음역", "떼창적합", "반주필수", "메모")
SETLIST_COLUMNS = ("주일", "전례명", "카테고리", "곡번호", "곡명", "선정이유", "비고")
LOG_TARGETS = ("곡", "미사")


def _new_log_id() -> str:
    """8자리 hex id 생성. 충돌률 1/4억, 본 도메인 양에서 사실상 0."""
    return secrets.token_hex(4)


def _load_impressions() -> dict:
    """song_impressions.json 로드. 없으면 빈 구조 반환."""
    if not IMPRESSIONS_PATH.exists():
        return {"metadata": {"updated": None}, "songs": {}}
    try:
        return json.loads(IMPRESSIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"song_impressions.json parse failed: {e}")


def _save_impressions(data: dict) -> None:
    """song_impressions.json 원자적 쓰기 (tmp → move)."""
    data.setdefault("metadata", {})["updated"] = datetime.now().isoformat(
        timespec="seconds"
    )
    tmp = IMPRESSIONS_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    shutil.move(str(tmp), str(IMPRESSIONS_PATH))


def _impression_for_viewer(entry: dict | None) -> dict:
    """viewer 어댑터용. 사이드카에 곡 엔트리가 없으면 모든 필드 null/""."""
    e = entry or {}
    return {
        "난이도": e.get("난이도"),
        "음역": e.get("음역"),
        "떼창적합": e.get("떼창적합"),
        "반주필수": e.get("반주필수"),
        "메모": e.get("메모", ""),
        "최종갱신": e.get("최종갱신"),
        "last_reflected_id": e.get("last_reflected_id"),
    }


def _append_impression_log(entry: dict) -> dict:
    """impression_log.jsonl 한 줄 append. id/시각은 서버 생성."""
    out = {
        "id": _new_log_id(),
        "시각": datetime.now().isoformat(timespec="seconds"),
        "대상": entry["대상"],
        "미사": entry.get("미사"),
        "곡번호": entry.get("곡번호"),
        "코멘트": entry.get("코멘트", ""),
        "태그": entry.get("태그") or [],
        "출처": entry.get("출처", "log-impression"),
    }
    line = json.dumps(out, ensure_ascii=False) + "\n"
    with IMPRESSION_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line)
    return out


def _read_impression_log() -> list[dict]:
    """전체 로그 로드 (양 적음)."""
    if not IMPRESSION_LOG_PATH.exists():
        return []
    out: list[dict] = []
    with IMPRESSION_LOG_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _validate_impression_patch(patch: dict) -> dict:
    """PUT /api/impressions/{num} 입력 검증. 허용 필드만 추출 + enum 검사."""
    out: dict[str, Any] = {}
    if "난이도" in patch:
        v = patch["난이도"]
        if v is not None and v not in DIFFICULTY_VALUES:
            raise HTTPException(400, f"난이도는 {DIFFICULTY_VALUES} 또는 null")
        out["난이도"] = v
    if "음역" in patch:
        v = patch["음역"]
        if v is not None and v not in RANGE_VALUES:
            raise HTTPException(400, f"음역은 {RANGE_VALUES} 또는 null")
        out["음역"] = v
    for k in ("떼창적합", "반주필수"):
        if k in patch:
            v = patch[k]
            if v is not None and not isinstance(v, bool):
                raise HTTPException(400, f"{k}는 bool 또는 null")
            out[k] = v
    if "메모" in patch:
        v = patch["메모"]
        if not isinstance(v, str):
            raise HTTPException(400, "메모는 문자열")
        out["메모"] = v
    if not out:
        raise HTTPException(400, "편집 가능한 필드가 patch에 없음")
    return out


@app.get("/api/impressions/{num}")
async def api_get_impressions(num: str, n: int = 5) -> JSONResponse:
    """곡별 최근 raw 로그 N건 + 현재 집계 반환 (viewer 표시용)."""
    try:
        target = int(num)
    except ValueError:
        raise HTTPException(400, "곡번호는 정수")
    impressions = _load_impressions()
    aggregate = (impressions.get("songs") or {}).get(str(target))
    log = _read_impression_log()
    recent = [
        e for e in log if e.get("대상") == "곡" and e.get("곡번호") == target
    ][-n:]
    return JSONResponse(
        {
            "곡번호": target,
            "사용경험": _impression_for_viewer(aggregate),
            "최근로그": list(reversed(recent)),
        }
    )


@app.put("/api/impressions/{num}")
async def api_put_impressions(num: str, patch: dict) -> JSONResponse:
    """곡별 집계 직접 편집 — 양방향 기록 (집계 + audit 로그 + watermark 이동)."""
    try:
        target = int(num)
    except ValueError:
        raise HTTPException(400, "곡번호는 정수")

    cleaned = _validate_impression_patch(patch)

    async with IMPRESSIONS_LOCK:
        # 1. audit 로그 append (id 생성됨)
        diff_summary = ", ".join(f"{k}={v!r}" for k, v in cleaned.items())
        audit = _append_impression_log(
            {
                "대상": "곡",
                "미사": None,
                "곡번호": target,
                "코멘트": f"viewer 편집: {diff_summary}",
                "태그": [],
                "출처": "viewer-edit",
            }
        )

        # 2. 집계 사이드카 갱신
        impressions = _load_impressions()
        songs = impressions.setdefault("songs", {})
        cur = songs.get(str(target)) or {}
        cur.update(cleaned)
        cur["최종갱신"] = datetime.now().date().isoformat()
        cur["last_reflected_id"] = audit["id"]
        songs[str(target)] = cur
        _save_impressions(impressions)

    return JSONResponse(
        {
            "ok": True,
            "곡번호": target,
            "사용경험": _impression_for_viewer(cur),
            "audit_id": audit["id"],
        }
    )


class ImpressionLogIn(BaseModel):
    대상: str
    곡번호: int | None = None
    미사: str | None = None
    코멘트: str = ""
    태그: list[str] | None = None


@app.post("/api/impression-log")
async def api_post_impression_log(req: ImpressionLogIn) -> JSONResponse:
    """raw 소감 한 건 append (`/log-impression` 스킬용). watermark 이동은 안 함."""
    if req.대상 not in LOG_TARGETS:
        raise HTTPException(400, f"대상은 {LOG_TARGETS}")
    if req.대상 == "곡" and req.곡번호 is None:
        raise HTTPException(400, "대상=곡이면 곡번호 필수")
    if req.대상 == "미사" and req.곡번호 is not None:
        raise HTTPException(400, "대상=미사면 곡번호는 null")
    async with IMPRESSIONS_LOCK:
        entry = _append_impression_log(
            {
                "대상": req.대상,
                "미사": req.미사,
                "곡번호": req.곡번호,
                "코멘트": req.코멘트,
                "태그": req.태그 or [],
                "출처": "log-impression",
            }
        )
    return JSONResponse({"ok": True, "entry": entry})


class ReflectIn(BaseModel):
    """집계 갱신 + watermark 이동 (회고 승인 게이트용)."""

    곡번호: int
    사용경험: dict
    last_log_id: str  # 이번에 반영하는 가장 마지막 로그 id


@app.post("/api/impressions/reflect")
async def api_reflect(req: ReflectIn) -> JSONResponse:
    """회고 후 집계 반영 — viewer-edit 경로와 달리 audit 로그를 새로 만들지 않고
    이미 있는 raw 로그들을 last_reflected_id로만 가리킨다.
    """
    cleaned = _validate_impression_patch(req.사용경험)
    async with IMPRESSIONS_LOCK:
        impressions = _load_impressions()
        songs = impressions.setdefault("songs", {})
        cur = songs.get(str(req.곡번호)) or {}
        cur.update(cleaned)
        cur["최종갱신"] = datetime.now().date().isoformat()
        cur["last_reflected_id"] = req.last_log_id
        songs[str(req.곡번호)] = cur
        _save_impressions(impressions)
    return JSONResponse(
        {"ok": True, "곡번호": req.곡번호, "사용경험": _impression_for_viewer(cur)}
    )


# ────────────────────────────────────────────────────────────────
# 선곡표 xlsx
# ────────────────────────────────────────────────────────────────


def _read_setlist_xlsx() -> list[dict]:
    """선곡표.xlsx → list[dict]. 빈 행/헤더 제외."""
    if not SETLIST_XLSX_PATH.exists():
        return []
    wb = load_workbook(SETLIST_XLSX_PATH, data_only=True)
    if "선곡" not in wb.sheetnames:
        return []
    ws = wb["선곡"]
    headers = [str(c.value or "").strip() for c in next(ws.iter_rows(max_row=1))]
    out: list[dict] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(cell not in (None, "") for cell in row):
            continue
        item = {h: row[i] if i < len(row) else None for i, h in enumerate(headers)}
        if item.get("곡번호") is not None:
            try:
                item["곡번호"] = int(float(str(item["곡번호"])))
            except (ValueError, TypeError):
                pass
        out.append(item)
    return out


def _append_setlist_rows(rows: list[dict]) -> int:
    """선곡표.xlsx에 행 append. 반환: 추가된 행 수."""
    if not SETLIST_XLSX_PATH.exists():
        raise FileNotFoundError(f"선곡표 없음: {SETLIST_XLSX_PATH}")
    wb = load_workbook(SETLIST_XLSX_PATH)
    if "선곡" not in wb.sheetnames:
        raise ValueError("'선곡' 시트가 없습니다")
    ws = wb["선곡"]
    start = ws.max_row + 1
    count = 0
    for row in rows:
        for col_idx, key in enumerate(SETLIST_COLUMNS, start=1):
            v = row.get(key, "")
            cell = ws.cell(row=start + count, column=col_idx, value=v)
            cell.number_format = "@"
        count += 1
    wb.save(SETLIST_XLSX_PATH)
    return count


class SetlistRow(BaseModel):
    주일: str
    전례명: str
    카테고리: str
    곡번호: int
    곡명: str = ""
    선정이유: str = ""
    비고: str = ""


class SetlistAppendIn(BaseModel):
    rows: list[SetlistRow]


@app.get("/api/setlist")
async def api_get_setlist() -> JSONResponse:
    try:
        rows = _read_setlist_xlsx()
    except PermissionError:
        raise HTTPException(
            409,
            "선곡표.xlsx가 잠겼습니다 — 엑셀에서 파일을 닫고 재시도하세요.",
        )
    return JSONResponse({"rows": rows, "count": len(rows)})


@app.post("/api/setlist")
async def api_post_setlist(req: SetlistAppendIn) -> JSONResponse:
    if not req.rows:
        raise HTTPException(400, "rows가 비어있음")
    async with SETLIST_LOCK:
        try:
            n = _append_setlist_rows([r.model_dump() for r in req.rows])
        except PermissionError:
            raise HTTPException(
                409,
                "선곡표.xlsx가 잠겼습니다 — 엑셀에서 파일을 닫고 재시도하세요.",
            )
        except FileNotFoundError as e:
            raise HTTPException(500, str(e))
        except ValueError as e:
            raise HTTPException(500, str(e))
    return JSONResponse({"ok": True, "appended": n})
