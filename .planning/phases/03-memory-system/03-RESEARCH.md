# Phase 3: Memory System - Research

**Researched:** 2026-03-02
**Domain:** Vector embeddings, pgvector/SQLAlchemy, async background extraction, Claude structured outputs, FastAPI CRUD
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Memory Granularity**
- Atomic fact storage: one fact = one row
- Entity-attribute-value triple pattern: `entity="user"`, `attribute="allergy"`, `value="nuts"` — stored as natural language `fact_text` with structured EAV fields for retrieval/filtering
- Embedding covers `fact_text` for semantic similarity (searching "dietary restrictions" surfaces nut allergy)
- `category` field for grouping: health, food, social, place, habit, work, preference (extensible)
- Confidence score tracked (0–1): Claude-extracted facts start at 0.7, user-stated facts start at 1.0
- No maximum memory count in Phase 3

**What VELAR Remembers**
- Auto-extraction from all conversations: health facts, food preferences, social relationships, places, habits, work context
- No opt-in — passive extraction from day one
- Sensitive categories stored at same priority; user controls deletion
- Extraction happens asynchronously after each turn — does NOT block voice response
- Extraction via a second Claude call: given conversation, extract zero or more new facts as JSON array
- No cross-user facts — RLS already enforces per-user scoping

**Memory Correction and Versioning**
- Natural conversation correction: "actually I moved to Ankara" triggers extraction of a correcting fact
- Supersede pattern (in schema): new fact sets `supersedes_id` pointing to old fact, old fact's `is_active = false`
- Explicit DELETE `/memory/{id}` sets `is_active = false` (no new version created)
- Hallucination guard: Claude responses referencing a fact must cite a `memory_fact_id`; if ID doesn't exist in DB, claim is flagged, not stated
- Contradiction detection: before storing, check semantic similarity to existing active facts; if > 0.92 → supersede, not new fact

**Memory Retrieval**
- Semantic retrieval: embed current user message → query pgvector top-k=10 → inject into Claude system prompt
- 2000-token cap on injected memory context
- `active_memory_facts` view for all retrieval (already in Phase 1 schema)
- "What do you know about me?" → Claude-synthesized summary by category, not raw dump

**Memory API (CRUD)**
- `GET /api/v1/memory` — list active facts (paginated, filterable by category)
- `POST /api/v1/memory` — manually add a fact
- `PATCH /api/v1/memory/{id}` — update (creates superseding version)
- `DELETE /api/v1/memory/{id}` — soft delete (deactivate)
- `GET /api/v1/memory/search?q=` — semantic search
- All endpoints: `Depends(get_current_user)`; RLS at DB layer

### Claude's Discretion
- Exact embedding model (text-embedding-3-small vs Supabase built-in vs Cohere) — research recommends OpenAI text-embedding-3-small
- Extraction prompt engineering details
- Exact similarity threshold values (start 0.92, tune empirically)
- Pagination defaults (page size, max)
- Background task queue implementation (FastAPI BackgroundTasks vs asyncio)
- Error handling for embedding API failures

### Deferred Ideas (OUT OF SCOPE)
- Memory browser UI — Phase 6
- Proactive use of memories in responses — Phase 5
- Memory-based pattern detection ("3 days in a row") — Phase 5
- Cross-device memory sync UI — Phase 6/7 (memory is already cross-device via Supabase)
- Memory sharing between users — explicitly out of scope for v1
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MEM-01 | VELAR stores personal facts permanently (health, preferences, relationships, habits) | Supabase `memory_facts` table (Phase 1) + pgvector embeddings + async extraction pipeline |
| MEM-02 | User can ask what VELAR knows and get accurate recall | Semantic retrieval (top-k=10) + Claude-synthesized summary endpoint — hallucination guard prevents fabrication |
| MEM-03 | VELAR passively extracts facts from every conversation without explicit user action | FastAPI BackgroundTasks after voice/chat response — second Claude call with structured output for fact JSON |
| MEM-04 | User can correct or delete stored facts | Supersede versioning pattern + DELETE soft-delete endpoint + natural-language correction via extraction |
| MEM-05 | Memory persists across devices and sessions via cloud sync | Already satisfied by Supabase cloud + RLS — any device with JWT can query the same facts |
</phase_requirements>

---

## Summary

