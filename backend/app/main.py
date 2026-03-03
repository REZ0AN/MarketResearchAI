from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, chat, usage

app = FastAPI(title="Gemini MVP API", version="1.0.0")

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── ROUTERS ──────────────────────────────────────────────────────────────────
app.include_router(auth.router,  prefix="/api/v1")
app.include_router(chat.router,  prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}