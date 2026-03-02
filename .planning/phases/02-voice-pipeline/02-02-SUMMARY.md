---
phase: 02-voice-pipeline
plan: 02
subsystem: voice-conversation
tags: [claude, anthropic, tts, elevenlabs, edge-tts, fastapi, voice-pipeline, turkish, tenacity, testing, mock]

dependency_graph:
  requires:
    - 02-01  # STTService, schemas (ChatRequest, ChatResponse, STTResult), config keys
    - 01-foundation-01  # config.py, project structure
    - 01-foundation-02  # dependencies.py (get_current_user), conftest.py
  provides:
    - Claude Haiku conversation loop with VELAR system prompt and tool-use scaffold
    - ElevenLabs TTS (eleven_flash_v2_5) with Edge TTS automatic fallback
    - POST /api/v1/voice endpoint — audio-in, audio-out (STT -> Claude -> TTS)
    - POST /api/v1/chat endpoint — text-in, JSON-out (Claude -> TTS)
    - Both endpoints protected by JWT authentication
  affects:
    - 02-03 (E2E pipeline test, latency benchmarks, streaming optimization)
    - Phase 4 (tool-use scaffold ready for calendar/reminders integration)

tech_stack:
  added:
    - anthropic==0.84.0  # already in requirements; first active use in conversation.py
    - elevenlabs==2.37.0  # already in requirements; TTSService primary provider
    - edge-tts==7.2.7  # already in requirements; TTSService fallback
    - tenacity>=8.3  # retry logic on ElevenLabs _elevenlabs_synthesize
  patterns:
    - lazy singleton (threading.Lock + _LazyTTSProxy) for TTSService — avoids settings validation at import time
    - asyncio.to_thread for sync ElevenLabs SDK calls — never blocks event loop
    - tenacity @retry(stop_after_attempt=2) for ElevenLabs transient failures
    - sys.modules injection for mock app.config in unit tests — avoids pydantic-settings validation
    - cascade fallback pattern: ElevenLabs -> Edge TTS on any exception
    - _get_client() lazy factory — Anthropic client created on first conversation call

key_files:
  created:
    - velar-backend/app/voice/conversation.py  # Claude loop, VELAR system prompt, tool-use scaffold
    - velar-backend/app/voice/tts.py  # TTSService with ElevenLabs + Edge TTS fallback
    - velar-backend/app/voice/router.py  # /voice and /chat endpoints
    - velar-backend/tests/test_tts.py  # 5 TTS unit tests
    - velar-backend/tests/test_conversation.py  # 5 conversation unit tests
  modified:
    - velar-backend/app/main.py  # voice_router registration, STT model log in lifespan

decisions:
  - "claude-haiku-4-5-20251001 selected for voice — fastest model for voice latency per Phase 2 research"
  - "Tool-use scaffold present as commented code in conversation.py — Phase 4+ adds real tools (calendar, reminders)"
  - "history truncated to last 10 turns max in run_conversation() — Phase 2 is mostly stateless; caller manages state"
  - "ElevenLabs primary, Edge TTS automatic fallback — no explicit flag needed; any exception triggers fallback"
  - "_LazyTTSProxy wraps TTSService as lazy singleton — same pattern as get_stt_service() from 02-01"
  - "Auth endpoint tests skip when SUPABASE_URL absent — same graceful-skip pattern as Whisper model tests"

patterns_established:
  - "Lazy module import for settings inside __init__ methods — prevents pydantic-settings ValidationError at import time"
  - "sys.modules injection for mock app.config — preferred for unit tests that cannot use .env"
  - "Cascade fallback: try primary service, catch any Exception, warn and use fallback — no flag juggling"

requirements_completed: [VOICE-03, VOICE-04]

duration: 6min
completed: "2026-03-02"
---

# Phase 2 Plan 02: Claude Conversation Loop and TTS Service Summary

**Claude Haiku conversation loop with VELAR system prompt, ElevenLabs/Edge-TTS cascade fallback, and two authenticated FastAPI endpoints completing the full voice pipeline.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-02T14:08:21Z
- **Completed:** 2026-03-02T14:14:00Z
- **Tasks:** 2
- **Files modified:** 6 (5 created, 1 updated)

## Accomplishments

- `conversation.py`: VELAR system prompt with language mirroring, Jarvis-inspired persona, concise voice style, and Phase 4+ tool-use scaffold (commented). `run_conversation()` uses claude-haiku-4-5-20251001 via asyncio.to_thread, truncates history to 10 turns, maps anthropic errors to HTTPException 502/503.
- `tts.py`: TTSService with ElevenLabs eleven_flash_v2_5 as primary (75ms latency), Edge TTS (tr-TR-AhmetNeural / en-US-GuyNeural) as automatic fallback. tenacity @retry(2 attempts) on ElevenLabs for transient failures. Lazy singleton via _LazyTTSProxy.
- `router.py`: POST /api/v1/voice (audio upload -> STT -> Claude -> TTS -> MP3 stream with metadata headers) and POST /api/v1/chat (text -> Claude -> TTS -> ChatResponse JSON), both requiring JWT authentication.
- 10 tests (8 pass always, 2 skip without Supabase .env): system prompt validation, mock-Claude wiring, error mapping, TTS creation/synthesis/fallback, auth protection.

## Task Commits

1. **Task 1: Claude conversation loop and TTS service** - `9eee90c` (feat)
2. **Task 2: Voice and chat endpoints, router registration, and tests** - `ea34a4d` (feat)

## Files Created/Modified