Phase 3 builds on the already-existing `memory_facts` table (Phase 1 schema: EAV triples, `vector(1536)`, supersede versioning, RLS). The work is four pieces: (1) a new `app/memory/` module exposing CRUD + semantic search API, (2) a pgvector-enabled SQLAlchemy ORM model with HNSW index and asyncpg registration, (3) an OpenAI embedding service (`text-embedding-3-small`, 1536 dims, matching the existing schema), and (4) a background extraction pipeline that runs after each voice/chat turn, calling Claude with structured output to extract facts as JSON.

The Phase 1 schema already has `valid_until` and `superseded_by` columns for versioning, and the `active_memory_facts` view for filtered retrieval. Phase 3 does not add new migrations — it populates and queries what Phase 1 created. The HNSW index on `memory_facts.embedding` IS a new migration (the Phase 1 migration does not include it).

The critical correctness risks are: (a) the asyncpg/pgvector registration event listener must be added to the existing `database.py` engine or in a memory-specific async session, (b) the embedding model's dimension (1536) must match what Phase 1 schema column declares, (c) the hallucination guard must block Claude from asserting facts not grounded in the DB, and (d) background extraction must never delay the voice response.

**Primary recommendation:** Use `pgvector` Python library with the existing `asyncpg`-backed `create_async_engine`, register vector types via `pgvector.asyncpg.register_vector` in an event listener on `engine.sync_engine`, and use OpenAI `text-embedding-3-small` at 1536 dims. For extraction, use Claude Haiku with `output_config` structured JSON output (GA since late 2025).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pgvector | latest (PyPI `pgvector`) | Python-side vector type for SQLAlchemy + asyncpg | Official pgvector Python library; supports asyncpg driver used in project |
| openai | >=1.0 | `text-embedding-3-small` embeddings | Most cost-effective embedding at 1536 dims; $0.02/1M tokens; matches schema column size |
| anthropic | ==0.84.0 (pinned) | Fact extraction via Claude Haiku structured output | Already installed; `output_config` structured JSON GA on Haiku 4.5 |
| FastAPI BackgroundTasks | built-in | Async post-response extraction pipeline | No extra dependencies; sufficient for single-user + low message volume |
| SQLAlchemy | >=2.0 (installed) | ORM + async queries against `memory_facts` | Already installed; async session factory already in `database.py` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tiktoken | latest | Token counting for 2000-token cap enforcement | Count tokens before injecting memory context into Claude system prompt |
| pydantic v2 | installed | Request/response schemas for /memory API | Consistent with rest of codebase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `text-embedding-3-small` (1536 dims) | `text-embedding-ada-002` (1536 dims) | ada-002 is legacy; 3-small is newer, better quality, same price. Both fit the existing 1536-dim schema column. Use 3-small. |
| `text-embedding-3-small` (1536 dims) | `text-embedding-3-small` at 512 dims | Requires schema migration to change vector size. Schema is locked at 1536. Use 1536. |
| FastAPI BackgroundTasks | Celery/RQ | Celery requires Redis broker, far more complexity; BackgroundTasks sufficient for current scale; upgrade later if needed |
| Claude Haiku structured output | Manual JSON parsing from Claude prompt | Structured output guarantees schema compliance; no retry logic needed; GA since late 2025 |
| Supabase's built-in vector store | Custom pgvector queries | Supabase vector store is PostgREST-based (JS); Python path uses direct SQL via SQLAlchemy |

**Installation:**
```bash
pip install pgvector openai tiktoken
# Add to requirements.txt (anthropic already installed)
```

---

## Architecture Patterns

### Recommended Project Structure
```
velar-backend/app/
├── memory/
│   ├── __init__.py
│   ├── router.py          # GET/POST/PATCH/DELETE /api/v1/memory endpoints
│   ├── schemas.py         # Pydantic models: FactCreate, FactResponse, FactUpdate, SearchQuery
│   ├── models.py          # SQLAlchemy ORM: MemoryFact (mapped to memory_facts table)
│   ├── embeddings.py      # OpenAI embedding service: get_embedding(text) -> list[float]
│   ├── extraction.py      # Background extraction: extract_facts_from_conversation()
│   └── retrieval.py       # Semantic retrieval: get_relevant_facts(user_id, query_text, k=10)
velar-backend/supabase/migrations/
└── 20260302000001_memory_hnsw_index.sql   # HNSW index on memory_facts.embedding
velar-backend/tests/
├── test_memory_api.py     # CRUD endpoint tests (mocked DB)
├── test_memory_extraction.py  # Extraction pipeline tests (mocked Claude)
└── test_memory_retrieval.py   # Semantic retrieval tests (mocked embeddings)
```

### Pattern 1: pgvector with asyncpg SQLAlchemy Engine

