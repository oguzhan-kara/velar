---
phase: 03-memory-system
plan: "01"
subsystem: database
tags: [pgvector, openai, tiktoken, sqlalchemy, embeddings, semantic-search, hnsw]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: memory_facts table with Vector(1536) embedding column and RLS policies

provides:
  - pgvector codec registered in SQLAlchemy async engine (connect event listener)
  - HNSW index migration for memory_facts.embedding (cosine distance)
  - MemoryFact ORM model (SQLAlchemy, EAV pattern, versioning columns)
  - OpenAI embedding service (text-embedding-3-small, 1536-dim, lazy singleton)
  - Semantic retrieval: get_relevant_facts, facts_to_context_string (1800-token cap)
  - get_all_active_facts for summary endpoint
  - 11 unit tests (mocked embeddings + DB, no .env required)

affects:
  - 03-02 (memory write pipeline uses embeddings.py and models.py)
  - 03-03 (memory lifecycle uses retrieval.py for context injection)
  - 04 (proactive suggestions rely on semantic retrieval)

# Tech tracking
tech-stack:
  added:
    - pgvector 0.4.2 (asyncpg codec + SQLAlchemy ORM Vector type)
    - openai>=1.0 (AsyncOpenAI, text-embedding-3-small)
    - tiktoken (cl100k_base tokenizer for token cap enforcement)
  patterns:
    - Event listener pattern for pgvector codec: @event.listens_for(engine.sync_engine, "connect") with dbapi_connection.run_sync(register_vector)
    - Lazy singleton client pattern (same as Phase 2 STT/TTS)
    - Active-only filter pattern: valid_until IS NULL AND superseded_by IS NULL (never query view directly)
    - 10% token cap safety margin: 1800 tokens not 2000 (tiktoken/Claude tokenizer divergence on Turkish)
    - cosine_distance as column comparator method: MemoryFact.embedding.cosine_distance(vec) not standalone import

key-files:
  created:
    - velar-backend/app/memory/__init__.py
    - velar-backend/app/memory/models.py
    - velar-backend/app/memory/embeddings.py
    - velar-backend/app/memory/retrieval.py
    - velar-backend/supabase/migrations/20260302000001_memory_hnsw_index.sql
    - velar-backend/tests/test_memory_retrieval.py
  modified:
    - velar-backend/requirements.txt (added pgvector, openai>=1.0, tiktoken)
    - velar-backend/app/config.py (added openai_api_key: str = "")
    - velar-backend/app/database.py (added pgvector connect event listener)

key-decisions:
  - "TIMESTAMP(timezone=True) used instead of TIMESTAMPTZ — TIMESTAMPTZ is not a valid SQLAlchemy dialect import"
  - "cosine_distance is a comparator method on Vector columns (MemoryFact.embedding.cosine_distance(vec)), not a standalone import from pgvector.sqlalchemy"
  - "Token cap at 1800 not 2000 — 10% safety margin absorbs tiktoken/Claude tokenizer divergence especially for Turkish text"
  - "HNSW index preferred over IVFFlat — HNSW works on empty table at start, IVFFlat requires data before creation"
  - "active_memory_facts view re-created WITH (security_invoker = true) in migration — Python code always queries memory_facts directly (never the view) as additional safeguard"
  - "mock_scalars uses MagicMock not AsyncMock — result.all() in retrieval.py is synchronous (called after await session.scalars())"

patterns-established:
  - "Active-only fact filter: always use valid_until.is_(None) AND superseded_by.is_(None) in ORM queries, never query active_memory_facts view from Python"
  - "Embedding null guard: MemoryFact.embedding.is_not(None) filter in retrieval query — facts stored without embedding are excluded from semantic search"
  - "Graceful degradation: RuntimeError from OpenAI embedding returns [] from get_relevant_facts, never crashes request"

requirements-completed: [MEM-01, MEM-02, MEM-05]

# Metrics
duration: 6min
completed: "2026-03-02"
---

# Phase 3 Plan 01: pgvector Infrastructure, Embedding Service, and Semantic Retrieval Summary

**pgvector HNSW index, AsyncOpenAI text-embedding-3-small service, and SQLAlchemy semantic retrieval with 1800-token context cap on memory_facts**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-02T15:19:45Z
- **Completed:** 2026-03-02T15:25:55Z
- **Tasks:** 4
- **Files modified:** 9

## Accomplishments

- pgvector codec registered per-connection via SQLAlchemy event listener — no codec errors on memory_facts.embedding reads/writes
- HNSW index migration (m=16, ef_construction=64) + active_memory_facts view re-created with security_invoker=true
- MemoryFact ORM (EAV triple, Vector(1536), valid_from/valid_until/superseded_by versioning) + full embedding/retrieval service
- 11 unit tests pass with mocked OpenAI and mocked DB — no .env file required

## Task Commits

Each task was committed atomically:

1. **Task T1: Install dependencies and add openai_api_key config** - `1687a86` (feat)
2. **Task T2: Register pgvector codec in database.py and add HNSW migration** - `be86352` (feat)
3. **Task T3: Create app/memory module: ORM model, embedding service, and semantic retrieval** - `2a2dd3d` (feat)
4. **Task T4: Write test_memory_retrieval.py with mocked embeddings and DB** - `35329a4` (test)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `velar-backend/requirements.txt` — Added pgvector, openai>=1.0, tiktoken under Memory system (Phase 3) comment
- `velar-backend/app/config.py` — Added openai_api_key: str = "" under Memory system (Phase 3) comment
- `velar-backend/app/database.py` — Added @event.listens_for(engine.sync_engine, "connect") with dbapi_connection.run_sync(register_vector)
- `velar-backend/supabase/migrations/20260302000001_memory_hnsw_index.sql` — HNSW index + active_memory_facts view SECURITY INVOKER fix
- `velar-backend/app/memory/__init__.py` — Package docstring
- `velar-backend/app/memory/models.py` — MemoryFact ORM (Vector(1536), TIMESTAMP(timezone=True), self-referential superseded_by FK)
- `velar-backend/app/memory/embeddings.py` — AsyncOpenAI lazy singleton, text-embedding-3-small, 1536-dim assertion
- `velar-backend/app/memory/retrieval.py` — get_relevant_facts, facts_to_context_string (1800-token cap), get_all_active_facts
- `velar-backend/tests/test_memory_retrieval.py` — 11 unit tests, sys.modules config injection pattern

