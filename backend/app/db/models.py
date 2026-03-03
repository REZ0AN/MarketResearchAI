import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, Numeric, SmallInteger, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


# ─── ENUMS ────────────────────────────────────────────────────────────────────
class LimitTypeEnum(str, enum.Enum):
    tokens_per_day    = "tokens_per_day"
    tokens_per_minute = "tokens_per_minute"
    context_window    = "context_window"
    requests_per_day  = "requests_per_day"

class WindowTypeEnum(str, enum.Enum):
    daily       = "daily"
    hourly      = "hourly"
    per_request = "per_request"
    rolling_60s = "rolling_60s"

class SubStatusEnum(str, enum.Enum):
    active    = "active"
    cancelled = "cancelled"
    expired   = "expired"
    trialing  = "trialing"


# ─── PLAN ─────────────────────────────────────────────────────────────────────
class Plan(Base):
    __tablename__ = "plans"

    id    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name  = Column(String(50),  nullable=False, unique=True)
    price = Column(Numeric(8,2), nullable=False, default=0)
    tier  = Column(SmallInteger, nullable=False, default=0)

    limits        = relationship("PlanLimit",     back_populates="plan", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription",  back_populates="plan")


class PlanLimit(Base):
    __tablename__ = "plan_limits"
    __table_args__ = (UniqueConstraint("plan_id", "limit_type"),)

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id     = Column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    limit_type  = Column(Enum(LimitTypeEnum,  name="limit_type_enum"),  nullable=False)
    limit_value = Column(Integer, nullable=False)
    window_type = Column(Enum(WindowTypeEnum, name="window_type_enum"), nullable=False)

    plan = relationship("Plan", back_populates="limits")


# ─── USER ─────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email              = Column(String(255), nullable=False, unique=True)
    hashed_password    = Column(Text, nullable=False)
    is_verified        = Column(Boolean, nullable=False, default=False)
    verification_token = Column(Text)
    reset_token        = Column(Text)
    reset_token_exp    = Column(DateTime(timezone=True))
    created_at         = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    subscription  = relationship("Subscription",    back_populates="user", uselist=False)
    chats         = relationship("Chat",            back_populates="user", cascade="all, delete-orphan")
    token_usages  = relationship("TokenUsage",      back_populates="user", cascade="all, delete-orphan")
    quota_buckets = relationship("UserQuotaBucket", back_populates="user", cascade="all, delete-orphan")


# ─── SUBSCRIPTION ─────────────────────────────────────────────────────────────
class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id"),)

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id    = Column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    status     = Column(Enum(SubStatusEnum, name="sub_status_enum"), nullable=False, default=SubStatusEnum.active)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="subscription")
    plan = relationship("Plan", back_populates="subscriptions")


# ─── CHAT ─────────────────────────────────────────────────────────────────────
class Chat(Base):
    __tablename__ = "chats"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id           = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title             = Column(String(200))
    model             = Column(String(100), nullable=False, default="llama-3.3-70b-versatile")
    created_at        = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    total_tokens_used = Column(Integer, nullable=False, default=0)

    user     = relationship("User",         back_populates="chats")
    messages = relationship("Message",      back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at")
    usages   = relationship("TokenUsage",   back_populates="chat", cascade="all, delete-orphan")


# ─── MESSAGE ──────────────────────────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id    = Column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    role       = Column(String(20), nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chat = relationship("Chat", back_populates="messages")


# ─── TOKEN USAGE ──────────────────────────────────────────────────────────────
class TokenUsage(Base):
    __tablename__ = "token_usage"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id       = Column(UUID(as_uuid=True), ForeignKey("chats.id",  ondelete="CASCADE"), nullable=False)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id",  ondelete="CASCADE"), nullable=False)
    input_tokens  = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens  = Column(Integer, nullable=False, default=0)
    model         = Column(String(100), nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chat = relationship("Chat", back_populates="usages")
    user = relationship("User", back_populates="token_usages")


# ─── QUOTA BUCKET ─────────────────────────────────────────────────────────────
class UserQuotaBucket(Base):
    __tablename__ = "user_quota_buckets"
    __table_args__ = (UniqueConstraint("user_id", "window_type", "window_start"),)

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    window_type   = Column(Enum(WindowTypeEnum, name="window_type_enum"), nullable=False)
    window_start  = Column(DateTime(timezone=True), nullable=False)
    tokens_used   = Column(Integer, nullable=False, default=0)
    requests_used = Column(Integer, nullable=False, default=0)
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="quota_buckets")