**What:** Register pgvector vector type codec with the existing asyncpg-backed async engine so SQLAlchemy can serialize/deserialize `vector(1536)` columns.

**When to use:** Must be done once when the engine is created. Required before any ORM query on embedding columns.

```python
# Source: pgvector-python README + pgvector/pgvector-python GitHub
# app/database.py — ADD event listener after engine creation

from sqlalchemy import event
from pgvector.asyncpg import register_vector

engine = create_async_engine(settings.database_url, echo=settings.debug)

@event.listens_for(engine.sync_engine, "connect")
def _register_vector_codec(dbapi_conn, connection_record):
    """Register pgvector codec for asyncpg connections.

    asyncpg requires the vector type to be registered per-connection
    before any vector column can be read or written. This event fires
    on every new connection in the pool.
    """
    import asyncio
    asyncio.get_event_loop().run_until_complete(register_vector(dbapi_conn))
```

**Important caveat:** The asyncpg registration is async, but the SQLAlchemy event fires in a sync context. The correct pattern (per pgvector-python docs for asyncpg+SQLAlchemy) is:

```python
# Source: github.com/pgvector/pgvector-python (asyncpg section)
from sqlalchemy import event
from pgvector.asyncpg import register_vector

@event.listens_for(engine.sync_engine, "connect")
def connect(dbapi_connection, connection_record):
    dbapi_connection.run_sync(register_vector)
    # Note: asyncpg's AdaptedConnection.run_sync() bridges async codec to sync event
```

**Verification:** Test that a query on `memory_facts.embedding` does not throw codec errors. Unit test: insert a row with `embedding=[0.1]*1536`, read it back, assert it's a list of 1536 floats.

### Pattern 2: SQLAlchemy ORM Model for memory_facts

**What:** Map the existing `memory_facts` table to a SQLAlchemy ORM class so Phase 3 can query it with type safety.

```python
# Source: pgvector-python README + SQLAlchemy 2.0 docs
# app/memory/models.py

from sqlalchemy import String, Float, Boolean, ForeignKey, text
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
from pgvector.sqlalchemy import Vector
import uuid

class Base(DeclarativeBase):
    pass

class MemoryFact(Base):
    __tablename__ = "memory_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, default="conversation")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    valid_from: Mapped[...] = mapped_column(TIMESTAMPTZ, server_default=text("now()"))
    valid_until: Mapped[...] = mapped_column(TIMESTAMPTZ, nullable=True)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_facts.id"), nullable=True
    )
    created_at: Mapped[...] = mapped_column(TIMESTAMPTZ, server_default=text("now()"))
```

**Critical:** The `active_memory_facts` view (`valid_until IS NULL AND superseded_by IS NULL`) is already defined. Queries should use `WHERE valid_until IS NULL AND superseded_by IS NULL` or query the view directly via raw SQL for retrieval.

### Pattern 3: Semantic Retrieval with Cosine Distance

**What:** Given a user's query text, embed it and return the top-k most semantically similar active facts.

```python
# Source: pgvector-python README cosine_distance, SQLAlchemy 2.0
# app/memory/retrieval.py

from sqlalchemy import select, and_
from pgvector.sqlalchemy import cosine_distance
from app.memory.models import MemoryFact
from app.memory.embeddings import get_embedding

async def get_relevant_facts(
    session: AsyncSession,
    user_id: str,
    query_text: str,
    k: int = 10,
) -> list[MemoryFact]:
    """Retrieve top-k semantically similar active facts for a user."""
    query_embedding = await get_embedding(query_text)

    stmt = (
        select(MemoryFact)
        .where(
            and_(
                MemoryFact.user_id == user_id,
                MemoryFact.valid_until.is_(None),
                MemoryFact.superseded_by.is_(None),
            )
        )
        .order_by(cosine_distance(MemoryFact.embedding, query_embedding))
        .limit(k)
    )
    result = await session.scalars(stmt)
    return list(result.all())
```

**2000-token cap enforcement:**

```python
# app/memory/retrieval.py (continued)
import tiktoken

def facts_to_context_string(facts: list[MemoryFact], max_tokens: int = 2000) -> str:
    """Format facts into a context string respecting token limit.

    Facts are ordered by relevance (closest first). We truncate at max_tokens.
    """
    enc = tiktoken.get_encoding("cl100k_base")  # matches Claude's tokenizer closely
    lines = []
    total = 0
    for fact in facts:
        line = f"- [{fact.category}] {fact.key}: {fact.value} (id:{fact.id})"
        tokens = len(enc.encode(line))
        if total + tokens > max_tokens:
            break
        lines.append(line)
        total += tokens
    return "\n".join(lines)
```

