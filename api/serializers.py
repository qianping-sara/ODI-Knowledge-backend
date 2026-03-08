from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime as format_rfc1123
from typing import Any

from models.entities import ChatMessage, ChatSession


def _format_timestamp(dt: datetime) -> tuple[int, str]:
    aware = dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    milliseconds = int(aware.timestamp() * 1000)
    return milliseconds, format_rfc1123(aware)


def message_to_dict(message: ChatMessage) -> dict[str, Any]:
    created_ms, _ = _format_timestamp(message.created_at)
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "fileurls": message.file_urls or [],
        "action": [],
        "created_at": created_ms,
    }


def session_to_dict(session: ChatSession, messages: list[ChatMessage]) -> dict[str, Any]:
    created_ms, created_rfc = _format_timestamp(session.created_at)
    updated_at = session.updated_at or session.created_at
    updated_ms, updated_rfc = _format_timestamp(updated_at)
    return {
        "id": session.id,
        "chat_id": session.id,
        "name": session.name,
        "status": session.status,
        "user_id": session.user_id,
        "user_name": session.user_name,
        "user_mail": session.user_mail,
        "user_data": session.user_data,
        "created_at": session.created_at.isoformat(),
        "create_time": created_ms,
        "update_time": updated_ms,
        "create_date": created_rfc,
        "update_date": updated_rfc,
        "messages": [message_to_dict(message) for message in messages],
    }
