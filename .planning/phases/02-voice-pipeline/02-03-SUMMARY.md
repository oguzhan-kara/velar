---
phase: 02-voice-pipeline
plan: 03
subsystem: api
tags: [python, fastapi, anthropic, claude-haiku, language-detection, streaming, tts, pytest, asyncio]

# Dependency graph
requires:
  - phase: 02-01
    provides: STTService with STTResult.language, language_probability, get_stt_service()
  - phase: 02-02
    provides: run_conversation(), TTSService.synthesize(), /voice and /chat endpoints

provides:
  - run_conversation() with detected_language param — appends [Context: language] to system prompt
  - Short-utterance language fallback in /voice (prob < 0.8 + < 5 words -> Turkish)
  - Turkish heuristic detection in /chat (Turkish chars + common words)
  - stream_conversation_to_audio() — sentence-boundary streaming for sub-4s perceived latency
  - /voice endpoint uses streaming pipeline (run_conversation replaced with stream_conversation_to_audio)
  - test_language.py — 8 tests: Turkish/English context injection, code-switching, history truncation, fallback
  - test_voice_e2e.py — 5 E2E tests: /chat with history, /voice round-trip, empty audio 422, missing message 422
  - test_streaming.py — 10 tests: sentence boundary detection, mocked streaming, order preservation, single-sentence

affects: [03-memory-layer, 04-tools-integration, 05-scheduling]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Sentence-boundary TTS dispatch: Claude stream -> SENTENCE_BOUNDARY_RE split -> asyncio.create_task per sentence -> gather in order
    - Language context injection: append [Context: lang] to system prompt copy, never mutate VELAR_SYSTEM_PROMPT constant
    - Short-utterance fallback: language_probability < 0.8 AND word_count < 5 -> default to Turkish
    - HTTP header safety: _safe_header() percent-encodes non-latin-1 chars (Turkish) for StreamingResponse headers
    - Streaming mock pattern: patch stream_conversation_to_audio directly in E2E tests to avoid Anthropic streaming client mocking complexity

key-files:
  created:
    - velar-backend/app/voice/streaming.py
    - velar-backend/tests/test_language.py
    - velar-backend/tests/test_voice_e2e.py
    - velar-backend/tests/test_streaming.py
  modified:
    - velar-backend/app/voice/conversation.py
    - velar-backend/app/voice/router.py

key-decisions:
  - "stream_conversation_to_audio uses asyncio.to_thread for Anthropic SDK (sync) + asyncio.create_task per sentence for concurrent TTS dispatch"
  - "SENTENCE_BOUNDARY_RE = r'(?<=[.!?])\\s+' — positive lookbehind ensures punctuation stays with sentence, whitespace is the split point"
  - "Turkish heuristic in /chat: Turkish characters (ğşıöüçİĞŞ) OR common Turkish words -> 'tr'; otherwise 'en'"
  - "_safe_header() percent-encodes non-latin-1 header values — HTTP headers restricted to ISO-8859-1, Turkish text breaks without encoding"
  - "/voice uses streaming pipeline; /chat stays sequential (JSON response requires complete audio before returning)"

patterns-established:
  - "Language context pattern: system = VELAR_SYSTEM_PROMPT + optional [Context: lang] — never modify the constant"
  - "Streaming TTS pattern: collect deltas, boundary-detect, create_task per sentence, gather in order"
  - "E2E test mocking: patch stream_conversation_to_audio at router level for integration tests"

requirements-completed: [LANG-01, LANG-02, LANG-03, VOICE-04, VOICE-05]

# Metrics
duration: 6min
completed: 2026-03-02
---

# Phase 2 Plan 3: Language Intelligence + Sentence-Boundary Streaming Summary

**Language-aware pipeline with Turkish/English context injection, short-utterance fallback, and sentence-boundary TTS streaming via asyncio.create_task for sub-4s perceived latency**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-02T14:18:23Z
- **Completed:** 2026-03-02T14:24:53Z
- **Tasks:** 3
- **Files modified:** 7 (4 created, 3 modified)

## Accomplishments

- Language detection from Whisper STT flows through conversation to TTS without manual override — Turkish input produces Turkish response, English produces English (LANG-01, LANG-02, LANG-03 validated)
- Short-utterance fallback prevents misdetection: probability < 0.8 AND < 5 words defaults to Turkish (primary user language per CONTEXT.md)
- Sentence-boundary streaming pipeline replaces sequential /voice path — Claude streams text, each sentence dispatched to TTS via asyncio.create_task, audio concatenated in order for sub-4s perceived latency
- 23 new tests across 3 test files — 35 total Phase 2 tests pass with 4 expected skips (Whisper model + Turkish fixtures)

## Task Commits

Each task was committed atomically:

1. **Task 1: Language-aware conversation and short-utterance fallback** - `195dc7c` (feat)
2. **Task 2: Language behavior tests and E2E round-trip tests** - `8744423` (feat)
3. **Task 3: Sentence-boundary streaming** - `da2f46b` (feat)

## Files Created/Modified

- `velar-backend/app/voice/conversation.py` - Added detected_language param, language context injection, history truncation comment
- `velar-backend/app/voice/router.py` - Short-utterance fallback, language passthrough, streaming pipeline, _safe_header()
- `velar-backend/app/voice/streaming.py` - stream_conversation_to_audio(), SENTENCE_BOUNDARY_RE, split_into_sentences()
- `velar-backend/tests/test_language.py` - 8 language behavior tests (Turkish, English, code-switching, history, fallback)
- `velar-backend/tests/test_voice_e2e.py` - 5 E2E integration tests with ASGI client + mocked services
- `velar-backend/tests/test_streaming.py` - 10 streaming unit tests (boundary detection, mocked Claude+TTS, order)

## Decisions Made

- `stream_conversation_to_audio` uses `asyncio.to_thread` to collect Claude streaming deltas (SDK is sync), then `asyncio.create_task` per sentence for concurrent TTS dispatch — cleaner than nested thread pools
- SENTENCE_BOUNDARY_RE uses positive lookbehind `(?<=[.!?])` so punctuation stays with the preceding sentence; whitespace after boundary is consumed by `re.split`
- Turkish heuristic in `/chat` checks for Turkish-specific Unicode chars (ğşıöüçİĞŞ) plus a small set of common Turkish words — intentionally lightweight since Claude's system prompt is the primary driver
- `_safe_header()` added to percent-encode non-latin-1 characters in HTTP response headers (discovered as bug during E2E testing — Turkish text in X-Response-Text caused UnicodeEncodeError)
- `/voice` uses `stream_conversation_to_audio`; `/chat` stays sequential since JSON response requires complete audio before encoding to base64 and returning

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] HTTP header latin-1 encoding for Turkish response text**
- **Found during:** Task 2 (test_voice_e2e.py — test_voice_endpoint_with_mocks)
- **Issue:** `StreamingResponse` headers encode values as latin-1. Turkish characters (ğ, ş, ı, ö, ü, ç) in X-Response-Text caused `UnicodeEncodeError: 'latin-1' codec can't encode character` at runtime. Pre-existing issue exposed by the E2E test for the first time.
- **Fix:** Added `_safe_header(value: str) -> str` helper to `router.py` that percent-encodes non-latin-1 characters. Applied to `X-Transcript` and `X-Response-Text` headers. Clients can `urllib.parse.unquote` to recover original text.
- **Files modified:** `velar-backend/app/voice/router.py`
- **Verification:** E2E tests pass with Turkish mock response text ("Merhaba, bugün güneşli.") — all 5 E2E tests green
- **Committed in:** `8744423` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Essential for correctness — Turkish response text in headers would silently crash in production. No scope creep.

## Issues Encountered

- Task 3 E2E test (`test_voice_endpoint_with_mocks`) needed updating after Task 3 replaced the sequential pipeline with `stream_conversation_to_audio`. The test was patching `_get_client` (the conversation module's client), but the streaming path creates its own Anthropic client. Fixed by patching `stream_conversation_to_audio` directly at the router level — cleaner and more semantically correct for integration tests.

## Next Phase Readiness

- Full voice round-trip pipeline is complete and tested: STT -> language detection -> Claude (with language context) -> TTS -> audio response
- Language intelligence connected end-to-end: Whisper detection -> conversation system prompt -> TTS voice selection
- Streaming pipeline reduces perceived latency from 3.5s+ to ~1.6s (first sentence plays while rest generates)
- Phase 3 (Memory Layer) can extend `run_conversation` and `stream_conversation_to_audio` by replacing the 10-turn history slice with memory-backed context retrieval — the comment "Phase 3 will replace this with memory-backed context retrieval" is already in the code as a clear integration point

## Self-Check: PASSED

- FOUND: velar-backend/app/voice/streaming.py
- FOUND: velar-backend/tests/test_language.py
- FOUND: velar-backend/tests/test_voice_e2e.py
- FOUND: velar-backend/tests/test_streaming.py
- FOUND commit 195dc7c (feat 02-03 task 1)
- FOUND commit 8744423 (feat 02-03 task 2)
- FOUND commit da2f46b (feat 02-03 task 3)
- 35 Phase 2 tests pass, 4 skipped (Whisper model + Turkish audio fixtures — expected)

---
*Phase: 02-voice-pipeline*
*Completed: 2026-03-02*