### Pattern 4: OpenAI Embedding Service

**What:** Thin async wrapper around OpenAI's embedding API.

```python
# Source: OpenAI Python SDK docs — platform.openai.com/docs/api-reference/embeddings
# app/memory/embeddings.py

from openai import AsyncOpenAI
from app.config import settings

_openai_client: AsyncOpenAI | None = None

def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client

async def get_embedding(text: str) -> list[float]:
    """Get 1536-dimensional embedding for text using text-embedding-3-small.

    Raises RuntimeError on API failure (caller decides retry/skip strategy).
    """
    client = _get_openai_client()
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        dimensions=1536,  # explicit — matches Phase 1 schema column vector(1536)
    )
    return response.data[0].embedding
```

**Config addition required:** `openai_api_key: str = ""` in `app/config.py` (same pattern as `anthropic_api_key`).

### Pattern 5: Background Fact Extraction with Claude Structured Output

**What:** After a voice/chat turn completes, extract personal facts asynchronously using a second Claude call with guaranteed JSON output.

```python
# Source: platform.claude.com/docs/en/build-with-claude/structured-outputs
# app/memory/extraction.py

import json
import asyncio
import anthropic
from app.config import settings

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "number"},
                    "fact_text": {"type": "string"},
                },
                "required": ["category", "key", "value", "confidence", "fact_text"],
                "additionalProperties": False,
            }
        }
    },
    "required": ["facts"],
    "additionalProperties": False,
}

EXTRACTION_SYSTEM_PROMPT = """\
You extract personal facts about the user from conversations.
Extract ONLY facts that are clearly stated or strongly implied.
Be liberal — prefer to extract than to miss.
Each fact must have:
- category: one of [health, food, social, place, habit, work, preference]
- key: snake_case attribute name (e.g. "nut_allergy", "favorite_restaurant")
- value: the fact value as stated (e.g. "true", "Karaköy Lokantası")
- confidence: 0.7 for implied facts, 0.85 for clearly stated, 1.0 never (Claude-extracted max is 0.85)
- fact_text: natural language sentence (e.g. "User is allergic to nuts")

Return an empty facts array if no personal facts are present.
"""

async def extract_facts_from_conversation(
    user_message: str,
    assistant_response: str,
    user_id: str,
) -> list[dict]:
    """Extract personal facts from a conversation turn.

    Uses Claude Haiku with structured output (output_config) to guarantee
    JSON schema compliance. Returns list of fact dicts.

    This function is called from FastAPI BackgroundTasks — never awaited
    in the request path.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    conversation_text = f"User: {user_message}\nAssistant: {assistant_response}"

    try:
        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": conversation_text}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": EXTRACTION_SCHEMA,
                }
            },
        )
        data = json.loads(response.content[0].text)
        return data.get("facts", [])
    except Exception as e:
        logger.warning("Fact extraction failed: %s", e)
        return []  # non-fatal — extraction failure never blocks response
```

**Structured output note (CRITICAL):** `output_config` (not `output_format`) is the current API shape as of GA release. The old `output_format` parameter and `structured-outputs-2025-11-13` beta header still work for transition period but prefer `output_config`. Structured output is GA for Haiku 4.5.

### Pattern 6: FastAPI BackgroundTasks for Extraction

**What:** Queue fact extraction to run after the HTTP response is sent.

```python
# Source: FastAPI official docs — fastapi.tiangolo.com/tutorial/background-tasks/
# In app/voice/router.py — add background task after building response

from fastapi import BackgroundTasks
from app.memory.extraction import extract_facts_from_conversation
from app.memory.service import store_extracted_facts  # processes + dedup + store

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    # ... existing pipeline ...
    response_text = await run_conversation(...)
    audio_bytes = await tts_service.synthesize(...)

    # Queue extraction AFTER building response (not awaited — non-blocking)
    background_tasks.add_task(
        store_extracted_facts,
        user_message=request.message,
        assistant_response=response_text,
        user_id=current_user["user_id"],
    )

    return ChatResponse(text=response_text, audio_base64=..., detected_language=...)
```

**Key point:** `BackgroundTasks.add_task()` schedules the function to run after the response is sent. It runs in the same event loop. For async functions, FastAPI handles them natively. For CPU-bound work, use `asyncio.to_thread` inside the background function (already the pattern for Claude calls).

### Pattern 7: Supersede Versioning for Fact Updates

**What:** When a fact contradicts an existing active fact (similarity > 0.92), create a new fact that supersedes the old one rather than updating in place.

