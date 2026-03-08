from __future__ import annotations

import asyncio
import importlib.util
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)
_AGENT = None

# Node names used by deepagents / LangGraph for model and tools
MODEL_NODE_NAMES = ("model_request", "call_model", "model")
TOOLS_NODE_NAME = "tools"


def _load_agent():
    global _AGENT  # noqa: PLW0603
    if _AGENT is not None:
        return _AGENT
    try:
        project_root = Path(__file__).resolve().parents[1]
        agent_path = project_root / "agent" / "entry.py"
        spec = importlib.util.spec_from_file_location("agent_entry", agent_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _AGENT = getattr(module, "agent", None)
        return _AGENT
    except Exception:
        _AGENT = None
        return None


def _extract_last_message_content(messages: list[Any]) -> str:
    if not messages:
        return ""
    last = messages[-1]
    if hasattr(last, "content"):
        return str(last.content)
    if isinstance(last, dict):
        return str(last.get("content") or "")
    return str(last)


async def run_agent(messages: list[dict[str, str]]) -> str:
    agent = _load_agent()
    if agent is None:
        return "(stub response) Agent not configured."

    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = (m.get("content") or "")[:100]
            if len(m.get("content") or "") > 100:
                last_user += "…"
            break

    logger.info("[Agent] START user_message=%r (history_len=%d)", last_user, len(messages))

    def _invoke():
        result = agent.invoke({"messages": messages})
        if isinstance(result, dict) and "messages" in result:
            return _extract_last_message_content(result["messages"])
        return ""

    response = await asyncio.to_thread(_invoke)
    logger.info("[Agent] END response_len=%d", len(response))
    return response


def _run_agent_stream_sync(
    messages: list[dict[str, str]],
    event_callback: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    """Run agent with stream_mode='updates', parse tool events, return final answer."""
    agent = _load_agent()
    if agent is None:
        return "(stub response) Agent not configured."

    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = (m.get("content") or "")[:100]
            if len(m.get("content") or "") > 100:
                last_user += "…"
            break

    logger.info("[Agent] STREAM START user_message=%r (history_len=%d)", last_user, len(messages))

    # Map tool_call_id -> tool_name for pairing tool_end (ToolMessage may not have name)
    tool_call_id_to_name: dict[str, str] = {}
    final_answer = ""

    def _emit(event: dict[str, Any]) -> None:
        logger.info(
            "[Agent] process event subtype=%s tool=%s tool_call_id=%s",
            event.get("subtype"),
            event.get("tool_name"),
            event.get("tool_call_id"),
        )
        if event_callback:
            event_callback(event)

    try:
        # stream_mode="updates" yields per-node updates
        for update in agent.stream(
            {"messages": messages},
            stream_mode="updates",
            subgraphs=False,
        ):
            # Handle (namespace, chunk) or (node_name, output) or chunk-only
            node_items: list[tuple[str, Any]] = []
            if isinstance(update, (list, tuple)) and len(update) >= 2:
                first, second = update[0], update[1]
                if isinstance(second, dict) and (first is None or first == () or isinstance(first, (tuple, list))):
                    # (namespace, {node: data})
                    chunk = second
                    logger.debug("[Agent] stream (namespace,chunk) chunk_keys=%s", _safe_keys(chunk))
                    node_items = list(chunk.items()) if isinstance(chunk, dict) else []
                elif isinstance(second, dict) and first and not isinstance(first, (tuple, list)):
                    # (node_name, output)
                    logger.debug("[Agent] stream (node_name,output) node=%s keys=%s", first, _safe_keys(second))
                    node_items = [(str(first), second)]
                else:
                    logger.debug("[Agent] stream tuple first=%r second_type=%s", first, type(second))
                    continue
            elif isinstance(update, dict):
                logger.debug("[Agent] stream chunk_keys=%s", _safe_keys(update))
                node_items = list(update.items()) if update else []
            else:
                logger.debug("[Agent] stream raw update type=%s repr=%s", type(update).__name__, _truncate(repr(update), 200))
                continue

            for node_name, data in node_items:
                # Node output: {"messages": [...]} or [message, ...]
                if isinstance(data, dict):
                    messages_list = data.get("messages") or []
                elif isinstance(data, list):
                    messages_list = data
                else:
                    continue

                # Model node: extract tool_calls (tool_start) or final AIMessage (no tool_calls)
                if node_name in MODEL_NODE_NAMES:
                    for msg in messages_list:
                        tool_calls = getattr(msg, "tool_calls", None) or []
                        if tool_calls:
                            for tc in tool_calls:
                                tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                                tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                                tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {}) or {}
                                if tc_id and tc_name:
                                    tool_call_id_to_name[tc_id] = tc_name
                                    evt = {
                                        "subtype": "tool_start",
                                        "tool_call_id": tc_id,
                                        "tool_name": tc_name,
                                        "input": tc_args if isinstance(tc_args, dict) else {},
                                    }
                                    _emit(evt)
                                    logger.info(
                                        "[Agent] tool_start tool_name=%s tool_call_id=%s input=%s",
                                        tc_name,
                                        tc_id,
                                        _truncate(str(tc_args), 120),
                                    )
                        else:
                            content = getattr(msg, "content", None) or ""
                            if content and isinstance(content, str):
                                final_answer = content
                                logger.info(
                                    "[Agent] final AIMessage len=%d preview=%s",
                                    len(final_answer),
                                    _truncate(final_answer, 80),
                                )

                # Tools node: extract tool results (tool_end)
                elif node_name == TOOLS_NODE_NAME:
                    for msg in messages_list:
                        msg_type = getattr(msg, "type", None) or (
                            msg.__class__.__name__ if hasattr(msg, "__class__") else None
                        )
                        is_tool = msg_type == "tool" or "ToolMessage" in str(type(msg).__name__)
                        if not is_tool:
                            continue
                        tc_id = getattr(msg, "tool_call_id", None)
                        content = getattr(msg, "content", None) or ""
                        name = getattr(msg, "name", None) or tool_call_id_to_name.get(tc_id or "", "unknown")
                        if tc_id:
                            evt = {
                                "subtype": "tool_end",
                                "tool_call_id": tc_id,
                                "tool_name": name,
                                "output_raw": str(content),
                            }
                            _emit(evt)
                            logger.info(
                                "[Agent] tool_end tool_name=%s tool_call_id=%s output_len=%d preview=%s",
                                name,
                                tc_id,
                                len(str(content)),
                                _truncate(str(content), 120),
                            )

    except Exception as exc:
        logger.exception("[Agent] STREAM error: %s", exc)
        raise

    logger.info("[Agent] STREAM END response_len=%d", len(final_answer))
    return final_answer


def _safe_keys(obj: Any) -> list[str]:
    """Safely get keys from dict for logging."""
    if isinstance(obj, dict):
        return list(obj.keys())
    return []


def _truncate(s: str, max_len: int) -> str:
    """Truncate string for logging."""
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


async def run_agent_stream(
    messages: list[dict[str, str]],
    event_callback: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    """Run agent with stream_mode='updates', emit tool events via callback, return final answer."""
    return await asyncio.to_thread(_run_agent_stream_sync, messages, event_callback)
