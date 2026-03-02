"""SQLAlchemy ORM model for the memory_facts table.

The memory_facts table was created in Phase 1 migration with:
- EAV triple pattern: user_id, category, key, value
- embedding: extensions.vector(1536) for semantic similarity
- valid_until / superseded_by: supersede versioning pattern
- RLS policy: users manage only their own facts

This ORM class maps to that table. No migrations are added here.

Phase 5: The embedding column dimension is driven by EMBEDDING_PROVIDER env var:
- EMBEDDING_PROVIDER=local  (default): Vector(384) — sentence-transformers
- EMBEDDING_PROVIDER=openai:            Vector(1536) — OpenAI text-embedding-3-small

SQLAlchemy requires a fixed dimension at class definition time, so we read
EMBEDDING_PROVIDER from os.environ directly (before settings is imported) to set
the correct dimension. Run the 20260302000002_embeddings_384dim.sql migration
before switching providers if there is existing data.
"""

import os
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, ForeignKey, text, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

# TIMESTAMP with timezone — pgvector/SA standard alias for TIMESTAMPTZ
TIMESTAMPTZ = TIMESTAMP(timezone=True)

# Resolve embedding dimension from env var at module load time.
# This must happen before the MemoryFact class body is evaluated by Python,
# since SQLAlchemy reads the mapped_column() call at class definition time.
# Default: 384 (local sentence-transformers). Set EMBEDDING_PROVIDER=openai for 1536.
_EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "local").lower()
_EMBEDDING_DIMS = 1536 if _EMBEDDING_PROVIDER == "openai" else 384


class Base(DeclarativeBase):
    pass


class MemoryFact(Base):
    __tablename__ = "memory_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    # category values: health, food, social, place, habit, work, preference
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="conversation")
    # source values: conversation, explicit, derived
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # Claude-extracted: 0.7 (implied) to 0.85 (clearly stated)
    # User-stated (explicit source): 1.0
    embedding: Mapped[Optional[list]] = mapped_column(Vector(_EMBEDDING_DIMS), nullable=True)
    # embedding may be NULL if the embedding call failed at store time.
    # Facts with NULL embedding are stored but excluded from semantic search.
    # Dimension: 384 (EMBEDDING_PROVIDER=local) or 1536 (EMBEDDING_PROVIDER=openai).
    valid_from: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=text("now()"), nullable=False
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ, nullable=True)
    # valid_until IS NULL means the fact is currently active.
    # Set to now() to deactivate (soft delete or supersede step 1).
    superseded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memory_facts.id", name="fk_memory_facts_superseded_by"),
        nullable=True,
    )
    # superseded_by points to the newer fact that replaces this one.
    # Set alongside valid_until when a fact is superseded (not for simple deletes).
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=text("now()"), nullable=False
    )
