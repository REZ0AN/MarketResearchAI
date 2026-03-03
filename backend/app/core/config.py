from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str                        = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int      = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int        = 7

    # Email
    SMTP_HOST: str
    SMTP_PORT: int                        = 587
    SMTP_USER: str
    SMTP_PASS: str
    EMAILS_FROM: str                      = "noreply@gemini-mvp.dev"

    # App
    FRONTEND_URL: str                     = "http://localhost:5173"

    # AI
    GROQ_API_KEY: str


settings = Settings()