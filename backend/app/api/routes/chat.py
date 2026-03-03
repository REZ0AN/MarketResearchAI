from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_verified_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.chat import ChatDetailOut, ChatOut, ChatCreateRequest, MessageRequest
from app.services.chat import delete_chat, get_chat, list_chats, stream_chat

router = APIRouter(prefix="/chats", tags=["chat"])


@router.get("", response_model=list[ChatOut])
async def get_chats(
    user: User             = Depends(get_verified_user),
    db:   AsyncSession     = Depends(get_db),
):
    return await list_chats(user, db)


@router.get("/{chat_id}", response_model=ChatDetailOut)
async def get_chat_detail(
    chat_id: str,
    user:    User          = Depends(get_verified_user),
    db:      AsyncSession  = Depends(get_db),
):
    return await get_chat(chat_id, user, db)


@router.delete("/{chat_id}", status_code=204)
async def remove_chat(
    chat_id: str,
    user:    User          = Depends(get_verified_user),
    db:      AsyncSession  = Depends(get_db),
):
    await delete_chat(chat_id, user, db)


@router.post("/stream")
async def stream_new_chat(
    body: ChatCreateRequest,
    user: User             = Depends(get_verified_user),
    db:   AsyncSession     = Depends(get_db),
):
    """Start a brand-new chat and stream the first response."""
    return StreamingResponse(
        stream_chat(
            user=user,
            message=body.message,
            model=body.model,
            db=db,
        ),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},  # disable nginx buffering
    )


@router.post("/{chat_id}/stream")
async def stream_existing_chat(
    chat_id: str,
    body:    MessageRequest,
    user:    User          = Depends(get_verified_user),
    db:      AsyncSession  = Depends(get_db),
):
    """Continue an existing chat and stream the next response."""
    return StreamingResponse(
        stream_chat(
            user=user,
            message=body.message,
            model="llama-3.3-70b-versatile",
            db=db,
            chat_id=chat_id,
        ),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )