"""Memory service layer: store, deduplicate, supersede, and retrieve facts.

All public functions accept an AsyncSession and operate on memory_facts.
Background task functions create their own sessions via async_session_factory()
— they NEVER use a request-scoped session (would be closed before task runs).
"""

import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.models import MemoryFact
from app.memory.embeddings import get_embedding
from app.database import async_session_factory

logger = logging.getLogger(__name__)

# Similarity threshold for contradiction detection.
# If cosine similarity (1 - cosine_distance) > 0.92, treat new fact as an
# update to the existing fact (supersede), not a new independent fact.
# This prevents "I'm allergic to nuts" and "nut allergy" from being stored
# as two separate facts. Start at 0.92; tune empirically.
SUPERSEDE_SIMILARITY_THRESHOLD = 0.92


async def store_fact(
    session: AsyncSession,
    user_id: str,
    category: str,
    key: str,
    value: str,
    source: str = "conversation",
    confidence: float = 1.0,
) -> MemoryFact:
    """Store a single fact with embedding. Checks for contradictions first.

    If an existing active fact in the same category has cosine similarity > 0.92
    with the new fact's embedding, the existing fact is superseded (not a new row).

    Args:
        session:    SQLAlchemy async session.
        user_id:    UUID string of the fact owner.
        category:   Fact category (health, food, social, place, habit, work, preference).
        key:        Attribute name in snake_case.
        value:      Fact value.
        source:     'conversation' (Claude-extracted) or 'explicit' (user-stated via API).
        confidence: 0.7-0.85 for extracted, 1.0 for explicit.

    Returns:
        The stored MemoryFact (new or the new superseding fact).
    """
    # Embed the fact text for similarity search and future retrieval
    fact_text = f"{key}: {value}"
    try:
        embedding = await get_embedding(fact_text)
    except RuntimeError as exc:
        logger.warning("Embedding failed for fact (%s=%s): %s — storing without embedding", key, value, exc)
        embedding = None

    # Contradiction check: find top-5 active facts in same category by cosine similarity
    existing_fact = None
    if embedding is not None:
        try:
            stmt = (
                select(MemoryFact)
                .where(
                    and_(
                        MemoryFact.user_id == user_id,
                        MemoryFact.category == category,
                        MemoryFact.valid_until.is_(None),
                        MemoryFact.superseded_by.is_(None),
                        MemoryFact.embedding.is_not(None),
                    )
                )
                .order_by(MemoryFact.embedding.cosine_distance(embedding))
                .limit(5)
            )
            result = await session.scalars(stmt)
            top_candidates = list(result.all())

            for candidate in top_candidates:
                # cosine_distance returns 0 (identical) to 2 (opposite)
                # cosine_similarity = 1 - cosine_distance
                # We can't get the distance value directly from ORM result — compute inline
                # by querying a scalar cosine_distance value for this specific pair
                dist_stmt = select(
                    MemoryFact.embedding.cosine_distance(embedding)
                ).where(MemoryFact.id == candidate.id)
                dist_result = await session.scalar(dist_stmt)
                if dist_result is not None:
                    similarity = 1.0 - float(dist_result)
                    if similarity >= SUPERSEDE_SIMILARITY_THRESHOLD:
                        existing_fact = candidate
                        logger.info(
                            "Contradiction detected (similarity=%.3f): superseding fact %s",
                            similarity, candidate.id
                        )
                        break
        except Exception as exc:
            logger.warning("Contradiction check failed: %s — storing as new fact", exc)

    if existing_fact is not None:
        # Supersede the existing fact
        return await _supersede_fact(
            session=session,
            old_fact=existing_fact,
            new_key=key,
            new_value=value,
            new_embedding=embedding,
            source=source,
            confidence=confidence,
            user_id=user_id,
            category=category,
        )

    # No contradiction — store as new fact
    new_fact = MemoryFact(
        user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
        category=category,
        key=key,
        value=value,
        source=source,
        confidence=confidence,
        embedding=embedding,
    )
    session.add(new_fact)
    await session.commit()
    await session.refresh(new_fact)
    logger.info("Stored new fact: [%s] %s=%s (source=%s)", category, key, value, source)
    return new_fact


