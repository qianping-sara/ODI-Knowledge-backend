from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.responses import error, success
from api.serializers import session_to_dict
from core.database import get_db_session
from models import schemas
from repositories import message_repository
from services import session_service

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.post("/sessions")
async def create_session(
    payload: schemas.ChatSessionCreate | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    session = await session_service.create_chat_session(db, payload or schemas.ChatSessionCreate())
    await db.commit()
    await db.refresh(session)
    data = session_to_dict(session, [])
    return success(data=data)


@router.get("/sessions")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    orderby: str = Query("updated_at", pattern="^(updated_at|created_at)$"),
    desc: bool = Query(True),
    name: str | None = None,
    id: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    sessions = await session_service.list_chat_sessions(
        db,
        page=page,
        page_size=page_size,
        orderby=orderby,
        descending=desc,
        session_id=id,
        name=name,
    )
    data: list[dict[str, Any]] = []
    for session in sessions:
        history_entities = await message_repository.list_messages(db, session.id)
        data.append(session_to_dict(session, history_entities))
    if id and not data:
        return error(400, "The session doesn't exist", status_code=400)
    return success(data=data)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db_session)):
    session = await session_service.get_chat_session(db, session_id)
    if session is None:
        return error(404, "Session not found", status_code=404)
    history = await message_repository.list_messages(db, session.id)
    return success(data=session_to_dict(session, history))


@router.put("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    payload: schemas.ChatSessionRename,
    db: AsyncSession = Depends(get_db_session),
):
    renamed = await session_service.rename_chat_session(db, session_id, payload)
    if renamed is None:
        return error(404, "Session not found", status_code=404)
    await db.commit()
    return success()


@router.put("/sessions/{session_id}/status")
async def update_session_status(
    session_id: str,
    payload: schemas.ChatSessionStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        updated = await session_service.update_chat_session_status(db, session_id, payload.status)
    except ValueError as exc:
        return error(400, str(exc), status_code=400)
    if updated is None:
        return error(404, "Session not found", status_code=404)
    await db.commit()
    return success()


@router.delete("/sessions")
async def delete_sessions(
    payload: schemas.ChatSessionDelete,
    db: AsyncSession = Depends(get_db_session),
):
    if not payload.ids:
        return error(400, "ids must not be empty.")
    existing = await session_service.delete_chat_sessions(db, payload.ids)
    await db.commit()
    if existing == 0:
        return error(404, "Session not found", status_code=404)
    return success()
