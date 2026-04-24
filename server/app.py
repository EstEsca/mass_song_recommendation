"""FastAPI 앱: 정적 파일 서빙 + SSE 기반 채팅 API + 가사 편집기."""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROJECT_ROOT = BASE_DIR.parent
VIEWER_DIR = PROJECT_ROOT / "viewer"
SONGS_PATH = PROJECT_ROOT / "data" / "songs.json"

SONGS_LOCK = asyncio.Lock()
ALLOWED_LYRICS_FIELDS = ("본문", "절별", "절구조", "참조URL")

app = FastAPI(title="성가 선곡 어시스턴트")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/editor", StaticFiles(directory=VIEWER_DIR, html=True), name="editor")


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


class ChatRequest(BaseModel):
    prompt: str
    client_id: str = "anonymous"


def _sse_format(event: dict) -> bytes:
    data = json.dumps(event, ensure_ascii=False)
    return f"data: {data}\n\n".encode("utf-8")


@app.post("/api/chat")
async def api_chat(req: ChatRequest, request: Request) -> StreamingResponse:
    async def event_stream():
        task: asyncio.Task | None = None
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
# 가사 편집기 API (viewer/server.py 포팅)
# ────────────────────────────────────────────────────────────────


@app.get("/api/songs")
async def api_get_songs() -> Response:
    try:
        data = SONGS_PATH.read_bytes()
    except OSError as e:
        raise HTTPException(500, f"songs.json read failed: {e}")
    return Response(
        content=data,
        media_type="application/json; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


def _validate_patch(patch: dict) -> list[str]:
    """검증만 수행. 잘못된 값이면 예외."""
    errors: list[str] = []
    if "검증완료" in patch and not isinstance(patch["검증완료"], bool):
        errors.append("검증완료 must be boolean")
    lyrics = patch.get("가사") or {}
    if not isinstance(lyrics, dict):
        errors.append("가사 must be an object")
        return errors
    if "참조URL" in lyrics:
        urls = lyrics["참조URL"]
        if not isinstance(urls, list):
            errors.append("참조URL must be a list of strings")
        else:
            for u in urls:
                if not isinstance(u, str):
                    errors.append("참조URL items must be strings")
                    break
                s = u.strip()
                if s and not (s.startswith("http://") or s.startswith("https://")):
                    errors.append("참조URL must start with http(s)://")
                    break
    return errors


def _apply_patch(song: dict[str, Any], patch: dict) -> list[str]:
    changed: list[str] = []

    if "검증완료" in patch:
        song["검증완료"] = bool(patch["검증완료"])
        changed.append("검증완료")

    lyrics_patch = patch.get("가사") or {}
    for key in ALLOWED_LYRICS_FIELDS:
        if key not in lyrics_patch:
            continue
        value = lyrics_patch[key]
        if key == "참조URL":
            value = [u.strip() for u in value if isinstance(u, str) and u.strip()]
        song.setdefault("가사", {})[key] = value
        changed.append(f"가사.{key}")

    return changed


@app.put("/api/songs/{num}")
async def api_put_song(num: str, patch: dict) -> JSONResponse:
    errors = _validate_patch(patch)
    if errors:
        raise HTTPException(400, "; ".join(errors))

    async with SONGS_LOCK:
        try:
            data = json.loads(SONGS_PATH.read_text(encoding="utf-8"))
        except OSError as e:
            raise HTTPException(500, f"read failed: {e}")

        songs = data.get("songs", {})
        if num not in songs:
            raise HTTPException(404, f"song {num} not found")

        song = songs[num]
        changed = _apply_patch(song, patch)
        if not changed:
            raise HTTPException(400, "no editable fields in patch")

        touched_content = any(c.startswith("가사.") for c in changed)
        now = datetime.now().isoformat(timespec="seconds")
        if touched_content:
            song["사용자수정시각"] = now

        tmp = SONGS_PATH.with_suffix(SONGS_PATH.suffix + ".tmp")
        try:
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            shutil.move(str(tmp), str(SONGS_PATH))
        except OSError as e:
            raise HTTPException(500, f"write failed: {e}")

    resp: dict[str, Any] = {"ok": True, "changed": changed}
    if touched_content:
        resp["사용자수정시각"] = now
    if "검증완료" in changed:
        resp["검증완료"] = song.get("검증완료", False)
    return JSONResponse(resp)