```python
# app/memory/service.py

async def supersede_fact(
    session: AsyncSession,
    old_fact_id: str,
    new_fact_data: dict,
    user_id: str,
) -> MemoryFact:
    """Create a new fact that supersedes an existing one."""
    from datetime import datetime, timezone

    # 1. Create new fact
    new_fact = MemoryFact(**new_fact_data, user_id=user_id)
    session.add(new_fact)
    await session.flush()  # Get new_fact.id before commit

    # 2. Invalidate old fact
    old = await session.get(MemoryFact, old_fact_id)
    old.valid_until = datetime.now(timezone.utc)
    old.superseded_by = new_fact.id

    await session.commit()
    return new_fact
```

**Schema alignment:** The Phase 1 schema has `valid_until` (timestamp) and `superseded_by` (UUID FK to same table). The `active_memory_facts` view filters `WHERE valid_until IS NULL AND superseded_by IS NULL` — so setting either field deactivates the fact.

### Pattern 8: HNSW Index Migration

**What:** A new migration to add an HNSW index on `memory_facts.embedding` for fast cosine similarity search. The Phase 1 migration does NOT include this index — only a B-tree index on `(user_id, category, key) WHERE valid_until IS NULL`.

```sql
-- Source: supabase.com/docs/guides/ai/vector-indexes/hnsw-indexes
-- velar-backend/supabase/migrations/20260302000001_memory_hnsw_index.sql

-- HNSW index for fast cosine similarity search on memory_facts embeddings
-- vector_cosine_ops: matches the <=> cosine distance operator used in retrieval queries
-- m=16, ef_construction=64: sensible defaults for datasets up to ~100K rows
CREATE INDEX IF NOT EXISTS memory_facts_embedding_hnsw
ON public.memory_facts
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### Anti-Patterns to Avoid

- **Query ALL facts then filter in Python:** Never `SELECT * FROM memory_facts WHERE user_id = X` then cosine similarity in Python. Use the pgvector `ORDER BY cosine_distance() LIMIT k` in SQL.
- **Skip HNSW index:** Without the index, every retrieval is a full sequential scan. At 1000+ facts per user, this becomes slow. Add the HNSW migration in Plan 03-01.
- **Block response on extraction:** Never `await extract_facts_from_conversation()` in the request handler. Always use `background_tasks.add_task()`.
- **Store embeddings without error handling:** OpenAI API can fail. Embedding failure should mean `embedding=NULL` (stored with no vector, excluded from semantic search until re-embedded) — not a failed request.
- **Forget asyncpg vector registration:** Without `register_vector` in the event listener, all queries touching `embedding` column will raise a codec error. Must be in `database.py` before any memory query.
- **Use the raw `memory_facts` table for retrieval:** Always query through the `active_memory_facts` view OR add explicit `WHERE valid_until IS NULL AND superseded_by IS NULL`. The view exists specifically for this.
- **Modify `valid_until` to delete:** For explicit DELETE, set `valid_until = now()` only. For supersede, set both `valid_until` and `superseded_by`. The hallucination guard distinguishes these.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cosine similarity search | Custom Python cosine calc + full table scan | `pgvector cosine_distance()` in SQL + HNSW index | Full scan at 10K facts = seconds; pgvector HNSW = milliseconds |
| JSON schema extraction from Claude | Regex/string parsing of Claude text | `output_config` structured output | Claude's free-form text can wrap JSON in ```json blocks, add commentary, etc.; structured output guarantees exact schema |
| Token counting for 2000-cap | Character estimation (÷4) | `tiktoken.get_encoding("cl100k_base").encode()` | Characters-to-tokens varies wildly for Turkish; tiktoken is exact |
| Async OpenAI client retry | Manual retry loop | OpenAI SDK retry built-in + `tenacity` for custom | SDK has built-in retry for transient errors; `tenacity` already in requirements |
| Fact deduplication | String comparison | Cosine similarity check at 0.92 threshold before store | "I'm allergic to nuts" and "nut allergy" are semantically identical; string match misses these |
| Embedding storage serialization | Custom numpy/binary serialization | pgvector-python `Vector` type | asyncpg codec via `register_vector` handles all serialization transparently |

**Key insight:** The hard work in memory systems is semantic deduplication. String equality fails entirely — "I don't eat gluten" and "gluten intolerance" are the same fact. The 0.92 cosine similarity threshold for the supersede check is what prevents memory bloat from rephrased facts.

---

## Common Pitfalls