- `velar-backend/app/voice/conversation.py` — Claude Haiku loop, VELAR system prompt, tool-use scaffold
- `velar-backend/app/voice/tts.py` — TTSService with ElevenLabs primary and Edge TTS fallback
- `velar-backend/app/voice/router.py` — /voice and /chat authenticated endpoints
- `velar-backend/app/main.py` — voice_router registered at /api/v1; STT config logged in lifespan
- `velar-backend/tests/test_tts.py` — 5 TTS unit tests (all pass without .env)
- `velar-backend/tests/test_conversation.py` — 5 conversation tests (3 always pass, 2 skip without Supabase)

## Decisions Made

- `claude-haiku-4-5-20251001` selected for minimum voice latency; matches research from Phase 2 02-RESEARCH.md.
- Tool-use scaffold is present as commented-out `tools=[...]` block with clear Phase 4+ instructions — avoids passing `tools=[]` which the Anthropic SDK interprets differently from omitting the parameter.
- History is truncated to last 10 turns inside `run_conversation()` to keep Phase 2 mostly stateless; Phase 3/4+ will add persistent session history.
- `_LazyTTSProxy` pattern mirrors `get_stt_service()` from 02-01 — TTSService.__init__ does `from app.config import settings` lazily, so the proxy defers instantiation until first `synthesize()` call.
- Auth endpoint tests use `@pytest.mark.skipif(not SUPABASE_URL)` to skip cleanly — same graceful approach as the Whisper model tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level TTSService() instantiation triggered pydantic-settings ValidationError**
- **Found during:** Task 1 verification (`python -c "from app.voice.tts import TTSService"`)
- **Issue:** Plan specified `tts_service = TTSService()` at module level. TTSService.__init__ does `from app.config import settings` (lazy import), but `app.config` instantiates `Settings()` at its own module level — which requires Supabase env vars. Importing `app.voice.tts` without a `.env` file failed with `ValidationError: 5 validation errors for Settings`.
- **Fix:** Replaced module-level `tts_service = TTSService()` with a `_LazyTTSProxy` class that defers instantiation until first `synthesize()` call. Added `get_tts_service()` lazy singleton factory with double-checked locking. Identical pattern to `get_stt_service()` established in 02-01.
- **Files modified:** `velar-backend/app/voice/tts.py`
- **Verification:** `python -c "from app.voice.tts import TTSService; print('TTS import OK')"` passes without .env.
- **Committed in:** 9eee90c (Task 1 commit)

**2. [Rule 1 - Bug] Test fixture `monkeypatch.setattr(cfg_module.settings, ...)` triggered pydantic-settings ValidationError**
- **Found during:** Task 2 test run (first attempt of test_tts.py and test_conversation.py)
- **Issue:** Tests used `import app.config as cfg_module` to monkeypatch settings. This triggered `Settings()` at import time — same ValidationError, because `app.config` was not yet in `sys.modules`. Tests collecting without .env failed.
- **Fix:** Adopted the `sys.modules` injection pattern: inject a mock `app.config` module (`types.ModuleType + MagicMock`) into `sys.modules["app.config"]` before any import that transitively needs settings. For conversation tests that don't touch settings directly, patch `conv_module._get_client` instead. Auth endpoint tests use `@pytest.mark.skipif(not SUPABASE_URL)`.
- **Files modified:** `velar-backend/tests/test_tts.py`, `velar-backend/tests/test_conversation.py`
- **Verification:** `pytest tests/test_tts.py tests/test_conversation.py -q` → 8 passed, 2 skipped (no .env needed).
- **Committed in:** ea34a4d (Task 2 commit)

**3. [Rule 1 - Bug] STTService.model_size attribute missing — lifespan would raise AttributeError**
- **Found during:** Task 2 (writing main.py lifespan update)
- **Issue:** Plan instructed `logger.info(f"STT service initialized: model={stt.model_size}")` but STTService stores the model in `self.model` (a WhisperModel object), not `self.model_size`. Calling `get_stt_service()` in lifespan would also load the 5-20s Whisper model at startup.
- **Fix:** Replaced the lifespan STT check with a lightweight log of `settings.whisper_model_size` (the configured string) rather than calling `get_stt_service()`. This preserves the intent (logging STT availability) without triggering model load at startup.
- **Files modified:** `velar-backend/app/main.py`
- **Verification:** Lifespan code reads `settings.whisper_model_size` — no AttributeError, no model load at startup.
- **Committed in:** ea34a4d (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (Rule 1 - Bug x3)
**Impact on plan:** All three fixes were necessary for correctness and test-collection reliability. No scope creep. The lazy proxy pattern is now consistent across both voice services (STT and TTS).

## Issues Encountered

None beyond the three auto-fixed deviations above.

## User Setup Required

Two API keys are needed for full functionality:

- `ANTHROPIC_API_KEY` — required for Claude conversation (`run_conversation`). Without it, /voice and /chat return 503. Get from: https://console.anthropic.com/settings/keys
- `ELEVENLABS_API_KEY` — optional. Without it, Edge TTS handles all synthesis automatically (Turkish: tr-TR-AhmetNeural, English: en-US-GuyNeural). For premium TTS: https://elevenlabs.io/app/settings/api-keys

Add both to `velar-backend/.env`.

## Next Phase Readiness

- Full voice round-trip pipeline is wired: STT (Plan 02-01) -> Claude (this plan) -> TTS (this plan) -> API endpoints
- Plan 02-03 can now build end-to-end integration tests, measure latency, and decide on streaming TTS optimization
- Tool-use scaffold in conversation.py is ready for Phase 4 calendar/reminders integration
- ElevenLabs Turkish voice quality should be empirically tested before Phase 3 sign-off

---
*Phase: 02-voice-pipeline*
*Completed: 2026-03-02*
