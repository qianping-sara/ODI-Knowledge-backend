from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    name: str | None = Field(default=None, max_length=255)


class ChatSessionRename(BaseModel):
    name: str = Field(max_length=255)


class ChatSessionStatusUpdate(BaseModel):
    status: str


class ChatSessionDelete(BaseModel):
    ids: list[str]


class ChatMessageCreate(BaseModel):
    question: str | None = None
    file_urls: list[str | None] | None = None


class CompletionRequest(ChatMessageCreate):
    session_id: str | None = None
    stream: bool = True


class ChatMessageRead(BaseModel):
    id: int
    role: str
    content: str
    fileurls: list[str] = Field(default_factory=list)
    action: list[Any] = Field(default_factory=list)
    created_at: int