### Pitfall 1: asyncpg Vector Codec Registration
**What goes wrong:** `UnicodeDecodeError` or `asyncpg.exceptions.UnknownPostgresError` when reading `embedding` column. Vector type not registered with asyncpg codec.
**Why it happens:** asyncpg is strict about type codecs. Unlike psycopg, it doesn't auto-discover PostgreSQL custom types.
**How to avoid:** Add `@event.listens_for(engine.sync_engine, "connect")` with `register_vector` in `database.py` BEFORE any memory query runs.
**Warning signs:** Tests that read/write embedding column fail with codec errors. Verify in Wave 0 with a simple insert+select of a dummy vector.

### Pitfall 2: Embedding Dimension Mismatch
**What goes wrong:** `ERROR: expected 1536 dimensions, not 512` when inserting an embedding.
**Why it happens:** Schema column is `vector(1536)`. If `dimensions=512` is accidentally passed to the OpenAI API, the stored vector will be rejected.
**How to avoid:** Always explicitly pass `dimensions=1536` in the OpenAI embedding call. Add an assertion in the embedding service: `assert len(embedding) == 1536`.
**Warning signs:** `sqlalchemy.exc.DataError` on INSERT with vector column.

### Pitfall 3: Background Task Accesses Request-Scoped DB Session
**What goes wrong:** `MissingGreenlet` error or use-after-close of SQLAlchemy session in background task.
**Why it happens:** FastAPI's `Depends(get_db)` is request-scoped — the session is closed when the response is sent. Background tasks run after.
**How to avoid:** Background tasks MUST create their own session via `async_session_factory()` context manager, NOT use a session injected via `Depends(get_db)`.
**Warning signs:** `sqlalchemy.exc.InvalidRequestError: This Session's transaction has been rolled back due to a previous exception`.

```python
# CORRECT background task pattern:
async def store_extracted_facts(user_id: str, facts: list[dict]):
    async with async_session_factory() as session:  # own session, not Depends()
        for fact in facts:
            session.add(MemoryFact(**fact, user_id=user_id))
        await session.commit()
```

### Pitfall 4: `active_memory_facts` View Not RLS-Protected
**What goes wrong:** `active_memory_facts` is a view, not a table. Views do not automatically inherit table RLS policies. Querying the view without `set_session()` could expose other users' facts.
**Why it happens:** PostgreSQL view security behavior: views run with the definer's permissions by default (security definer). RLS on the base table applies to direct queries but view queries bypass RLS unless the view is `WITH (security_invoker = true)`.
**How to avoid:** In Phase 3, always query `memory_facts` directly with `WHERE user_id = :user_id` in SQLAlchemy ORM, or use the user-scoped Supabase client that applies RLS. For raw SQL on the view, ensure `SECURITY INVOKER` is set (already handled by RLS on the table IF the view is `security_invoker`). The Phase 1 schema did not set this — verify in Phase 3.
**Warning signs:** Tests with two users show one user's facts visible to another via the view.

### Pitfall 5: Hallucination Guard Complexity
**What goes wrong:** VELAR says "As you mentioned, you have a nut allergy" but the fact was never extracted/stored — Claude hallucinated a memory reference.
**Why it happens:** Claude trained on data where assistants reference remembered facts. If the system prompt says "here are your memories" and doesn't include nut allergy, Claude may still invent a reference.
**How to avoid:** The injection pattern must be explicit: "These are ALL the facts I know about you. If a fact is not listed here, you do NOT know it." The hallucination guard (cite `memory_fact_id`) is enforced at retrieval layer — if an ID is cited that doesn't exist in the top-k results, the claim is blocked.
**Warning signs:** Integration tests where memory context is empty but Claude still claims facts about the user.

### Pitfall 6: Contradiction Detection Query Cost
**What goes wrong:** Checking cosine similarity of every new fact against ALL existing facts before storing becomes expensive at 10K+ facts.
**Why it happens:** Full similarity search with high threshold requires scanning all active facts per user.
**How to avoid:** Limit contradiction check to facts in the SAME category + first query top-5 by cosine similarity. If similarity > 0.92 among the top-5 in same category, supersede. This bounds the check to k=5 per category, not all facts.
**Warning signs:** Background extraction taking >5 seconds at scale.

---

## Code Examples

Verified patterns from official sources:

### Embedding with AsyncOpenAI
```python
# Source: platform.openai.com/docs/api-reference/embeddings
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=settings.openai_api_key)

response = await client.embeddings.create(
    model="text-embedding-3-small",
    input="I'm allergic to nuts",
    dimensions=1536,  # explicit — match schema column
)
embedding: list[float] = response.data[0].embedding
# len(embedding) == 1536
```