async def _supersede_fact(
    session: AsyncSession,
    old_fact: MemoryFact,
    new_key: str,
    new_value: str,
    new_embedding: list[float] | None,
    source: str,
    confidence: float,
    user_id: str,
    category: str,
) -> MemoryFact:
    """Create a new fact and mark the old one as superseded.

    The supersede pattern (from Phase 1 schema design):
    1. Create new fact (gets a new UUID)
    2. Set old_fact.valid_until = now()
    3. Set old_fact.superseded_by = new_fact.id

    Both changes are committed atomically.
    """
    now = datetime.now(timezone.utc)

    # 1. Create new fact (flush to get its ID before updating old fact)
    new_fact = MemoryFact(
        user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
        category=category,
        key=new_key,
        value=new_value,
        source=source,
        confidence=confidence,
        embedding=new_embedding,
    )
    session.add(new_fact)
    await session.flush()  # assigns new_fact.id without committing

    # 2. Invalidate old fact
    old_fact.valid_until = now
    old_fact.superseded_by = new_fact.id

    await session.commit()
    await session.refresh(new_fact)
    return new_fact


async def store_extracted_facts(
    user_message: str,
    assistant_response: str,
    user_id: str,
) -> None:
    """Background task entry point: extract facts from a conversation turn, then store.

    This function is called via FastAPI BackgroundTasks.add_task() — it runs AFTER
    the HTTP response is sent, in its own task, and MUST create its own DB session
    (not use a request-scoped session that will be closed before this runs).

    Does not raise — all exceptions are caught and logged. Extraction or storage
    failures are non-fatal: the user's voice response is already delivered.
    """
    from app.memory.extraction import extract_facts_from_conversation

    try:
        facts = await extract_facts_from_conversation(user_message, assistant_response)
    except Exception as exc:
        logger.warning("Fact extraction failed — no facts stored: %s", exc)
        return

    if not facts:
        logger.debug("Extraction returned 0 facts for conversation turn")
        return

    # Create own session — request-scoped session is already closed
    try:
        async with async_session_factory() as session:
            for fact_data in facts:
                try:
                    await store_fact(
                        session=session,
                        user_id=user_id,
                        category=fact_data.get("category", "preference"),
                        key=fact_data.get("key", "unknown"),
                        value=fact_data.get("value", ""),
                        source="conversation",
                        confidence=float(fact_data.get("confidence", 0.7)),
                    )
                except Exception as exc:
                    logger.warning("Failed to store extracted fact %s: %s", fact_data, exc)
                    # Continue with remaining facts
    except Exception as exc:
        logger.error("Background fact storage session failed: %s", exc)


async def soft_delete_fact(
    session: AsyncSession,
    fact_id: str,
    user_id: str,
) -> bool:
    """Soft-delete a fact by setting valid_until = now().

    Does NOT set superseded_by — this is an explicit user deletion, not a supersede.
    The hallucination guard distinguishes deleted (valid_until set, no superseded_by)
    from superseded (both set) facts.

    Returns:
        True if the fact was found and deactivated.
        False if the fact was not found or belongs to a different user.
    """
    stmt = select(MemoryFact).where(
        and_(
            MemoryFact.id == (uuid.UUID(fact_id) if isinstance(fact_id, str) else fact_id),
            MemoryFact.user_id == (uuid.UUID(user_id) if isinstance(user_id, str) else user_id),
            MemoryFact.valid_until.is_(None),  # only active facts can be deleted
        )
    )
    result = await session.scalar(stmt)
    if result is None:
        return False

    result.valid_until = datetime.now(timezone.utc)
    await session.commit()
    logger.info("Soft-deleted fact %s for user %s", fact_id, user_id)
    return True


async def update_fact(
    session: AsyncSession,
    fact_id: str,
    user_id: str,
    new_value: str,
    confidence: float = 1.0,
) -> MemoryFact | None:
    """Update a fact by creating a superseding version (PATCH semantics).

    The old fact is preserved in history (valid_until set, superseded_by set).
    The new fact gets a new UUID and is returned.

    Returns:
        The new superseding MemoryFact, or None if the original fact was not found.
    """
    stmt = select(MemoryFact).where(
        and_(
            MemoryFact.id == (uuid.UUID(fact_id) if isinstance(fact_id, str) else fact_id),
            MemoryFact.user_id == (uuid.UUID(user_id) if isinstance(user_id, str) else user_id),
            MemoryFact.valid_until.is_(None),
        )
    )
    old_fact = await session.scalar(stmt)
    if old_fact is None:
        return None

    # Embed the updated value so PATCH-corrected facts remain visible to semantic search.
    # If embedding fails, pass None — the fact is stored but excluded from semantic search
    # until re-embedded. This is better than leaving it permanently invisible (MEM-02).
    fact_text = f"{old_fact.key}: {new_value}"
    try:
        new_embedding = await get_embedding(fact_text)
    except RuntimeError:
        new_embedding = None

    return await _supersede_fact(
        session=session,
        old_fact=old_fact,
        new_key=old_fact.key,
        new_value=new_value,
        new_embedding=new_embedding,
        source="explicit",
        confidence=confidence,
        user_id=user_id,
        category=old_fact.category,
    )
