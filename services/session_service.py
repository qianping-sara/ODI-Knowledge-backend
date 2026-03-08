from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from models import schemas
from models.entities import ChatSession
from repositories import session_repository

MAX_SESSION_NAME_LENGTH = 255


def _normalize_session_name(name: str | None) -> str:
    if not name:
        return "New Chat"
    trimmed = name.strip()
    if not trimmed:
        return "New Chat"
    first_line = trimmed.splitlines()[0]
    return first_line[:MAX_SESSION_NAME_LENGTH]


async def create_chat_session(db: AsyncSession, payload: schemas.ChatSessionCreate) -> ChatSession:
    normalized = _normalize_session_name(payload.name)
    return await session_repository.create_session(db, name=normalized)


async def list_chat_sessions(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    orderby: str,
    descending: bool,
    session_id: str | None = None,
    name: str | None = None,
) -> list[ChatSession]:
    return await session_repository.list_sessions(
        db,
        page=page,
        page_size=page_size,
        orderby=orderby,
        descending=descending,
        session_id=session_id,
        name=name,
    )


async def get_chat_session(db: AsyncSession, session_id: str) -> ChatSession | None:
    return await session_repository.get_session(db, session_id)


async def rename_chat_session(
    db: AsyncSession, session_id: str, payload: schemas.ChatSessionRename
) -> ChatSession | None:
    normalized = _normalize_session_name(payload.name)
    return await session_repository.rename_session(db, session_id, normalized)


async def update_chat_session_status(
    db: AsyncSession, session_id: str, status: str
) -> ChatSession | None:
    cleaned = status.strip() if isinstance(status, str) else ""
    if not cleaned:
        raise ValueError("status must not be empty.")
    return await session_repository.update_status(db, session_id, cleaned)


async def delete_chat_sessions(db: AsyncSession, session_ids: list[str]) -> int:
    return await session_repository.delete_sessions(db, session_ids)
