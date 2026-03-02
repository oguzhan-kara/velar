"""Embedding service for VELAR memory system.

Provider selection via EMBEDDING_PROVIDER env var:
- "local"  (default): Use sentence-transformers with paraphrase-multilingual-MiniLM-L12-v2
                       (384 dims, Turkish-native, no API key required).
- "openai": Use OpenAI text-embedding-3-small at 1536 dimensions (paid).

When EMBEDDING_PROVIDER=local the model is loaded once at first call and cached.
When EMBEDDING_PROVIDER=openai the existing AsyncOpenAI path is used unchanged.

If the embedding call fails, raises RuntimeError. Callers (extraction pipeline,
retrieval) catch this and fall back gracefully:
- Extraction: stores fact with embedding=NULL (searchable by filter, not semantics)
- Retrieval: skips embedding step, returns empty list
"""

import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider and dimension constants
# ---------------------------------------------------------------------------

# Determine provider at import time via os.environ so models.py can also
# read the same variable without importing settings (which requires DB env vars).
_EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "local").lower()

# OpenAI path constants (unchanged from Phase 3)
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDING_DIMENSIONS = 1536  # must match extensions.vector(1536) in Phase 1 schema

# Local sentence-transformers constants
LOCAL_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"  # 384 dims, Turkish-native
LOCAL_EMBEDDING_DIMENSIONS = 384

# Resolve active dimensions based on provider
EMBEDDING_DIMENSIONS = (
    OPENAI_EMBEDDING_DIMENSIONS if _EMBEDDING_PROVIDER == "openai"
    else LOCAL_EMBEDDING_DIMENSIONS
)

# ---------------------------------------------------------------------------
# OpenAI client (unchanged, lazy singleton)
# ---------------------------------------------------------------------------

_openai_client = None


def _get_openai_client():
    """Return (or create) the AsyncOpenAI client using current settings."""
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        from app.config import settings
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


# ---------------------------------------------------------------------------
# Local sentence-transformers client (lazy singleton)
# ---------------------------------------------------------------------------

_local_model = None
_local_model_lock = None


def _get_local_model():
    """Return (or create) the sentence-transformers SentenceTransformer model.

    Loads the model on first call and caches it in _local_model.
    Thread-safe via a threading.Lock.
    """
    global _local_model, _local_model_lock
    import threading
    if _local_model_lock is None:
        _local_model_lock = threading.Lock()
    if _local_model is None:
        with _local_model_lock:
            if _local_model is None:
                from app.config import settings
                model_name = getattr(settings, "embedding_model", LOCAL_EMBEDDING_MODEL)
                logger.info(
                    "Loading local sentence-transformers model %r (first call — may take a moment).",
                    model_name,
                )
                try:
                    from sentence_transformers import SentenceTransformer
                    _local_model = SentenceTransformer(model_name)
                    logger.info("Local embedding model %r loaded.", model_name)
                except Exception as exc:
                    logger.error("Failed to load local embedding model %r: %s", model_name, exc)
                    raise RuntimeError(f"Failed to load local embedding model: {exc}") from exc
    return _local_model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_embedding(text: str) -> list[float]:
    """Get an embedding vector for text using the configured provider.

    EMBEDDING_PROVIDER=local  (default): Uses sentence-transformers locally,
                                          returns 384-dim vector, no API key needed.
    EMBEDDING_PROVIDER=openai:            Uses OpenAI text-embedding-3-small,
                                          returns 1536-dim vector, requires OPENAI_API_KEY.

    Args:
        text: The text to embed. Should be the fact_text or query string.

    Returns:
        List of floats representing the embedding vector.
        Length is 384 (local) or 1536 (openai).

    Raises:
        RuntimeError: If the embedding call fails. Caller decides retry/skip strategy.
    """
    if not text or not text.strip():
        raise RuntimeError("Cannot embed empty text")

    provider = _EMBEDDING_PROVIDER

    if provider == "openai":
        return await _get_openai_embedding(text)
    else:
        # Default: local sentence-transformers
        return await _get_local_embedding(text)


async def _get_local_embedding(text: str) -> list[float]:
    """Get embedding using local sentence-transformers (384 dims, Turkish-native).

    Uses asyncio.to_thread because the sentence-transformers encode() call is
    synchronous and CPU-bound — avoids blocking the event loop.
    """
    import asyncio

    try:
        model = _get_local_model()

        def _encode() -> list[float]:
            embedding = model.encode(text.strip(), normalize_embeddings=True)
            return embedding.tolist()

        embedding = await asyncio.to_thread(_encode)

        assert len(embedding) == LOCAL_EMBEDDING_DIMENSIONS, (
            f"Embedding dimension mismatch: expected {LOCAL_EMBEDDING_DIMENSIONS}, "
            f"got {len(embedding)}"
        )
        return embedding
    except AssertionError:
        raise
    except Exception as exc:
        logger.error("Local embedding failed for text %r: %s", text[:50], exc)
        raise RuntimeError(f"Embedding failed: {exc}") from exc


async def _get_openai_embedding(text: str) -> list[float]:
    """Get 1536-dimensional embedding for text using OpenAI text-embedding-3-small.

    Unchanged from Phase 3 — full OpenAI path preserved for paid users.

    Args:
        text: The text to embed.

    Returns:
        List of 1536 floats representing the embedding vector.

    Raises:
        RuntimeError: If the OpenAI API call fails.
    """
    client = _get_openai_client()
    try:
        response = await client.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=text.strip(),
            dimensions=OPENAI_EMBEDDING_DIMENSIONS,  # explicit — must match schema column
        )
        embedding = response.data[0].embedding
        # Sanity check: schema rejects wrong dimension at INSERT time, but catch here
        assert len(embedding) == OPENAI_EMBEDDING_DIMENSIONS, (
            f"Embedding dimension mismatch: expected {OPENAI_EMBEDDING_DIMENSIONS}, "
            f"got {len(embedding)}"
        )
        return embedding
    except AssertionError:
        raise
    except Exception as exc:
        logger.error("OpenAI embedding failed for text %r: %s", text[:50], exc)
        raise RuntimeError(f"Embedding failed: {exc}") from exc
