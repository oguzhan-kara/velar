---
phase: 03-memory-system
plan: "02"
subsystem: api
tags: [memory, pgvector, extraction, claude-haiku, background-tasks, fastapi, sqlalchemy]

# Dependency graph
requires:
  - phase: 03-01-memory-system
    provides: MemoryFact ORM model, get_embedding(), get_relevant_facts(), facts_to_context_string(), pgvector HNSW migration

provides:
  - Memory schemas (FactCreate, FactUpdate, FactResponse, FactListResponse, MemorySummaryResponse)
  - Memory service layer (store_fact, store_extracted_facts, soft_delete_fact, update_fact, supersede pattern)
  - Claude-based background extraction (extract_facts_from_conversation with output_config structured output)
  - /memory CRUD API — 5 endpoints: GET list, POST create, PATCH update, DELETE soft-delete, GET search/summary
  - Memory context injection into run_conversation() with hallucination guard
  - Background fact extraction after every /chat and /voice turn via FastAPI BackgroundTasks
  - Full MEM-01 through MEM-05 requirement satisfaction

affects:
  - 04-tool-use
  - 05-notifications
  - 06-cross-device

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Background task session pattern: store_extracted_facts creates its own AsyncSession via async_session_factory() — never uses request-scoped Depends(get_db)
    - Contradiction detection: cosine similarity > 0.92 threshold triggers supersede instead of new fact insert
    - output_config (not output_format) for Claude Haiku structured output GA API
    - Hallucination guard pattern: [VELAR MEMORY] block in system prompt with explicit "do NOT know" constraint
    - Force-set sys.modules injection in tests (not setdefault) with complete settings mock including database_url

key-files:
  created:
    - velar-backend/app/memory/schemas.py
    - velar-backend/app/memory/service.py
    - velar-backend/app/memory/extraction.py
    - velar-backend/app/memory/router.py
    - velar-backend/tests/test_memory_extraction.py
    - velar-backend/tests/test_memory_api.py
  modified:
    - velar-backend/app/voice/conversation.py
    - velar-backend/app/voice/router.py
    - velar-backend/app/main.py

key-decisions:
  - "output_config (not output_format) for Claude Haiku structured JSON output — GA API, no beta headers"
  - "Background task store_extracted_facts creates own AsyncSession via async_session_factory() — not request-scoped"
  - "Cosine similarity threshold 0.92 for contradiction detection — supersede instead of duplicate insert"
  - "Hallucination guard injected into run_conversation() system prompt when memory_context is non-empty"
  - "voice_endpoint background extraction added but memory RETRIEVAL not added to /voice (streaming pipeline refactor deferred)"
  - "Test config mock: force-set sys.modules['app.config'] with complete settings (database_url as string) in each test — prevents MagicMock URL errors from test_streaming.py's module-level injection"

patterns-established:
  - "Memory background task pattern: FastAPI BackgroundTasks.add_task(store_extracted_facts, ...) after response assembled"
  - "Memory context injection: get_relevant_facts() + facts_to_context_string() before run_conversation() in chat_endpoint"
  - "Hallucination guard: VELAR MEMORY block with 'do NOT know' constraint, injected only when memory_context is non-empty"

requirements-completed: [MEM-01, MEM-02, MEM-03, MEM-04, MEM-05]

# Metrics
duration: 17min
completed: 2026-03-02
---

# Phase 3 Plan 02: Extraction Pipeline, Memory Service, CRUD API, and Conversation Integration Summary

**Claude-based background fact extraction after every /chat and /voice turn, /memory CRUD API with 5 endpoints, contradiction-aware supersede logic, and hallucination-guarded memory context injection into system prompt — satisfying all 5 MEM requirements**

## Performance

- **Duration:** 17 min
- **Started:** 2026-03-02T15:30:29Z
- **Completed:** 2026-03-02T15:47:08Z
- **Tasks:** 4
- **Files modified:** 9

## Accomplishments

- Full memory service layer with store_fact, soft_delete_fact, update_fact, and _supersede_fact — contradiction detection at 0.92 cosine similarity threshold
- Background extraction pipeline using Claude Haiku structured output (output_config) — non-fatal, runs after every /chat and /voice turn
- /memory CRUD API with 5 endpoints — list (paginated/filterable), create, PATCH supersede, DELETE soft-delete, GET semantic search/summary
- Memory context injected into run_conversation() with hallucination guard: "If a fact is not listed in [VELAR MEMORY], I do NOT know it"
- 17 new tests (test_memory_extraction.py + test_memory_api.py) — all pass, no regressions in Phase 2 suite

## Task Commits

Each task was committed atomically:

1. **Task T1: Memory schemas, service layer, and extraction pipeline** - `64cf2d5` (feat)
2. **Task T2: /memory CRUD API router and main.py registration** - `aad2091` (feat)
3. **Task T3: Integrate memory retrieval into conversation and voice router** - `1b23d9b` (feat)
4. **Task T4: Write test suites — test_memory_api.py and test_memory_extraction.py** - `1a2ae81` (test)

## Files Created/Modified

