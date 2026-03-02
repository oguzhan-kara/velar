"""Semantic retrieval for VELAR memory system.

Provides:
- get_relevant_facts(): embed a query, find top-k semantically similar active facts
- facts_to_context_string(): format facts into a token-capped Claude context block

The 2000-token cap from CONTEXT.md is implemented at 1800 tokens (10% safety margin)
because tiktoken cl100k_base (OpenAI tokenizer) is only an approximation of Claude's
tokenizer. Turkish text can cause larger divergence than English — the margin prevents
memory context from overflowing the Claude system prompt.
"""

import logging
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
import tiktoken

from app.memory.models import MemoryFact
from app.memory.embeddings import get_embedding

logger = logging.getLogger(__name__)

# 10% below the 2000-token cap from CONTEXT.md — absorbs tiktoken/Claude tokenizer gap
# Turkish text (non-ASCII, longer avg token length in CL100K) makes estimation less accurate
TOKEN_CAP = 1800
_tokenizer = None


def _get_tokenizer():
    """Lazy-load tiktoken tokenizer (one-time cost)."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = tiktoken.get_encoding("cl100k_base")
    return _tokenizer


async def get_relevant_facts(
    session: AsyncSession,
    user_id: str,
    query_text: str,
    k: int = 10,
) -> list[MemoryFact]:
    """Retrieve top-k semantically similar active facts for a user.

    Embeds the query text and performs a cosine distance search against
    active memory_facts (valid_until IS NULL AND superseded_by IS NULL).
    Facts with NULL embedding are excluded by the ORDER BY clause (NULL
    embeddings sort last in pgvector distance queries).

    Args:
        session:    SQLAlchemy async session (request-scoped from Depends(get_db)
                    or task-scoped from async_session_factory()).
        user_id:    UUID string of the authenticated user.
        query_text: The user's current message or query to embed.
        k:          Maximum number of facts to return (default 10 per CONTEXT.md).

    Returns:
        List of MemoryFact objects ordered by cosine similarity (closest first).
        Returns empty list if embedding fails or no active facts exist.
    """
    try:
        query_embedding = await get_embedding(query_text)
    except RuntimeError as exc:
        logger.warning("Retrieval embedding failed — returning empty context: %s", exc)
        return []

    try:
        stmt = (
            select(MemoryFact)
            .where(
                and_(
                    MemoryFact.user_id == user_id,
                    MemoryFact.valid_until.is_(None),
                    MemoryFact.superseded_by.is_(None),
                    MemoryFact.embedding.is_not(None),  # skip facts with no embedding
                )
            )
            .order_by(MemoryFact.embedding.cosine_distance(query_embedding))
            .limit(k)
        )
        result = await session.scalars(stmt)
        return list(result.all())
    except Exception as exc:
        logger.error("Semantic retrieval query failed: %s", exc)
        return []


def facts_to_context_string(facts: list[MemoryFact], max_tokens: int = TOKEN_CAP) -> str:
    """Format active facts into a token-capped context string for Claude's system prompt.

    Facts are ordered by relevance (closest cosine distance first, as returned by
    get_relevant_facts). We truncate at max_tokens to stay within the 2000-token cap
    specified in CONTEXT.md.

    Each line format: "- [category] key: value (id:<uuid>)"
    The (id:<uuid>) suffix is required by the hallucination guard in Plan 03-02:
    Claude must cite memory_fact_id when referencing a stored fact.

    Args:
        facts:      List of MemoryFact objects (ordered by relevance).
        max_tokens: Token cap (default 1800 — see module docstring for why not 2000).

    Returns:
        Newline-joined string of formatted facts, or empty string if facts is empty.
    """
    if not facts:
        return ""

    enc = _get_tokenizer()
    lines = []
    total_tokens = 0

    for fact in facts:
        line = f"- [{fact.category}] {fact.key}: {fact.value} (id:{fact.id})"
        tokens = len(enc.encode(line))
        if total_tokens + tokens > max_tokens:
            break
        lines.append(line)
        total_tokens += tokens

    return "\n".join(lines)


async def get_all_active_facts(
    session: AsyncSession,
    user_id: str,
) -> list[MemoryFact]:
    """Return all active facts for a user, ordered by category then created_at.

    Used by the 'What do you know about me?' summary endpoint — returns all facts
    (not just semantic top-k) so Claude can synthesize a complete picture.
    Does NOT apply token cap — the caller (summary endpoint) passes all facts
    to Claude with the summary prompt.

    Args:
        session: SQLAlchemy async session.
        user_id: UUID string of the authenticated user.

    Returns:
        List of all active MemoryFact objects for the user.
    """
    try:
        stmt = (
            select(MemoryFact)
            .where(
                and_(
                    MemoryFact.user_id == user_id,
                    MemoryFact.valid_until.is_(None),
                    MemoryFact.superseded_by.is_(None),
                )
            )
            .order_by(MemoryFact.category, MemoryFact.created_at)
        )
        result = await session.scalars(stmt)
        return list(result.all())
    except Exception as exc:
        logger.error("get_all_active_facts query failed: %s", exc)
        return []
