from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.responses import error, success
from api.serializers import message_to_dict
from core.database import get_db_session
from services import chat_service, session_service

router = APIRouter(prefix="/api/v1", tags=["messages"])


@router.get("/sessions/{session_id}/messages")
async def list_messages(session_id: str, db: AsyncSession = Depends(get_db_session)):
    session = await session_service.get_chat_session(db, session_id)
    if session is None:
        return error(404, "Session not found", status_code=404)
    history = await chat_service.get_chat_history(db, session_id)
    return success(data=[message_to_dict(item) for item in history])