- `velar-backend/app/memory/schemas.py` — Pydantic schemas: FactCreate, FactUpdate, FactResponse, FactListResponse, MemorySummaryResponse
- `velar-backend/app/memory/service.py` — Service layer: store_fact with cosine-similarity contradiction detection, _supersede_fact (atomic), store_extracted_facts (background), soft_delete_fact, update_fact
- `velar-backend/app/memory/extraction.py` — Claude Haiku structured extraction using output_config with JSON schema; NEVER raises (non-fatal background task)
- `velar-backend/app/memory/router.py` — 5 /memory endpoints; search endpoint handles summary-intent queries (Turkish/English) vs semantic search
- `velar-backend/app/voice/conversation.py` — Added memory_context parameter; [VELAR MEMORY] block with hallucination guard injected when context non-empty
- `velar-backend/app/voice/router.py` — chat_endpoint: memory retrieval + BackgroundTasks; voice_endpoint: BackgroundTasks extraction
- `velar-backend/app/main.py` — memory_router registered under /api/v1
- `velar-backend/tests/test_memory_extraction.py` — 10 tests: extraction, small-talk, API failure, no-key, session factory, threshold, output_config
- `velar-backend/tests/test_memory_api.py` — 7 tests: CRUD 201/204/200/404, hallucination guard, cross-session isolation design check

## Decisions Made

- `output_config` (not deprecated `output_format`) for Claude Haiku structured JSON output — GA API, no beta headers required
- Background task `store_extracted_facts` creates its own `AsyncSession` via `async_session_factory()` — request-scoped session is closed before background task runs
- Cosine similarity threshold 0.92 for contradiction detection — empirically chosen starting point, tune later
- voice_endpoint gets background extraction but NOT memory retrieval — adding retrieval to streaming pipeline requires refactoring `stream_conversation_to_audio`, deferred
- Test mock pattern: force-set `sys.modules["app.config"]` with complete settings including `database_url` as string in each test — prevents `MagicMock` URL errors from test ordering conflicts

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed cosine_distance usage in service.py contradiction detection**
- **Found during:** Task T1 (service.py creation)
- **Issue:** Plan's service.py used `cosine_distance(MemoryFact.embedding, embedding)` as a standalone import (matching original plan code). The ORM model uses `MemoryFact.embedding.cosine_distance(embedding)` as a comparator method (established in 03-01).
- **Fix:** Used `MemoryFact.embedding.cosine_distance(embedding)` in the scalar distance query, consistent with 03-01's established pattern
- **Files modified:** velar-backend/app/memory/service.py
- **Committed in:** 64cf2d5 (Task T1 commit)

**2. [Rule 1 - Bug] Fixed "output_format" string in extraction.py docstring**
- **Found during:** Task T1 verification (test assertion checking no "output_format" in source)
- **Issue:** The plan's docstring said "Use output_config.format, not output_format" — the word "output_format" appears in the docstring and would fail the test assertion
- **Fix:** Rephrased docstring to "Use output_config.format (the GA parameter)" — removes the word from source
- **Files modified:** velar-backend/app/memory/extraction.py
- **Committed in:** 64cf2d5 (Task T1 commit)

**3. [Rule 1 - Bug] Fixed BackgroundTasks parameter ordering in voice_endpoint**
- **Found during:** Task T3 verification
- **Issue:** Plan placed `background_tasks: BackgroundTasks` after `audio: UploadFile = File(...)` (parameter with default). Python raises SyntaxError when parameter without default follows one with default.
- **Fix:** Moved `background_tasks: BackgroundTasks` before `audio: UploadFile = File(...)`
- **Files modified:** velar-backend/app/voice/router.py
- **Committed in:** 1b23d9b (Task T3 commit)

**4. [Rule 1 - Bug] Fixed test mock pattern for sys.modules injection**
- **Found during:** Task T4 (test suite verification with full test run)
- **Issue:** Plan used `sys.modules.setdefault("app.config", _mock_config)` at module level. When full suite runs, `test_streaming.py`'s module-level `_inject_mock_config()` (a pre-existing pattern) overwrites `app.config` with an incomplete mock (no `database_url`). This causes SQLAlchemy `ValueError` when memory test fixtures later import `app.main` and `app.database`.
- **Fix:** Changed to force-set `sys.modules["app.config"] = ...` inside each fixture/test function (lazy, not module-level), with complete settings including `database_url` as a real string
- **Files modified:** velar-backend/tests/test_memory_api.py, velar-backend/tests/test_memory_extraction.py
- **Committed in:** 1a2ae81 (Task T4 commit)

---

**Total deviations:** 4 auto-fixed (all Rule 1 — bugs)
**Impact on plan:** All fixes necessary for correctness. No scope creep. The test ordering issue (deviation 4) was a pre-existing pattern conflict, not a new bug.

## Issues Encountered

- Pre-existing `test_auth.py` errors: 4 errors in full suite from `test_streaming.py`'s module-level config injection (pre-existed before this plan). Our changes maintained identical test counts: `63 passed, 7 skipped, 4 errors`. No new failures introduced.

## Next Phase Readiness

- All 5 MEM requirements satisfied — memory system complete
- Phase 3 complete: pgvector infra (03-01) + full memory pipeline (03-02)
- Phase 4 (Tool Use: calendar, reminders) can use memory context from `get_relevant_facts()` for proactive tool suggestions
- Supabase HNSW migration (from 03-01) must still be applied to cloud before memory endpoints are usable in production

---
*Phase: 03-memory-system*
*Completed: 2026-03-02*