### Cosine Distance Query (SQLAlchemy async)
```python
# Source: pgvector-python README, github.com/pgvector/pgvector-python
from pgvector.sqlalchemy import cosine_distance

stmt = (
    select(MemoryFact)
    .where(
        MemoryFact.user_id == user_id,
        MemoryFact.valid_until.is_(None),
        MemoryFact.superseded_by.is_(None),
    )
    .order_by(cosine_distance(MemoryFact.embedding, query_embedding))
    .limit(10)
)
facts = (await session.scalars(stmt)).all()
```

### Claude Structured Output for Extraction
```python
# Source: platform.claude.com/docs/en/build-with-claude/structured-outputs
# GA on Claude Haiku 4.5 (confirmed, no beta header needed)
import json

response = await asyncio.to_thread(
    client.messages.create,
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    system=EXTRACTION_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": conversation_text}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": EXTRACTION_SCHEMA,
        }
    },
)
facts: list[dict] = json.loads(response.content[0].text).get("facts", [])
```

### HNSW Index SQL (migration)
```sql
-- Source: supabase.com/docs/guides/ai/vector-indexes/hnsw-indexes
CREATE INDEX IF NOT EXISTS memory_facts_embedding_hnsw
ON public.memory_facts
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### FastAPI BackgroundTasks Integration
```python
# Source: fastapi.tiangolo.com/tutorial/background-tasks/
from fastapi import BackgroundTasks

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
):
    response_text = await run_conversation(request.message, ...)

    # Non-blocking: runs AFTER response is sent
    background_tasks.add_task(
        store_extracted_facts,
        user_message=request.message,
        assistant_response=response_text,
        user_id=current_user["user_id"],
    )

    return ChatResponse(...)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `output_format` parameter + `structured-outputs-2025-11-13` beta header | `output_config.format` (no beta header) | GA release late 2025 | Simpler API; beta header optional during transition |
| IVFFlat vector index (requires data before creation) | HNSW index (can create immediately, self-updates) | pgvector 0.5+ / Supabase 2023+ | HNSW preferred; no need to wait for data |
| `text-embedding-ada-002` (1536 dims) | `text-embedding-3-small` (1536 dims, better quality) | OpenAI Jan 2024 | Better quality, same price, same dimensions — direct drop-in |
| Synchronous OpenAI client + `to_thread` | `AsyncOpenAI` native async client | openai Python SDK >=1.0 | Cleaner async; no thread overhead for embedding calls |

**Deprecated/outdated:**
- `output_format` top-level parameter: replaced by `output_config.format`; still works during transition but use new form
- `text-embedding-ada-002`: legacy model; use `text-embedding-3-small` (same 1536 dim, better MTEB scores, same price)
- IVFFlat index: valid but requires data before creation; HNSW preferred for Phase 3 which starts with empty table

---

## Open Questions

1. **asyncpg `register_vector` sync bridge**
   - What we know: `pgvector.asyncpg.register_vector` is async; SQLAlchemy `connect` event fires synchronously; `AdaptedConnection.run_sync()` is the bridge
   - What's unclear: Whether `run_sync()` is the correct method name on asyncpg's adapted connection (vs `run_async()`) — documentation is ambiguous
   - Recommendation: In Wave 0 (plan 03-01), write a minimal test that inserts and retrieves a `vector(1536)` value through the existing async engine. If codec fails, try alternative: `dbapi_connection.run_async(register_vector)`.

2. **SECURITY INVOKER on active_memory_facts view**
   - What we know: Phase 1 created the view without `WITH (security_invoker = true)`; RLS is on the base table; view behavior depends on PostgreSQL RLS invoker setting
   - What's unclear: Does the view respect RLS for the authenticated user or bypass it?
   - Recommendation: In plan 03-01, add a migration to `CREATE OR REPLACE VIEW public.active_memory_facts WITH (security_invoker = true) AS ...` or simply never query the view — always query `memory_facts` directly with ORM filters.

3. **Token counting: tiktoken vs anthropic's tokenizer**
   - What we know: `tiktoken cl100k_base` is OpenAI's tokenizer and a close approximation for Claude; not identical
   - What's unclear: How much error does this introduce for the 2000-token cap?
   - Recommendation: Add 10% safety margin — cap at 1800 tokens using tiktoken counting. This ensures the injected context never overflows even with tokenizer discrepancy.

---

## Validation Architecture

