# Phase 3: Memory System - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

VELAR stores personal facts about the user in Supabase (the `memory_facts` table already exists from Phase 1), retrieves relevant facts semantically using pgvector embeddings, auto-extracts new facts from conversations, supports correction and deletion, and exposes a /memory CRUD API. The Phase 1 schema (entity-attribute-value triples + vector(1536) + supersede versioning) is the foundation. This phase populates and queries that schema intelligently.

Not in scope: UI for browsing memories, proactive use of memories in responses (that's Phase 5: Proactive Engine), Watch app sync (Phase 7).

</domain>

<decisions>
## Implementation Decisions

### Memory Granularity
- Atomic fact storage: one fact = one row. "I'm allergic to nuts" is one fact, not a structured health record
- Entity-attribute-value triple pattern: entity="user", attribute="allergy", value="nuts" — but stored as natural language text for the `fact_text` column, with structured fields for retrieval/filtering
- Embedding covers `fact_text` for semantic similarity — searching "dietary restrictions" should surface the nut allergy
- Facts have a `category` field for grouping: health, food, social, place, habit, work, preference (extensible)
- Confidence score tracked (0-1) — Claude-extracted facts start at 0.7, user-stated facts start at 1.0
- No maximum memory count in Phase 3 — relevance and recency govern retrieval, not hard limits

### What VELAR Remembers
- Auto-extraction from all conversations: health facts, food preferences, social relationships, places frequented, habits, work context
- No opt-in required — passive extraction from day one (established in Phase 1 project decisions)
- Sensitive categories (health, relationships) stored at same priority as others — user controls deletion
- Memory extraction happens asynchronously after each conversation turn — does not block the voice response
- Extraction via a second Claude call: given the conversation, extract zero or more new facts as JSON array
- No cross-user facts — all memories are scoped to the authenticated user (RLS already enforced by Phase 1 schema)

### Memory Correction and Versioning
- Natural conversation correction supported: "actually I moved to Ankara, not Istanbul" triggers extraction of a correcting fact
- Supersede pattern (already in schema): new fact sets `supersedes_id` pointing to old fact, old fact's `is_active` = false — never hard-deleted, versioned
- Explicit deletion via `/memory/{id}` DELETE endpoint — sets `is_active = false` without creating a new version
- Hallucination guard: Claude responses that reference a fact must cite a `memory_fact_id` — if the ID doesn't exist, the claim is flagged, not stated
- Contradiction detection: before storing a new fact, Claude checks for semantic similarity to existing active facts; if similarity > 0.92, treat as update (supersede), not new fact

### Memory Retrieval
- Semantic retrieval at conversation time: embed the current user message, query pgvector for top-k nearest facts (k=10), inject into Claude system prompt as context
- 2000-token cap on injected memory context — most relevant facts first
- `active_memory_facts` view (already created in Phase 1) used for all retrieval — never queries superseded facts
- Retrieval scoped to current user via RLS — no additional filtering needed
- "What do you know about me?" query returns a Claude-synthesized summary of all active facts, grouped by category — not a raw dump

### Memory API (CRUD)
- GET /api/v1/memory — list active facts (paginated, filterable by category)
- POST /api/v1/memory — manually add a fact
- PATCH /api/v1/memory/{id} — update fact text (creates superseding version)
- DELETE /api/v1/memory/{id} — deactivate (soft delete)
- GET /api/v1/memory/search?q= — semantic search against stored facts
- All endpoints require JWT auth (Depends(get_current_user)); RLS applies at database layer too

### Claude's Discretion
- Exact embedding model (OpenAI text-embedding-3-small vs Supabase built-in vs Cohere)
- Extraction prompt engineering details
- Exact similarity threshold values (start with 0.92, tune empirically)
- Pagination defaults (page size, max)
- Background task queue implementation (FastAPI BackgroundTasks vs asyncio)
- Error handling for embedding API failures

</decisions>

<specifics>
## Specific Ideas

- The Morning Briefing demo (Phase 5) depends on rich memories: "You haven't eaten breakfast 3 days in a row" requires food habit memory. Phase 3 must extract habit patterns, not just one-off facts.
- User said "total life awareness" and "everything" — memory extraction should be liberal, not conservative. Better to store too much and let the user delete than to miss important facts.
- Supersede pattern preserves history — useful for future phases to show "VELAR noticed your eating improved over 30 days"
- The hallucination guard is critical: VELAR must never confidently state a fact it doesn't actually have stored

</specifics>

<deferred>
## Deferred Ideas

- Memory browser UI (visual list/timeline of all facts) — Phase 6 (iPhone App)
- Proactive use of memories ("By the way, you mentioned you're allergic to nuts — that restaurant you bookmarked has a peanut dish") — Phase 5 (Proactive Engine)
- Memory-based pattern detection ("You haven't slept well 3 days in a row") — Phase 5
- Cross-device memory sync UI — Phase 6/7 (memory is already cross-device via Supabase, just no UI)
- Memory sharing between users — explicitly out of scope for v1

</deferred>

---

*Phase: 03-memory-system*
*Context gathered: 2026-03-02*
