"""
Quota enforcement.

Before every request we:
  1. Load the user's plan limits (tokens_per_day, requests_per_day,
     tokens_per_minute via rolling_60s bucket).
  2. Read / upsert the matching user_quota_buckets rows.
  3. Raise 429 if any limit is exceeded.

After a request we call `record_usage` to increment the buckets.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from app.db.models import (
    LimitTypeEnum,
    Plan,
    Subscription,
    UserQuotaBucket,
    WindowTypeEnum,
)


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def _window_start(window_type: WindowTypeEnum) -> datetime:
    now = datetime.now(timezone.utc)
    if window_type == WindowTypeEnum.daily:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if window_type == WindowTypeEnum.hourly:
        return now.replace(minute=0, second=0, microsecond=0)
    if window_type == WindowTypeEnum.rolling_60s:
        return now - timedelta(seconds=60)
    return now   # per_request — not bucketed


async def _get_or_create_bucket(
    user_id: str,
    window_type: WindowTypeEnum,
    db: AsyncSession,
) -> UserQuotaBucket:
    ws = _window_start(window_type)

    # Upsert: create bucket if it doesn't exist for this window
    stmt = (
        pg_insert(UserQuotaBucket)
        .values(
            user_id=user_id,
            window_type=window_type,
            window_start=ws,
            tokens_used=0,
            requests_used=0,
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "window_type", "window_start"]
        )
    )
    await db.execute(stmt)
    await db.flush()

    bucket = await db.scalar(
        select(UserQuotaBucket).where(
            UserQuotaBucket.user_id    == user_id,
            UserQuotaBucket.window_type == window_type,
            UserQuotaBucket.window_start >= ws,
        )
    )
    return bucket


# ─── PUBLIC API ───────────────────────────────────────────────────────────────
async def check_quota(user_id: str, db: AsyncSession) -> dict:
    """
    Returns the plan limits dict so the caller can pass context_window
    to the LLM. Raises 429 if daily tokens, daily requests, or
    per-minute tokens are exceeded.
    """
    sub = await db.scalar(
        select(Subscription)
        .where(Subscription.user_id == user_id)
    )
    if not sub:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No active subscription.")

    plan: Plan = await db.scalar(
        select(Plan)
        .options(selectinload(Plan.limits))
        .where(Plan.id == sub.plan_id)
    )
    limits = {lim.limit_type: lim for lim in plan.limits}

    # ── Daily token check ────────────────────────────────────────────────────
    if LimitTypeEnum.tokens_per_day in limits:
        bucket = await _get_or_create_bucket(
            user_id, WindowTypeEnum.daily, db
        )
        if bucket and bucket.tokens_used >= limits[LimitTypeEnum.tokens_per_day].limit_value:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Daily token limit reached "
                f"({limits[LimitTypeEnum.tokens_per_day].limit_value:,}). "
                "Resets at midnight UTC."
            )

    # ── Daily request check ──────────────────────────────────────────────────
    if LimitTypeEnum.requests_per_day in limits:
        bucket = await _get_or_create_bucket(
            user_id, WindowTypeEnum.daily, db
        )
        if bucket and bucket.requests_used >= limits[LimitTypeEnum.requests_per_day].limit_value:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Daily request limit reached "
                f"({limits[LimitTypeEnum.requests_per_day].limit_value:,}). "
                "Resets at midnight UTC."
            )

    # ── Per-minute token check (rolling 60s) ─────────────────────────────────
    if LimitTypeEnum.tokens_per_minute in limits:
        bucket = await _get_or_create_bucket(
            user_id, WindowTypeEnum.rolling_60s, db
        )
        if bucket and bucket.tokens_used >= limits[LimitTypeEnum.tokens_per_minute].limit_value:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Per-minute token limit reached "
                f"({limits[LimitTypeEnum.tokens_per_minute].limit_value:,}). "
                "Try again shortly."
            )

    # Return context_window limit so chat service can truncate history
    ctx = limits.get(LimitTypeEnum.context_window)
    return {"context_window": ctx.limit_value if ctx else 8192}


async def record_usage(
    user_id:       str,
    input_tokens:  int,
    output_tokens: int,
    db:            AsyncSession,
) -> None:
    """Increment daily + rolling_60s buckets after a successful request."""
    total = input_tokens + output_tokens

    for window_type in (WindowTypeEnum.daily, WindowTypeEnum.rolling_60s):
        bucket = await _get_or_create_bucket(user_id, window_type, db)
        if bucket:
            bucket.tokens_used   += total
            bucket.requests_used += 1
            bucket.updated_at     = datetime.now(timezone.utc)

    await db.commit()