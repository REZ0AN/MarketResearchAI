from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import send_password_reset_email, send_verification_email
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_urlsafe_token,
    hash_password,
    verify_password,
)
from app.db.models import Plan, Subscription, User


# ─── REGISTER ─────────────────────────────────────────────────────────────────
async def register_user(email: str, password: str, db: AsyncSession) -> User:
    # Check duplicate
    existing = await db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered.")

    token = generate_urlsafe_token()
    user  = User(
        email=email,
        hashed_password=hash_password(password),
        verification_token=token,
    )
    db.add(user)
    await db.flush()   # get user.id before commit

    # Assign free plan
    free_plan = await db.scalar(select(Plan).where(Plan.name == "free"))
    if free_plan:
        db.add(Subscription(user_id=user.id, plan_id=free_plan.id))

    await db.commit()
    await db.refresh(user)

    # Send verification email (fire-and-forget — don't block response)
    try:
        await send_verification_email(email, token)
    except Exception:
        pass   # log in production; never crash registration over email failure

    return user


# ─── VERIFY EMAIL ─────────────────────────────────────────────────────────────
async def verify_email(token: str, db: AsyncSession) -> None:
    user = await db.scalar(
        select(User).where(User.verification_token == token)
    )
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token.")
    if user.is_verified:
        return   # idempotent

    user.is_verified        = True
    user.verification_token = None
    await db.commit()


# ─── LOGIN ────────────────────────────────────────────────────────────────────
async def login_user(email: str, password: str, db: AsyncSession) -> dict:
    user = await db.scalar(select(User).where(User.email == email))

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials.")
    if not user.is_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please verify your email first.")

    return {
        "access_token":  create_access_token(str(user.id)),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type":    "bearer",
    }


# ─── REFRESH ──────────────────────────────────────────────────────────────────
async def refresh_tokens(refresh_token: str, db: AsyncSession) -> dict:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token.")

    user = await db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found.")

    return {
        "access_token":  create_access_token(str(user.id)),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type":    "bearer",
    }


# ─── FORGOT PASSWORD ──────────────────────────────────────────────────────────
async def forgot_password(email: str, db: AsyncSession) -> None:
    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        return   # Don't leak whether email exists

    token               = generate_urlsafe_token()
    user.reset_token     = token
    user.reset_token_exp = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.commit()

    try:
        await send_password_reset_email(email, token)
    except Exception:
        pass


# ─── RESET PASSWORD ───────────────────────────────────────────────────────────
async def reset_password(token: str, new_password: str, db: AsyncSession) -> None:
    user = await db.scalar(select(User).where(User.reset_token == token))

    if not user or not user.reset_token_exp:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token.")
    if user.reset_token_exp < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token has expired.")

    user.hashed_password = hash_password(new_password)
    user.reset_token     = None
    user.reset_token_exp = None
    await db.commit()