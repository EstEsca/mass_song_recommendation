"""Claude Agent SDK wrapper with a global single-session lock.

한 번에 한 세션만 실행되도록 보장하고, SDK에서 나오는 메시지를
프론트엔드가 소비하기 쉬운 dict로 직렬화한다.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import AsyncIterator, Optional

from claude_agent_sdk import ClaudeAgentOptions, query

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "server" / "logs" / "prompts.jsonl"

MAX_PROMPT_CHARS = 2000
MAX_TURNS = 30

ALLOWED_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "WebFetch",
    "Bash",
]

SYSTEM_PROMPT_APPEND = (
    "당신은 성가 선곡 프로젝트의 웹 어시스턴트다. "
    "사용자가 요청한 작업은 반드시 이 프로젝트의 기존 스킬을 통해 수행하라. "
    "스킬로 해결할 수 없는 요청은 정중히 거절하라. "
    "git 조작, 임의 쉘 명령, 프로젝트 외부 파일 접근은 금지. "
    f"모든 파일 경로는 {PROJECT_ROOT.as_posix()} 하위로 제한된다."
)


class SessionBusy(Exception):
    """다른 세션이 점유 중."""


class _SessionState:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.client_id: Optional[str] = None
        self.started_at: Optional[float] = None
        self.current_task: Optional[asyncio.Task] = None

    def snapshot(self) -> dict:
        return {
            "busy": self.lock.locked(),
            "client_id": self.client_id,
            "started_at": self.started_at,
        }


STATE = _SessionState()


def _log_prompt(client_id: str, prompt: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.time(),
        "client_id": client_id,
        "prompt": prompt,
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _is_path_safe(path_str: str) -> bool:
    """Write/Edit 대상 경로가 프로젝트 밖으로 나가지 않는지 확인."""
    try:
        resolved = Path(path_str).resolve()
        resolved.relative_to(PROJECT_ROOT)
        return True
    except (ValueError, OSError):
        return False


def _serialize_content_block(block) -> dict:
    """SDK content block → dict.

    블록 타입 이름이 SDK 버전마다 조금씩 다를 수 있어 getattr로 방어.
    """
    block_type = type(block).__name__

    if block_type == "TextBlock" or hasattr(block, "text"):
        return {"kind": "text", "text": getattr(block, "text", "")}

    if block_type == "ToolUseBlock" or hasattr(block, "input"):
        name = getattr(block, "name", "?")
        tool_input = getattr(block, "input", {}) or {}
        summary = _summarize_tool_input(name, tool_input)
        return {
            "kind": "tool_use",
            "name": name,
            "input": tool_input,
            "summary": summary,
            "id": getattr(block, "id", None),
        }

    if block_type == "ToolResultBlock":
        content = getattr(block, "content", "")
        is_error = getattr(block, "is_error", False)
        # content가 리스트(블록의 리스트)일 수 있음
        if isinstance(content, list):
            content = "\n".join(
                getattr(c, "text", str(c)) for c in content
            )
        return {
            "kind": "tool_result",
            "is_error": bool(is_error),
            "content": str(content)[:500],
            "tool_use_id": getattr(block, "tool_use_id", None),
        }

    if block_type == "ThinkingBlock":
        return {"kind": "thinking"}

    return {"kind": "unknown", "block_type": block_type}


def _summarize_tool_input(tool_name: str, tool_input: dict) -> str:
    """도구 호출 입력값을 한 줄 요약."""
    if tool_name in ("Read", "Write", "Edit"):
        return tool_input.get("file_path", "")
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return cmd[:120]
    if tool_name in ("Glob", "Grep"):
        return tool_input.get("pattern", "")
    if tool_name == "WebFetch":
        return tool_input.get("url", "")
    return ""


def _serialize_message(msg) -> Optional[dict]:
    msg_type = type(msg).__name__

    if msg_type == "AssistantMessage":
        blocks = [
            _serialize_content_block(b) for b in getattr(msg, "content", [])
        ]
        return {"type": "assistant", "blocks": blocks}

    if msg_type == "UserMessage":
        # 도구 결과가 UserMessage에 실려 돌아오는 경우가 있음
        blocks = []
        content = getattr(msg, "content", [])
        if isinstance(content, list):
            blocks = [_serialize_content_block(b) for b in content]
        return {"type": "user_tool_result", "blocks": blocks}

    if msg_type == "SystemMessage":
        subtype = getattr(msg, "subtype", "")
        return {"type": "system", "subtype": subtype}

    if msg_type == "ResultMessage":
        return {
            "type": "result",
            "result": getattr(msg, "result", None),
            "cost_usd": getattr(msg, "total_cost_usd", None),
            "duration_ms": getattr(msg, "duration_ms", None),
            "num_turns": getattr(msg, "num_turns", None),
            "is_error": getattr(msg, "is_error", False),
        }

    return None


def _check_path_violations(event: dict) -> Optional[str]:
    """tool_use 이벤트에서 프로젝트 밖 경로 접근 시도를 탐지."""
    if event.get("type") != "assistant":
        return None
    for block in event.get("blocks", []):
        if block.get("kind") != "tool_use":
            continue
        name = block.get("name")
        if name not in ("Write", "Edit"):
            continue
        path = (block.get("input") or {}).get("file_path")
        if path and not _is_path_safe(path):
            return f"경로 차단: {path} (프로젝트 외부)"
    return None


async def run_chat(prompt: str, client_id: str) -> AsyncIterator[dict]:
    """프롬프트를 실행하고 이벤트를 순차 yield."""
    client_id = (client_id or "anonymous").strip()[:40] or "anonymous"
    prompt = (prompt or "").strip()

    if not prompt:
        yield {"type": "error", "message": "빈 프롬프트입니다."}
        return

    if len(prompt) > MAX_PROMPT_CHARS:
        yield {
            "type": "error",
            "message": f"프롬프트가 너무 깁니다 (최대 {MAX_PROMPT_CHARS}자).",
        }
        return

    if STATE.lock.locked():
        yield {
            "type": "busy",
            "current": STATE.snapshot(),
            "message": (
                f"{STATE.client_id or '다른 사용자'}님이 작업 중입니다. "
                "끝나면 다시 시도하세요."
            ),
        }
        return

    _log_prompt(client_id, prompt)

    async with STATE.lock:
        STATE.client_id = client_id
        STATE.started_at = time.time()
        STATE.current_task = asyncio.current_task()

        options = ClaudeAgentOptions(
            cwd=str(PROJECT_ROOT),
            allowed_tools=ALLOWED_TOOLS,
            permission_mode="acceptEdits",
            system_prompt={"type": "preset", "preset": "claude_code",
                           "append": SYSTEM_PROMPT_APPEND},
            max_turns=MAX_TURNS,
        )

        yield {"type": "start", "client_id": client_id}

        try:
            async for msg in query(prompt=prompt, options=options):
                event = _serialize_message(msg)
                if not event:
                    continue
                violation = _check_path_violations(event)
                if violation:
                    yield {"type": "error", "message": violation}
                    return
                yield event
                if event.get("type") == "result":
                    break
        except asyncio.CancelledError:
            yield {"type": "error", "message": "세션이 중단되었습니다."}
            raise
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "message": f"{type(e).__name__}: {e}"}
        finally:
            STATE.client_id = None
            STATE.started_at = None
            STATE.current_task = None
            yield {"type": "done"}


def list_skills() -> list[dict]:
    """`.claude/skills/*/SKILL.md`를 스캔해 이름/설명 목록 반환."""
    skills_dir = PROJECT_ROOT / ".claude" / "skills"
    out: list[dict] = []
    if not skills_dir.is_dir():
        return out
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        name = skill_dir.name
        description = ""
        try:
            text = skill_md.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass
        out.append({"name": name, "description": description})
    return out


def interrupt_current() -> bool:
    """실행 중 세션을 취소. 취소 성공 시 True."""
    task = STATE.current_task
    if task and not task.done():
        task.cancel()
        return True
    return False
