from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent.agent_adapter import run_agent, run_agent_stream
from models import schemas
from models.entities import ChatMessage as ChatMessageEntity
from models.entities import ChatSession
from repositories import message_repository, session_repository
from services.sse_service import process_event_from_agent


def _to_agent_message(entity: ChatMessageEntity) -> dict[str, str]:
    role = "assistant" if entity.role == "assistant" else "user"
    return {"role": role, "content": entity.content or ""}


async def send_chat_message(
    db: AsyncSession,
    session_id: str,
    payload: schemas.ChatMessageCreate,
) -> tuple[ChatSession, ChatMessageEntity, ChatMessageEntity] | None:
    session = await session_repository.get_session(db, session_id)
    if session is None:
        return None

    cleaned_file_urls = [str(url).strip() for url in (payload.file_urls or []) if str(url).strip()]

    user_message = await message_repository.create_message(
        db,
        session_id,
        "user",
        payload.question or "",
        file_urls=cleaned_file_urls,
    )

    history_entities = await message_repository.list_messages(db, session_id)
    agent_messages = [_to_agent_message(message) for message in history_entities]

    assistant_text = await run_agent(agent_messages)

    assistant_message = await message_repository.create_message(
        db,
        session_id,
        "assistant",
        assistant_text,
        file_urls=[],
    )

    return session, user_message, assistant_message


async def send_chat_message_stream(
    db: AsyncSession,
    session_id: str,
    payload: schemas.ChatMessageCreate,
    event_queue: asyncio.Queue[dict[str, Any]],
) -> tuple[ChatSession, ChatMessageEntity, ChatMessageEntity] | None:
    """Send chat message using run_agent_stream; put process events to queue."""
    session = await session_repository.get_session(db, session_id)
    if session is None:
        return None

    cleaned_file_urls = [str(url).strip() for url in (payload.file_urls or []) if str(url).strip()]

    user_message = await message_repository.create_message(
        db,
        session_id,
        "user",
        payload.question or "",
        file_urls=cleaned_file_urls,
    )

    history_entities = await message_repository.list_messages(db, session_id)
    agent_messages = [_to_agent_message(message) for message in history_entities]

    loop = asyncio.get_running_loop()

    def on_process(agent_event: dict[str, Any]) -> None:
        sse_event = process_event_from_agent(agent_event, session_id)
        loop.call_soon_threadsafe(event_queue.put_nowait, sse_event)

    assistant_text = await run_agent_stream(agent_messages, event_callback=on_process)

    assistant_message = await message_repository.create_message(
        db,
        session_id,
        "assistant",
        assistant_text,
        file_urls=[],
    )

    return session, user_message, assistant_message


async def get_chat_history(db: AsyncSession, session_id: str) -> list[ChatMessageEntity]:
    return await message_repository.list_messages(db, session_id)


def has_nonempty_content(payload: schemas.ChatMessageCreate) -> bool:
    if payload.question and payload.question.strip():
        return True
    for item in payload.file_urls or []:
        if isinstance(item, str) and item.strip():
            return True
    return False
