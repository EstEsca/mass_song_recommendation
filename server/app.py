"""FastAPI 앱: 정적 파일 서빙 + SSE 기반 채팅 API + 가사 편집기 (v2).

v2 SSoT: data/source/곡정보.xlsx
- GET /api/songs: songs.json(v2) 로드 → viewer 호환을 위해 v1 형태로 어댑트해 반환
- PUT /api/songs/{num}: v1 patch 에서 '가사.본문'만 추출 → 곡정보.xlsx 가사 시트에 쓰기
                        → 자동 rebuild (build_songs_json + build_song_index)
"""

from __future__ import annotations

import asyncio
import json
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

SONGS_LOCK = asyncio.Lock()

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


def _adapt_v2_to_v1(data_v2: dict) -> dict:
    """v2 songs.json → v1 호환 형태 (viewer가 읽을 수 있는 구조)."""
    songs_out: dict[str, dict] = {}
    for num, s in (data_v2.get("songs") or {}).items():
        idx = s.get("색인") or {}
        성경 = idx.get("성경") or []
        역할 = idx.get("역할") or []
        시기 = idx.get("시기") or []
        성월 = idx.get("성월") or []
        대축일 = idx.get("대축일") or []
        가사_text = s.get("가사") or ""

        songs_out[num] = {
            "번호": s.get("번호"),
            "제목": s.get("제목", ""),
            "작곡자": s.get("작곡자", ""),
            "분류": s.get("분류", ""),
            "색인": {
                "전례별": ", ".join(역할) if 역할 else None,
                "전례시기": ", ".join(시기) if 시기 else None,
                "성월별": ", ".join(성월) if 성월 else None,
                "대축일별": ", ".join(대축일) if 대축일 else None,
                "관련성경구절": "\n".join(성경) if 성경 else None,
                "비고": "",
            },
            # v2 새 필드도 노출 (viewer가 표시하지 않더라도 클라이언트 디버깅 용)
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

    adapted = _adapt_v2_to_v1(data_v2)
    body = json.dumps(adapted, ensure_ascii=False).encode("utf-8")
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


def _validate_patch(patch: dict) -> tuple[str | None, list[str]]:
    """v1 patch에서 v2가 처리할 부분만 추출.
    반환: (가사 본문 신규값 또는 None, 무시된 필드 목록)
    """
    ignored: list[str] = []
    body: str | None = None

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

    return body, ignored


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
    body, ignored = _validate_patch(patch)
    if body is None and not ignored:
        raise HTTPException(400, "편집 가능한 필드가 patch에 없습니다")
    if body is None:
        # 무시된 필드만 있는 patch — 사용자에게 알림
        return JSONResponse(
            {
                "ok": False,
                "error": "v2에서는 '가사.본문'만 편집 가능합니다",
                "무시된_필드": ignored,
                "안내": "색인·요약 등은 곡정보.xlsx에서 직접 편집하거나 /add-tag 스킬을 사용하세요",
            },
            status_code=400,
        )

    async with SONGS_LOCK:
        try:
            _write_lyrics_to_xlsx(num, body)
        except PermissionError:
            raise HTTPException(
                409,
                "곡정보.xlsx가 잠겼습니다 — 엑셀에서 파일을 닫고 재시도하세요.",
            )
        except FileNotFoundError as e:
            raise HTTPException(500, str(e))
        except ValueError as e:
            # 번호 없음 / 시트 없음
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
        "changed": ["가사.본문"],
        "사용자수정시각": now,
        "rebuilt": True,
    }
    if ignored:
        resp["무시된_필드"] = ignored
    return JSONResponse(resp)
