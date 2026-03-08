from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.responses import error, success
from core.database import get_db_session
from models import schemas
from services import chat_service, session_service
from services.sse_service import end_event, error_event, final_event, progress_event

router = APIRouter(prefix="/api/v1", tags=["completions"])


def _build_completion_payload(session_id: str, user_message, assistant_message) -> dict:
    return {
        "answer": assistant_message.content,
        "fileurls": assistant_message.file_urls or [],
        "id": str(assistant_message.id),
        "answer_id": str(assistant_message.id),
        "question_id": str(user_message.id),
        "action": [],
        "session_id": session_id,
    }


@router.post("/completions")
async def completions(
    payload: schemas.CompletionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    if not chat_service.has_nonempty_content(payload):
        return error(400, "Question cannot be empty.")

    session_id = payload.session_id
    if not session_id:
        session = await session_service.create_chat_session(db, schemas.ChatSessionCreate())
        await db.commit()
        await db.refresh(session)
        session_id = session.id
    else:
        session = await session_service.get_chat_session(db, session_id)
        if session is None:
            return error(404, "Session not found", status_code=404)

    async def _run_chat() -> dict | None:
        result = await chat_service.send_chat_message(
            db,
            session_id,
            schemas.ChatMessageCreate(
                question=payload.question,
                file_urls=payload.file_urls,
            ),
        )
        if result is None:
            return None
        _, user_message, assistant_message = result
        await db.commit()
        return _build_completion_payload(session_id, user_message, assistant_message)

    if payload.stream:
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def run_flow() -> None:
            try:
                await queue.put(progress_event(session_id))
                result = await chat_service.send_chat_message_stream(
                    db,
                    session_id,
                    schemas.ChatMessageCreate(
                        question=payload.question,
                        file_urls=payload.file_urls,
                    ),
                    event_queue=queue,
                )
                if result is None:
                    await queue.put(error_event(session_id, "Session not found"))
                else:
                    await db.commit()
                    _, user_message, assistant_message = result
                    response_payload = _build_completion_payload(
                        session_id, user_message, assistant_message
                    )
                    await queue.put(final_event(response_payload))
            except Exception as exc:  # pragma: no cover
                await queue.put(error_event(session_id, str(exc)))
            await queue.put(end_event())

        task = asyncio.create_task(run_flow())

        async def event_stream():
            try:
                while True:
                    event = await queue.get()
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    if event.get("data") is True:
                        break
            finally:
                if not task.done():
                    task.cancel()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    response_payload = await _run_chat()
    if response_payload is None:
        return error(404, "Session not found", status_code=404)
    return success(data=response_payload)
