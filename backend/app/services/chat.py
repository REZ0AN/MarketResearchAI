"""
Chat service — creates chats, appends messages, streams Groq responses,
and records token usage.
"""

import json
from typing import AsyncGenerator

from fastapi import HTTPException, status
from langchain_groq import ChatGroq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import Chat, Message, User
from app.services.quota import check_quota, record_usage
from app.services.token_counter import estimate_tokens, save_token_usage


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def _make_llm(model: str) -> ChatGroq:
    return ChatGroq(
        model=model,
        temperature=0.7,
        streaming=True,
        api_key=settings.GROQ_API_KEY,
    )


def _build_title(text: str) -> str:
    return text.strip()[:60] or "New Chat"


def _trim_history(messages: list[Message], context_window: int) -> list[dict]:
    """
    Convert DB messages → LangChain dicts, trimming oldest messages
    if estimated token count exceeds the plan's context_window.
    """
    lc_msgs = [{"role": m.role, "content": m.content} for m in messages]
    total   = sum(estimate_tokens(m["content"]) for m in lc_msgs)
    while total > context_window and len(lc_msgs) > 1:
        removed = lc_msgs.pop(0)
        total  -= estimate_tokens(removed["content"])
    return lc_msgs


# ─── CHAT CRUD ────────────────────────────────────────────────────────────────
async def list_chats(user: User, db: AsyncSession) -> list[Chat]:
    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == user.id)
        .order_by(Chat.created_at.desc())
    )
    return result.scalars().all()


async def get_chat(chat_id: str, user: User, db: AsyncSession) -> Chat:
    chat = await db.scalar(
        select(Chat)
        .options(selectinload(Chat.messages))
        .where(Chat.id == chat_id, Chat.user_id == user.id)
    )
    if not chat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found.")
    return chat


async def delete_chat(chat_id: str, user: User, db: AsyncSession) -> None:
    chat = await db.scalar(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id)
    )
    if not chat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found.")
    await db.delete(chat)
    await db.commit()


# ─── STREAMING ────────────────────────────────────────────────────────────────
async def stream_chat(
    user:     User,
    message:  str,
    model:    str,
    db:       AsyncSession,
    chat_id:  str | None = None,
) -> AsyncGenerator[str, None]:
    """
    SSE generator. Yields:
      data: {"chat_id": "..."}           — sent first so client can track
      data: {"token": "..."}             — streamed assistant tokens
      data: {"usage": {...}}             — final token counts
      data: [DONE]                       — stream closed
    """

    # 1. Quota check (raises 429 if exceeded)
    limits = await check_quota(str(user.id), db)
    ctx    = limits["context_window"]

    # 2. Get or create chat — always eager-load messages
    if chat_id:
        chat = await db.scalar(
            select(Chat)
            .options(selectinload(Chat.messages))
            .where(Chat.id == chat_id, Chat.user_id == user.id)
        )
        if not chat:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found.")
        prior_messages: list[Message] = list(chat.messages)
    else:
        chat = Chat(
            user_id=user.id,
            model=model,
            title=_build_title(message),
        )
        db.add(chat)
        await db.flush()          # get chat.id without committing
        prior_messages = []       # brand-new chat has no history

    # 3. Persist user message
    user_msg = Message(chat_id=chat.id, role="user", content=message)
    db.add(user_msg)
    await db.flush()

    # 4. Build LLM history from prior messages + new user message
    all_messages = prior_messages + [user_msg]
    history      = _trim_history(all_messages, ctx)
    input_tokens = sum(estimate_tokens(m["content"]) for m in history)

    # 5. Yield chat_id first so the client can store it
    yield f"data: {json.dumps({'chat_id': str(chat.id)})}\n\n"

    # 6. Stream LLM response
    llm           = _make_llm(model)
    full_response = ""

    try:
        async for chunk in llm.astream(history):
            token = chunk.content
            if token:
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        await db.rollback()
        return

    # 7. Persist assistant reply
    db.add(Message(chat_id=chat.id, role="assistant", content=full_response))

    # 8. Save token usage + update quota buckets
    output_tokens = estimate_tokens(full_response)
    await save_token_usage(db, chat, input_tokens, output_tokens, model)
    await record_usage(str(user.id), input_tokens, output_tokens, db)

    # 9. Final commit (covers chat, messages, token_usage in one shot)
    await db.commit()

    # 10. Yield usage summary and close
    yield f"data: {json.dumps({'usage': {'input': input_tokens, 'output': output_tokens, 'total': input_tokens + output_tokens}})}\n\n"
    yield "data: [DONE]\n\n"