## Decisions Made

- TIMESTAMP(timezone=True) used instead of TIMESTAMPTZ — TIMESTAMPTZ is not exported from sqlalchemy.dialects.postgresql; the correct import is TIMESTAMP with timezone=True
- cosine_distance is a comparator method on pgvector 0.4.2's Vector column type, accessed as MemoryFact.embedding.cosine_distance(vec), not importable as a standalone function
- mock_scalars in tests uses MagicMock not AsyncMock — result.all() is synchronous (SQLAlchemy scalars result is sync after being awaited)
- Token cap set at 1800 (not 2000) per plan specification — 10% safety margin for tiktoken/Claude tokenizer gap on Turkish text

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TIMESTAMPTZ not importable from sqlalchemy.dialects.postgresql**
- **Found during:** T3 (Create app/memory module — ORM model)
- **Issue:** Plan specified `from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ` but TIMESTAMPTZ is not in SQLAlchemy's postgresql dialect exports
- **Fix:** Changed to `from sqlalchemy import TIMESTAMP` and aliased `TIMESTAMPTZ = TIMESTAMP(timezone=True)`
- **Files modified:** velar-backend/app/memory/models.py
- **Verification:** `from app.memory.models import MemoryFact` succeeds
- **Committed in:** 2a2dd3d (Task T3 commit)

**2. [Rule 1 - Bug] cosine_distance is a comparator method, not a standalone import**
- **Found during:** T3 (Create app/memory module — retrieval)
- **Issue:** Plan specified `from pgvector.sqlalchemy import cosine_distance` but pgvector 0.4.2 does not export this as a standalone function; ImportError on module load
- **Fix:** Removed the import; changed ORDER BY to `MemoryFact.embedding.cosine_distance(query_embedding)` (correct pgvector 0.4.2 API)
- **Files modified:** velar-backend/app/memory/retrieval.py
- **Verification:** Module imports successfully; ORDER BY compiles correctly
- **Committed in:** 2a2dd3d (Task T3 commit)

**3. [Rule 1 - Bug] AsyncMock vs MagicMock for scalars result in tests**
- **Found during:** T4 (Write test suite)
- **Issue:** Tests used AsyncMock for mock_scalars, causing `result.all()` to return a coroutine instead of a list (`.all()` is synchronous on SQLAlchemy's already-awaited scalars result)
- **Fix:** Changed mock_scalars = AsyncMock() to mock_scalars = MagicMock() in two test methods
- **Files modified:** velar-backend/tests/test_memory_retrieval.py
- **Verification:** All 11 tests pass: `pytest tests/test_memory_retrieval.py -x -q`
- **Committed in:** 35329a4 (Task T4 commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** All fixes necessary for correctness — pgvector 0.4.2 API differs slightly from plan's assumed API surface. No scope creep.

## Issues Encountered

Pre-existing environment issue (out-of-scope, logged to deferred-items.md): `anthropic` and `soundfile` packages not installed in current venv session — affects Phase 2 test_auth.py and test_voice_*.py when running full suite. These failures are pre-existing and not caused by Phase 3 changes. Fix: `pip install -r requirements.txt`.

## User Setup Required

**Migration must be applied to Supabase cloud project before any memory endpoint is usable:**

1. Open Supabase dashboard > SQL Editor
2. Paste contents of `velar-backend/supabase/migrations/20260302000001_memory_hnsw_index.sql`
3. Execute
4. Verify in Table Editor > memory_facts > Indexes: should show `memory_facts_embedding_hnsw`

**Add to .env:**
```
OPENAI_API_KEY=sk-...  # Required for embeddings; memory endpoints fail without it
```

## Next Phase Readiness

- Retrieval layer complete: get_relevant_facts + facts_to_context_string ready for Plan 03-02 (memory write pipeline)
- pgvector codec registered — memory_facts.embedding reads/writes will not raise codec errors
- HNSW migration pending Supabase cloud apply (can apply before or during 03-02)
- Plan 03-02 builds on MemoryFact model and get_embedding service created here

---
*Phase: 03-memory-system*
*Completed: 2026-03-02*

## Self-Check: PASSED

All files found, all commits verified:
- FOUND: velar-backend/requirements.txt
- FOUND: velar-backend/app/config.py
- FOUND: velar-backend/app/database.py
- FOUND: velar-backend/supabase/migrations/20260302000001_memory_hnsw_index.sql
- FOUND: velar-backend/app/memory/__init__.py
- FOUND: velar-backend/app/memory/models.py
- FOUND: velar-backend/app/memory/embeddings.py
- FOUND: velar-backend/app/memory/retrieval.py
- FOUND: velar-backend/tests/test_memory_retrieval.py
- FOUND: .planning/phases/03-memory-system/03-01-SUMMARY.md
- FOUND commit: 1687a86 (T1)
- FOUND commit: be86352 (T2)
- FOUND commit: 2a2dd3d (T3)
- FOUND commit: 35329a4 (T4)