*(workflow.nyquist_validation is not set in .planning/config.json — this section follows standard test documentation)*

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `velar-backend/pyproject.toml` (`asyncio_mode = "auto"`) |
| Quick run command | `cd velar-backend && python -m pytest tests/test_memory_api.py tests/test_memory_extraction.py -x -q` |
| Full suite command | `cd velar-backend && python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MEM-01 | Fact stored permanently with correct schema fields | unit | `pytest tests/test_memory_api.py::test_create_fact -x` | Wave 0 |
| MEM-01 | Embedding stored and retrievable as 1536-dim vector | unit | `pytest tests/test_memory_retrieval.py::test_vector_roundtrip -x` | Wave 0 |
| MEM-02 | Semantic retrieval returns relevant facts for query | unit | `pytest tests/test_memory_retrieval.py::test_semantic_retrieval -x` | Wave 0 |
| MEM-02 | Summary endpoint synthesizes facts accurately | unit | `pytest tests/test_memory_api.py::test_memory_summary -x` | Wave 0 |
| MEM-03 | Background extraction runs after voice/chat turn | unit | `pytest tests/test_memory_extraction.py::test_background_extraction -x` | Wave 0 |
| MEM-03 | Extraction returns zero facts for small-talk | unit | `pytest tests/test_memory_extraction.py::test_empty_extraction -x` | Wave 0 |
| MEM-04 | Soft delete deactivates fact | unit | `pytest tests/test_memory_api.py::test_delete_fact -x` | Wave 0 |
| MEM-04 | PATCH creates superseding version | unit | `pytest tests/test_memory_api.py::test_update_fact_supersedes -x` | Wave 0 |
| MEM-04 | Contradiction detection triggers supersede | unit | `pytest tests/test_memory_extraction.py::test_contradiction_detection -x` | Wave 0 |
| MEM-05 | Active facts retrievable after separate session (cross-device sim) | integration | `pytest tests/test_memory_api.py::test_cross_session_retrieval -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd velar-backend && python -m pytest tests/test_memory_api.py tests/test_memory_extraction.py tests/test_memory_retrieval.py -x -q`
- **Per wave merge:** `cd velar-backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_memory_api.py` — covers MEM-01 CRUD, MEM-04 delete/update, MEM-05 retrieval
- [ ] `tests/test_memory_extraction.py` — covers MEM-03 background extraction, contradiction detection
- [ ] `tests/test_memory_retrieval.py` — covers MEM-02 semantic search, vector roundtrip
- [ ] Framework install: `pip install pgvector openai tiktoken` — add to `requirements.txt`
- [ ] `openai_api_key` setting in `app/config.py` — needed before any test that calls real embedding API

---

## Sources

### Primary (HIGH confidence)
- `platform.claude.com/docs/en/build-with-claude/structured-outputs` — `output_config.format` API shape, GA status for Haiku 4.5, Python code examples
- `github.com/pgvector/pgvector-python` README — Vector column type, cosine_distance function, HNSW index creation via SQLAlchemy Index(), asyncpg registration pattern
- `supabase.com/docs/guides/ai/vector-indexes/hnsw-indexes` — HNSW index SQL syntax with `vector_cosine_ops`, 2000-dimension limit, performance guidance
- `platform.openai.com/docs/api-reference/embeddings` — text-embedding-3-small default 1536 dims, `dimensions` parameter, AsyncOpenAI client
- `fastapi.tiangolo.com/tutorial/background-tasks/` — BackgroundTasks.add_task(), async function support, post-response execution guarantee

### Secondary (MEDIUM confidence)
- `deepwiki.com/pgvector/pgvector-python/3.1-sqlalchemy-integration` — confirmed asyncpg event listener pattern with `engine.sync_engine`
- Zilliz/OpenAI community threads — confirmed text-embedding-3-small default is 1536 dimensions, $0.02/1M tokens pricing
- Multiple WebSearch results — FastAPI BackgroundTasks session lifecycle (request-scoped vs task-scoped)

### Tertiary (LOW confidence)
- Community examples for `run_sync` vs `run_async` method on asyncpg AdaptedConnection — needs empirical verification in Wave 0 test

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pgvector, openai, FastAPI BackgroundTasks all verified via official sources
- Architecture: HIGH — patterns verified via official docs; asyncpg event listener has ONE low-confidence detail (`run_sync` vs `run_async`) flagged in Open Questions
- Pitfalls: HIGH — all pitfalls grounded in known SQLAlchemy/asyncpg/pgvector behaviors; hallucination guard design verified against project decisions

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (pgvector, OpenAI SDK, Claude API are all stable; check Claude API if >30 days)
