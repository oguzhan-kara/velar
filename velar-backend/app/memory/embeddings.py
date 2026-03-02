"""OpenAI embedding service for VELAR memory system.

Uses text-embedding-3-small at 1536 dimensions (matches Phase 1 schema column).
Lazy singleton client — created on first call, not at import time.

If the OpenAI API call fails, raises RuntimeError. Callers (extraction pipeline,
retrieval) catch this and fall back gracefully:
- Extraction: stores fact with embedding=NULL (searchable by filter, not semantics)
- Retrieval: skips embedding step, returns empty list
"""

import logging
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)

_openai_client: AsyncOpenAI | None = None

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536  # must match extensions.vector(1536) in Phase 1 schema


def _get_openai_client() -> AsyncOpenAI:
    """Return (or create) the AsyncOpenAI client using current settings."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


async def get_embedding(text: str) -> list[float]:
    """Get 1536-dimensional embedding for text using text-embedding-3-small.

    Args:
        text: The text to embed. Should be the fact_text or query string.

    Returns:
        List of 1536 floats representing the embedding vector.

    Raises:
        RuntimeError: If the OpenAI API call fails. Caller decides retry/skip strategy.
    """
    if not text or not text.strip():
        raise RuntimeError("Cannot embed empty text")

    client = _get_openai_client()
    try:
        response = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text.strip(),
            dimensions=EMBEDDING_DIMENSIONS,  # explicit — must match schema column
        )
        embedding = response.data[0].embedding
        # Sanity check: schema rejects wrong dimension at INSERT time, but catch here
        assert len(embedding) == EMBEDDING_DIMENSIONS, (
            f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, "
            f"got {len(embedding)}"
        )
        return embedding
    except AssertionError:
        raise
    except Exception as exc:
        logger.error("OpenAI embedding failed for text %r: %s", text[:50], exc)
        raise RuntimeError(f"Embedding failed: {exc}") from exc
