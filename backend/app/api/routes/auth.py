from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_verified_user
from app.db.session import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
)
from app.services.auth import (
    forgot_password,
    login_user,
    refresh_tokens,
    register_user,
    reset_password,
    verify_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    await register_user(body.email, body.password, db)
    return {"message": "Registered! Check your email to verify your account."}


@router.post("/verify-email")
async def verify(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    await verify_email(body.token, db)
    return {"message": "Email verified. You can now log in."}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login_user(body.email, body.password, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await refresh_tokens(body.refresh_token, db)


@router.post("/forgot-password")
async def forgot(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    await forgot_password(body.email, db)
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await reset_password(body.token, body.new_password, db)
    return {"message": "Password updated successfully."}


@router.get("/me", response_model=UserOut)
async def me(user=Depends(get_verified_user)):
    return user