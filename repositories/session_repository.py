from __future__ import annotations

from sqlalchemy import Select, asc, delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.entities import ChatSession


async def create_session(
    db: AsyncSession,
    *,
    name: str,
    status: str = "open",
    user_id: str | None = None,
    user_name: str | None = None,
    user_mail: str | None = None,
    user_data: dict | None = None,
) -> ChatSession:
    session = ChatSession(
        name=name,
        status=status,
        user_id=user_id,
        user_name=user_name,
        user_mail=user_mail,
        user_data=user_data,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


def _apply_filters(query: Select, *, session_id: str | None, name: str | None) -> Select:
    if session_id:
        query = query.where(ChatSession.id == session_id)
    if name:
        query = query.where(ChatSession.name.ilike(f"%{name}%"))
    return query


async def list_sessions(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    orderby: str,
    descending: bool,
    session_id: str | None = None,
    name: str | None = None,
) -> list[ChatSession]:
    order_column = ChatSession.updated_at if orderby == "updated_at" else ChatSession.created_at
    order_expression = desc(order_column) if descending else asc(order_column)
    query = select(ChatSession).order_by(order_expression)
    query = _apply_filters(query, session_id=session_id, name=name)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_session(db: AsyncSession, session_id: str) -> ChatSession | None:
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    return result.scalars().first()


async def rename_session(db: AsyncSession, session_id: str, name: str) -> ChatSession | None:
    session = await get_session(db, session_id)
    if session is None:
        return None
    session.name = name
    await db.flush()
    await db.refresh(session)
    return session


async def update_status(db: AsyncSession, session_id: str, status: str) -> ChatSession | None:
    session = await get_session(db, session_id)
    if session is None:
        return None
    session.status = status
    await db.flush()
    await db.refresh(session)
    return session


async def fetch_existing_ids(db: AsyncSession, session_ids: list[str]) -> set[str]:
    if not session_ids:
        return set()
    result = await db.execute(select(ChatSession.id).where(ChatSession.id.in_(session_ids)))
    return {row[0] for row in result}


async def delete_sessions(db: AsyncSession, session_ids: list[str]) -> int:
    if not session_ids:
        return 0
    result = await db.execute(delete(ChatSession).where(ChatSession.id.in_(session_ids)))
    return result.rowcount or 0
