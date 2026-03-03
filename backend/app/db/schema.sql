-- ─── EXTENSIONS ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- ─── ENUM TYPES ───────────────────────────────────────────────────────────────
CREATE TYPE limit_type_enum  AS ENUM (
    'tokens_per_day', 'tokens_per_minute',
    'context_window', 'requests_per_day'
);
CREATE TYPE window_type_enum AS ENUM (
    'daily', 'hourly', 'per_request', 'rolling_60s'
);
CREATE TYPE sub_status_enum  AS ENUM (
    'active', 'cancelled', 'expired', 'trialing'
);

-- ─── PLANS ────────────────────────────────────────────────────────────────────
CREATE TABLE plans (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(50)  NOT NULL UNIQUE,   -- "free", "pro", "enterprise"
    price      NUMERIC(8,2) NOT NULL DEFAULT 0,
    tier       SMALLINT     NOT NULL DEFAULT 0  -- 0=free 1=pro 2=enterprise
);

CREATE TABLE plan_limits (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id      UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    limit_type   limit_type_enum  NOT NULL,
    limit_value  INT  NOT NULL,
    window_type  window_type_enum NOT NULL,
    UNIQUE (plan_id, limit_type)
);

-- ─── USERS ────────────────────────────────────────────────────────────────────
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(255) NOT NULL UNIQUE,
    hashed_password     TEXT         NOT NULL,
    is_verified         BOOLEAN      NOT NULL DEFAULT FALSE,
    verification_token  TEXT,
    reset_token         TEXT,
    reset_token_exp     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─── SUBSCRIPTIONS ────────────────────────────────────────────────────────────
CREATE TABLE subscriptions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    plan_id    UUID NOT NULL REFERENCES plans(id)  ON DELETE RESTRICT,
    status     sub_status_enum NOT NULL DEFAULT 'active',
    started_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE (user_id)   -- one active subscription per user
);

-- ─── CHATS ────────────────────────────────────────────────────────────────────
CREATE TABLE chats (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title             VARCHAR(200),
    model             VARCHAR(100) NOT NULL DEFAULT 'llama-3.3-70b-versatile',
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    total_tokens_used INT          NOT NULL DEFAULT 0
);

CREATE INDEX idx_chats_user ON chats(user_id, created_at DESC);

-- ─── MESSAGES ─────────────────────────────────────────────────────────────────
CREATE TABLE messages (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id    UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role       VARCHAR(20) NOT NULL CHECK (role IN ('user','assistant','system')),
    content    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_chat ON messages(chat_id, created_at ASC);

-- ─── TOKEN USAGE ──────────────────────────────────────────────────────────────
CREATE TABLE token_usage (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id        UUID NOT NULL REFERENCES chats(id)  ON DELETE CASCADE,
    user_id        UUID NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    input_tokens   INT  NOT NULL DEFAULT 0,
    output_tokens  INT  NOT NULL DEFAULT 0,
    total_tokens   INT  NOT NULL DEFAULT 0,
    model          VARCHAR(100) NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_token_usage_user ON token_usage(user_id, created_at DESC);

-- ─── QUOTA BUCKETS ────────────────────────────────────────────────────────────
CREATE TABLE user_quota_buckets (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID             NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    window_type    window_type_enum NOT NULL,
    window_start   TIMESTAMPTZ      NOT NULL,
    tokens_used    INT              NOT NULL DEFAULT 0,
    requests_used  INT              NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, window_type, window_start)
);

-- ─── SEED DEFAULT PLANS ───────────────────────────────────────────────────────
INSERT INTO plans (name, price, tier) VALUES
    ('free',       0.00, 0),
    ('pro',        9.99, 1),
    ('enterprise', 49.99, 2);

INSERT INTO plan_limits (plan_id, limit_type, limit_value, window_type)
SELECT p.id, l.limit_type::limit_type_enum, l.limit_value, l.window_type::window_type_enum
FROM plans p
JOIN (VALUES
    -- FREE
    ('free', 'tokens_per_day',    20000,  'daily'),
    ('free', 'tokens_per_minute', 500,    'rolling_60s'),
    ('free', 'context_window',    8192,   'per_request'),
    ('free', 'requests_per_day',  50,     'daily'),
    -- PRO
    ('pro',  'tokens_per_day',    200000, 'daily'),
    ('pro',  'tokens_per_minute', 5000,   'rolling_60s'),
    ('pro',  'context_window',    32768,  'per_request'),
    ('pro',  'requests_per_day',  1000,   'daily'),
    -- ENTERPRISE
    ('enterprise', 'tokens_per_day',    2000000, 'daily'),
    ('enterprise', 'tokens_per_minute', 20000,   'rolling_60s'),
    ('enterprise', 'context_window',    131072,  'per_request'),
    ('enterprise', 'requests_per_day',  10000,   'daily')
) AS l(plan_name, limit_type, limit_value, window_type)
ON p.name = l.plan_name;