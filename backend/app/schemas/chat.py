from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# ─── REQUEST ──────────────────────────────────────────────────────────────────
class ChatCreateRequest(BaseModel):
    message: str
    model:   str = "llama-3.3-70b-versatile"


class MessageRequest(BaseModel):
    message: str


# ─── RESPONSE ─────────────────────────────────────────────────────────────────
class MessageOut(BaseModel):
    id:         UUID
    role:       str
    content:    str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatOut(BaseModel):
    id:                UUID
    title:             str | None
    model:             str
    created_at:        datetime
    total_tokens_used: int

    model_config = {"from_attributes": True}


class ChatDetailOut(ChatOut):
    messages: list[MessageOut] = []


class TokenUsageOut(BaseModel):
    input_tokens:  int
    output_tokens: int
    total_tokens:  int
    model:         str
    created_at:    datetime

    model_config = {"from_attributes": True}