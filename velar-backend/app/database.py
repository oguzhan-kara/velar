from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event
from typing import AsyncGenerator

from app.config import settings

# Engine is created at module import time but does NOT connect until first use
engine = create_async_engine(settings.database_url, echo=settings.debug)


@event.listens_for(engine.sync_engine, "connect")
def _register_pgvector_codec(dbapi_connection, connection_record):
    """Register pgvector vector type codec for every new asyncpg connection.

    asyncpg is strict about custom PostgreSQL types: the vector type codec
    must be registered per-connection before any column of type vector(1536)
    can be read or written. Without this, queries on memory_facts.embedding
    raise a codec error.

    dbapi_connection.run_sync() is asyncpg's AdaptedConnection bridge that
    allows async codec registration (register_vector is async) to be called
    from this synchronous SQLAlchemy event.
    """
    from pgvector.asyncpg import register_vector
    dbapi_connection.run_sync(register_vector)


async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a database session per request."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
