---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-03-02T17:02:00Z"
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 10
  completed_plans: 10
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** VELAR thinks ahead for you — it anticipates what you need before you realize it yourself.
**Current focus:** Phase 4 — Mac Daemon

## Current Position

Phase: 4 of 7 (Mac Daemon and Integrations)
Plan: 3 of 3 in current phase (COMPLETE)
Status: Phase 4 complete — 04-01 (daemon shell), 04-02 (audio capture + backend POST), 04-03 (4 integration tools + tool loop) all done
Last activity: 2026-03-02 — Completed 04-03: TOOL_DEFINITIONS (4 tools), execute_tool dispatcher, active tool_use loop in conversation.py, 5 unit tests, INTG-01 through INTG-04 satisfied

Progress: [█████████░] 82%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 5 min
- Total execution time: 0.50 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 2 | 7 min | 3.5 min |
| 02-voice-pipeline | 3 | 17 min | 5.7 min |
| 03-memory-system | 2 | 23 min | 11.5 min |
| 04-mac-daemon | 3 | 19 min | 6.3 min |

**Recent Trend:**
- Last 5 plans: 03-01 (6 min), 03-02 (17 min), 04-01 (5 min), 04-02 (7 min), 04-03 (7 min)
- Trend: stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Flutter for iPhone, Swift for Watch, FastAPI backend, Supabase + pgvector for data and memory
- [Roadmap]: Advice features (food, social, place) placed in Phase 7 — they require accumulated memory data from daily use to be meaningful
- [Roadmap]: SYNC requirements split across phases: SYNC-02 in Phase 1 (cloud schema), SYNC-01 in Phase 6 (cross-device conversation), SYNC-03 in Phase 5 (notification routing)
- [01-01]: Supabase runs as cloud project only — no local container in docker-compose (satisfies SYNC-02)
- [01-01]: pydantic-settings intentionally has no defaults for 5 secret vars — startup failure is desired behavior
- [01-01]: RLS policies use (select auth.uid()) caching syntax to avoid per-row function calls
- [01-01]: memory_facts uses EAV triple pattern with valid_from/valid_until/superseded_by for full audit trail
- [Phase 01-foundation]: JWT algorithm HS256 selected for Supabase JWT decode in dependencies.py; ES256/JWKS upgrade path documented in code
- [Phase 01-foundation]: supabase-py sync client wrapped in asyncio.to_thread for all Supabase calls — async client stability uncertain
- [Phase 01-foundation]: User-scoped Supabase client (anon_key + set_session) used in user-facing handlers; service_role_key never in request handlers
- [02-01]: device=cpu, compute_type=int8 for WhisperModel — cross-platform compatibility, no CUDA dependency
- [02-01]: language= NOT set in model.transcribe() — auto-detection handles Turkish/English and code-switching (VOICE-05)
- [02-01]: anthropic_api_key and elevenlabs_api_key default to empty string — app starts without voice keys; only voice endpoints fail
- [02-01]: get_stt_service() lazy singleton — model loads only on first call, not at import time
- [02-01]: conftest.py lazy app import — voice unit tests run without .env file (no Supabase credentials needed)
- [02-02]: claude-haiku-4-5-20251001 selected for voice — fastest model for voice latency per Phase 2 research
- [02-02]: Tool-use scaffold present as commented code in conversation.py — Phase 4+ adds real tools (calendar, reminders)
- [02-02]: ElevenLabs primary, Edge TTS automatic fallback — any exception triggers cascade to tr-TR-AhmetNeural / en-US-GuyNeural
- [02-02]: _LazyTTSProxy lazy singleton — TTSService.__init__ does lazy settings import, proxy defers until first synthesize() call
- [02-02]: sys.modules injection pattern for mock app.config in tests — avoids pydantic-settings ValidationError without .env
- [02-03]: stream_conversation_to_audio uses asyncio.to_thread (SDK sync) + asyncio.create_task per sentence for concurrent TTS dispatch
- [02-03]: SENTENCE_BOUNDARY_RE positive lookbehind (?<=[.!?]) keeps punctuation with sentence; whitespace after boundary consumed by split
- [02-03]: _safe_header() percent-encodes non-latin-1 chars in StreamingResponse headers (Turkish chars break HTTP latin-1 restriction)
- [02-03]: /voice uses sentence-boundary streaming pipeline; /chat stays sequential (JSON needs complete audio for base64 encoding)
- [03-01]: TIMESTAMP(timezone=True) used instead of TIMESTAMPTZ — TIMESTAMPTZ is not exported from sqlalchemy.dialects.postgresql
- [03-01]: cosine_distance is a comparator method on Vector columns (MemoryFact.embedding.cosine_distance(vec)), not a standalone import from pgvector.sqlalchemy
- [03-01]: Token cap at 1800 not 2000 — 10% safety margin absorbs tiktoken/Claude tokenizer divergence on Turkish text
- [03-01]: HNSW index preferred over IVFFlat — HNSW works on empty table at start; IVFFlat requires data before creation
- [03-01]: Active-only filter always via ORM (valid_until IS NULL AND superseded_by IS NULL) — never query active_memory_facts view from Python
- [03-02]: output_config (not output_format) for Claude Haiku structured JSON output — GA API, no beta headers required
- [03-02]: Background task store_extracted_facts creates own AsyncSession via async_session_factory() — request-scoped session is closed before background task runs
- [03-02]: Cosine similarity threshold 0.92 for contradiction detection — supersede instead of duplicate insert
- [03-02]: voice_endpoint gets background extraction but NOT memory retrieval — streaming pipeline refactor deferred
- [03-02]: Test config mock: force-set sys.modules['app.config'] with complete settings in each test — prevents MagicMock URL errors from test ordering conflicts
- [04-01]: inference_framework='onnx' explicitly set in Model() — tflite_runtime unavailable on macOS ARM64; onnxruntime handles .onnx models natively
- [04-01]: audio stream started only from application_will_finish_launching_, never __init__ — rumps deadlock prevention per research pitfall 2
- [04-01]: _on_wake 2s placeholder deferred to Phase 04-02 which wires real audio capture + backend POST
- [04-01]: paused flag uses atomic bool (no lock needed in CPython) — toggle from main thread, read from audio thread
- [04-03]: registry.py wraps each tool call in try/except so individual tool failures return prose strings rather than raising exceptions that crash the loop
- [04-03]: weather_tool defers settings import until after cache check — enables unit tests to pre-populate cache without needing a .env file
- [04-03]: places_tool uses Google Places Text Search (searchText) instead of Nearby Search — Text Search supports keyword queries better
- [04-03]: Existing tests updated to set mock_content.type = "text" and stop_reason = "end_turn" — required for new tool loop block.type check

### Pending Todos

None yet.

### Blockers/Concerns

- [Pre-Phase 2]: ElevenLabs Turkish TTS quality is unverified — must test empirically at Phase 2 start; Azure Cognitive Services tr-TR is fallback
- [Pre-Phase 2]: Whisper large-v3 Turkish WER on code-switched speech needs an acceptance test before advancing from Phase 2 (scaffold ready in 02-01, audio fixtures needed)
- [Pre-Phase 4]: openwakeword custom "Hey VELAR" wake word requires ~200 positive audio samples — scope decision needed (custom vs. generic trigger in v1)
- [Pre-Phase 5]: APScheduler v4 API is a rewrite from v3 — verify correct API surface before Phase 5 planning
- [03-01]: HNSW migration 20260302000001_memory_hnsw_index.sql must be applied to Supabase cloud before memory endpoints are usable
- [03-01]: anthropic and soundfile packages not installed in current venv — run pip install -r requirements.txt before Phase 2/3 integration tests

## Session Continuity

Last session: 2026-03-02
Stopped at: Completed 04-03-PLAN.md — 4 integration tools, tool_use loop activated, 5 unit tests, INTG-01 through INTG-04 satisfied. Phase 4 complete.
Resume file: None
