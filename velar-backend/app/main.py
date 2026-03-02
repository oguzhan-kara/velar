import asyncpg
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.health.router import router as health_router
from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.voice.router import router as voice_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: verify DB connectivity on startup, clean up on shutdown."""
    # Startup: verify database connectivity
    try:
        conn = await asyncpg.connect(
            dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
        await conn.execute("SELECT 1")
        await conn.close()
        logger.info("Database connectivity verified.")
    except Exception as exc:
        logger.error(f"Database connectivity check failed: {exc}")
        # Allow startup to continue — DB may be temporarily unavailable

    # Log configured STT model (does NOT load the Whisper model — stays lazy until first request)
    try:
        logger.info(f"STT service configured: model={settings.whisper_model_size} (loads on first request)")
    except Exception as e:
        logger.warning(f"STT service not available: {e} — voice endpoints will fail")

    yield
    # Shutdown: nothing to clean up for now


app = FastAPI(
    title="VELAR API",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health_router)  # responds at /health
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(users_router, prefix="/api/v1/users")
app.include_router(voice_router, prefix="/api/v1")
