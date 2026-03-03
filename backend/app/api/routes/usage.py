from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_verified_user
from app.db.models import TokenUsage, User, UserQuotaBucket
from app.db.session import get_db
from app.schemas.chat import TokenUsageOut

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/tokens", response_model=list[TokenUsageOut])
async def token_history(
    limit: int         = 20,
    user:  User        = Depends(get_verified_user),
    db:    AsyncSession = Depends(get_db),
):
    """Last N token usage records for the current user."""
    rows = await db.execute(
        select(TokenUsage)
        .where(TokenUsage.user_id == user.id)
        .order_by(TokenUsage.created_at.desc())
        .limit(limit)
    )
    return rows.scalars().all()


@router.get("/quota")
async def quota_status(
    user: User         = Depends(get_verified_user),
    db:   AsyncSession = Depends(get_db),
):
    """Returns current bucket usage vs plan limits for the dashboard."""
    from app.db.models import LimitTypeEnum, Plan, Subscription
    from app.services.quota import _window_start, WindowTypeEnum
    from sqlalchemy.orm import selectinload

    sub = await db.scalar(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    plan: Plan = await db.scalar(
        select(Plan)
        .options(selectinload(Plan.limits))
        .where(Plan.id == sub.plan_id)
    )
    limits     = {lim.limit_type: lim.limit_value for lim in plan.limits}

    # Daily bucket
    daily_ws = _window_start(WindowTypeEnum.daily)
    daily    = await db.scalar(
        select(UserQuotaBucket).where(
            UserQuotaBucket.user_id     == user.id,
            UserQuotaBucket.window_type == WindowTypeEnum.daily,
            UserQuotaBucket.window_start >= daily_ws,
        )
    )

    # Rolling 60s bucket
    minute_ws = _window_start(WindowTypeEnum.rolling_60s)
    minute    = await db.scalar(
        select(UserQuotaBucket).where(
            UserQuotaBucket.user_id     == user.id,
            UserQuotaBucket.window_type == WindowTypeEnum.rolling_60s,
            UserQuotaBucket.window_start >= minute_ws,
        )
    )

    return {
        "plan": plan.name,
        "daily": {
            "tokens_used":    daily.tokens_used    if daily  else 0,
            "requests_used":  daily.requests_used  if daily  else 0,
            "tokens_limit":   limits.get(LimitTypeEnum.tokens_per_day,   0),
            "requests_limit": limits.get(LimitTypeEnum.requests_per_day, 0),
        },
        "per_minute": {
            "tokens_used":  minute.tokens_used if minute else 0,
            "tokens_limit": limits.get(LimitTypeEnum.tokens_per_minute, 0),
        },
        "context_window": limits.get(LimitTypeEnum.context_window, 8192),
    }