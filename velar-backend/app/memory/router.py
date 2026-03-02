"""VELAR Memory API — personal fact CRUD and semantic search.

Endpoints:
    GET    /api/v1/memory                    — list active facts (paginated, filterable)
    POST   /api/v1/memory                    — manually add a fact
    PATCH  /api/v1/memory/{fact_id}          — update fact (creates superseding version)
    DELETE /api/v1/memory/{fact_id}          — soft-delete fact
    GET    /api/v1/memory/search?q=...       — semantic search or summary

All endpoints require JWT auth (Depends(get_current_user)).
RLS at the database layer ensures users can only access their own facts.
"""

import asyncio
import logging
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_current_user
from app.database import get_db
from app.memory.models import MemoryFact
from app.memory.schemas import (
    FactCreate, FactUpdate, FactResponse, FactListResponse, MemorySummaryResponse
)
from app.memory.service import store_fact, soft_delete_fact, update_fact
from app.memory.retrieval import get_all_active_facts, get_relevant_facts, facts_to_context_string

logger = logging.getLogger(__name__)

router = APIRouter(tags=["memory"])

# Claude model for summary synthesis — Haiku for speed (summary is not voice-optimized)
SUMMARY_MODEL = "claude-haiku-4-5-20251001"

# System prompt for the "What do you know about me?" summary
SUMMARY_SYSTEM_PROMPT = """\
You are summarizing what you know about a user based on stored memory facts.
Synthesize the facts into a clear, readable summary grouped by category.
Use natural language — not a raw list. Be accurate: only state what is in the facts.
Do not invent or extrapolate. If a category has no facts, do not mention it.
Keep the summary concise (under 300 words).
"""


@router.get("/memory", response_model=FactListResponse)
async def list_facts(
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FactListResponse:
    """List active memory facts for the authenticated user.

    Returns paginated list of facts, optionally filtered by category.
    Only active facts (valid_until IS NULL AND superseded_by IS NULL) are returned.
    """
    conditions = [
        MemoryFact.user_id == current_user["user_id"],
        MemoryFact.valid_until.is_(None),
        MemoryFact.superseded_by.is_(None),
    ]
    if category:
        conditions.append(MemoryFact.category == category)

    # Count total
    count_stmt = select(func.count()).select_from(MemoryFact).where(and_(*conditions))
    total = await session.scalar(count_stmt) or 0

    # Paginated query
    stmt = (
        select(MemoryFact)
        .where(and_(*conditions))
        .order_by(MemoryFact.category, MemoryFact.created_at)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.scalars(stmt)
    facts = list(result.all())

    return FactListResponse(
        facts=[FactResponse.model_validate(f) for f in facts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/memory", response_model=FactResponse, status_code=201)
async def create_fact(
    body: FactCreate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FactResponse:
    """Manually add a memory fact.

    Creates a new fact with source='explicit' and confidence=1.0 (user-stated).
    Performs contradiction detection — if an existing fact in the same category
    has cosine similarity > 0.92, the existing fact is superseded instead.
    """
    fact = await store_fact(
        session=session,
        user_id=current_user["user_id"],
        category=body.category,
        key=body.key,
        value=body.value,
        source="explicit",
        confidence=body.confidence,
    )
    return FactResponse.model_validate(fact)


@router.patch("/memory/{fact_id}", response_model=FactResponse)
async def update_fact_endpoint(
    fact_id: str,
    body: FactUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FactResponse:
    """Update a fact by creating a superseding version.

    The original fact is preserved in history (valid_until set, superseded_by set).
    Returns the new superseding fact.

    Raises 404 if the fact does not exist or belongs to another user.
    """
    new_fact = await update_fact(
        session=session,
        fact_id=fact_id,
        user_id=current_user["user_id"],
        new_value=body.value,
        confidence=body.confidence,
    )
    if new_fact is None:
        raise HTTPException(status_code=404, detail="Fact not found")
    return FactResponse.model_validate(new_fact)


@router.delete("/memory/{fact_id}", status_code=204)
async def delete_fact(
    fact_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a fact (sets valid_until = now()).

    The fact is deactivated and no longer returned by list or search endpoints.
    History is preserved — the fact remains in the DB with valid_until set.

    Raises 404 if the fact does not exist or belongs to another user.
    """
    deleted = await soft_delete_fact(
        session=session,
        fact_id=fact_id,
        user_id=current_user["user_id"],
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Fact not found")


@router.get("/memory/search", response_model=MemorySummaryResponse)
async def search_memory(
    q: str = Query(..., min_length=1, description="Search query or 'what do you know about me?'"),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MemorySummaryResponse:
    """Semantic search or full memory summary.

    If q is a summary-intent query ("what do you know", "ne biliyorsun", etc.),
    retrieves ALL active facts and synthesizes a Claude summary.

    Otherwise, performs semantic search (top-10 most relevant facts) and
    returns Claude's synthesis of the matching facts.

    Raises 503 if Anthropic API key is not configured.
    """
    from app.config import settings

    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="Anthropic API key not configured")

    # Determine if this is a summary-intent query
    summary_triggers = {
        "what do you know", "what do you remember", "ne biliyorsun",
        "ne hatırlıyorsun", "hakkımda ne", "about me"
    }
    q_lower = q.lower()
    is_summary = any(trigger in q_lower for trigger in summary_triggers)

    if is_summary:
        facts = await get_all_active_facts(session, current_user["user_id"])
    else:
        facts = await get_relevant_facts(session, current_user["user_id"], q, k=10)

    fact_count = len(facts)

    if not facts:
        return MemorySummaryResponse(
            summary="I don't have any stored facts about you yet.",
            fact_count=0,
        )

    # Format facts for Claude
    facts_text = facts_to_context_string(facts, max_tokens=1800)

    # Synthesize with Claude
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = f"Here are the stored facts about the user:\n\n{facts_text}\n\nProvide a natural language summary."

    try:
        response = await asyncio.to_thread(
            client.messages.create,
            model=SUMMARY_MODEL,
            max_tokens=512,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        summary_text = response.content[0].text
    except Exception as exc:
        logger.error("Summary synthesis failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to synthesize memory summary") from exc

    return MemorySummaryResponse(summary=summary_text, fact_count=fact_count)
