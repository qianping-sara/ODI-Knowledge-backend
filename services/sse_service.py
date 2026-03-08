from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def wrap_event(payload: dict[str, Any], *, code: int = 0) -> dict[str, Any]:
    return {"code": code, "data": payload}


def progress_event(session_id: str, *, phase: str = "analysis", status: str = "running") -> dict[str, Any]:
    return wrap_event(
        {
            "type": "progress",
            "phase": phase,
            "status": status,
            "session_id": session_id,
            "ts": _now_iso(),
        }
    )


def final_event(payload: dict[str, Any]) -> dict[str, Any]:
    final_payload = dict(payload)
    final_payload["type"] = "final"
    return wrap_event(final_payload)


def end_event() -> dict[str, Any]:
    return wrap_event(True)


def error_event(session_id: str, message: str) -> dict[str, Any]:
    return wrap_event(
        {
            "type": "error",
            "session_id": session_id,
            "message": message,
            "ts": _now_iso(),
        },
        code=1,
    )


def _process_base(session_id: str, subtype: str, tool_name: str, tool_call_id: str, **extra: Any) -> dict[str, Any]:
    """Base for process events (tool_start / tool_end)."""
    payload: dict[str, Any] = {
        "type": "process",
        "subtype": subtype,
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "session_id": session_id,
        "ts": _now_iso(),
    }
    payload.update(extra)
    return wrap_event(payload)


def process_event_tool_start(
    session_id: str,
    tool_name: str,
    tool_call_id: str,
    input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """SSE process event: tool invocation started."""
    return _process_base(
        session_id,
        subtype="tool_start",
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        input=input or {},
    )


def process_event_tool_end(
    session_id: str,
    tool_name: str,
    tool_call_id: str,
    output_raw: str,
    *,
    status: str = "completed",
    output_preview: str | None = None,
    output_json: Any = None,
    error: str | None = None,
) -> dict[str, Any]:
    """SSE process event: tool invocation completed."""
    preview = output_preview if output_preview is not None else (output_raw[:200] + "…" if len(output_raw) > 200 else output_raw)
    payload: dict[str, Any] = {
        "status": status,
        "output_preview": preview,
        "output_raw": output_raw,
    }
    if output_json is not None:
        payload["output_json"] = output_json
    if error is not None:
        payload["error"] = error
    return _process_base(
        session_id,
        subtype="tool_end",
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        **payload,
    )


# output_preview max length
OUTPUT_PREVIEW_MAX_LEN = 200

# Error detection: prefixes that indicate tool returned an error string
_TOOL_ERROR_PREFIXES = ("error ", "error:", "failed to ", "exception:", "traceback")
# Regex for "Error " or "Error:" at start (case insensitive)
_TOOL_ERROR_START = re.compile(r"^\s*error[\s:]", re.IGNORECASE)


def _detect_tool_error(output_raw: str) -> tuple[bool, str | None]:
    """Detect if output indicates a tool error. Returns (is_error, error_message)."""
    s = output_raw.strip()
    if not s:
        return False, None

    # 1. Starts with "Error " or "Error:"
    if _TOOL_ERROR_START.match(s):
        return True, (s[:500] + "…" if len(s) > 500 else s)

    # 2. Starts with known error prefixes
    lower = s.lower()
    for prefix in _TOOL_ERROR_PREFIXES:
        if lower.startswith(prefix):
            return True, (s[:500] + "…" if len(s) > 500 else s)

    # 3. Parsable as JSON with success: false
    try:
        obj = json.loads(s)
        if isinstance(obj, dict) and obj.get("success") is False:
            err = obj.get("error", obj.get("message", s))
            err_str = err if isinstance(err, str) else json.dumps(err, ensure_ascii=False)
            return True, (err_str[:500] + "…" if len(err_str) > 500 else err_str)
    except (json.JSONDecodeError, TypeError):
        pass

    return False, None


def _parse_output_json(output_raw: str, tool_name: str) -> Any | None:
    """Try to parse output_raw as JSON and extract useful structure for frontend.

    PageIndex / tools may return:
    - Plain text (common for chat_completions)
    - JSON like {"content":[{"type":"text","text":"..."}]}
    - JSON with docs: {"docs":[...], "success":true}
    """
    if not output_raw or not output_raw.strip():
        return None

    s = output_raw.strip()

    # Direct JSON parse
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            # Keep structure if it has useful keys
            if any(k in obj for k in ("docs", "content", "documents", "results")):
                return obj
            # Flatten content array if present (PageIndex style)
            if "content" in obj and isinstance(obj["content"], list):
                return obj
        return None
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to find JSON substring (e.g. text wrapping JSON)
    if "{" in s and "}" in s:
        try:
            start = s.index("{")
            end = s.rindex("}") + 1
            obj = json.loads(s[start:end])
            if isinstance(obj, dict) and any(
                k in obj for k in ("docs", "content", "documents", "success")
            ):
                return obj
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    return None


def process_event_from_agent(agent_event: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Convert agent_adapter event to SSE process event."""
    subtype = agent_event.get("subtype")
    tool_name = agent_event.get("tool_name", "unknown")
    tool_call_id = agent_event.get("tool_call_id", "")
    if subtype == "tool_start":
        return process_event_tool_start(
            session_id=session_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            input=agent_event.get("input"),
        )
    if subtype == "tool_end":
        output_raw = agent_event.get("output_raw", "")
        output_preview = (
            output_raw[:OUTPUT_PREVIEW_MAX_LEN] + "…"
            if len(output_raw) > OUTPUT_PREVIEW_MAX_LEN
            else output_raw
        )
        is_error, error_msg = _detect_tool_error(output_raw)
        status = "error" if is_error else "completed"
        output_json = None if is_error else _parse_output_json(output_raw, tool_name)
        return process_event_tool_end(
            session_id=session_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            output_raw=output_raw,
            status=status,
            output_preview=output_preview,
            output_json=output_json,
            error=error_msg,
        )
    # Fallback: wrap as generic process
    return _process_base(
        session_id,
        subtype=subtype or "unknown",
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        **{k: v for k, v in agent_event.items() if k not in ("subtype", "tool_name", "tool_call_id")},
    )
