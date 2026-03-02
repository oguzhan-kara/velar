---
phase: 02-voice-pipeline
plan: 01
subsystem: voice-stt
tags: [stt, whisper, faster-whisper, voice-pipeline, turkish, wer, pydantic, testing]
requirements: [VOICE-02, VOICE-05]

dependency_graph:
  requires:
    - 01-foundation-01  # config.py, project structure
    - 01-foundation-02  # conftest.py test infrastructure
  provides:
    - STTService async transcribe() with threading lock and VAD
    - Pydantic schemas for entire voice pipeline (STTResult, ChatRequest, ChatResponse, VoiceMetadata)
    - Phase 2 API key config fields (anthropic_api_key, elevenlabs_api_key, whisper_model_size)
    - Turkish WER acceptance test scaffold ready for audio fixtures
  affects:
    - 02-02 (uses STTService and schemas)
    - 02-03 (uses schemas and config keys)

tech_stack:
  added:
    - faster-whisper==1.2.1  # WhisperModel with built-in Silero VAD
    - anthropic==0.84.0      # Claude conversation (Phase 2 later plans)
    - elevenlabs==2.37.0     # TTS (Phase 2 later plans)
    - edge-tts==7.2.7        # Fallback TTS
    - soundfile>=0.12        # WAV/FLAC/OGG decoding
    - pydub>=0.25            # WebM/M4A/MP4 fallback conversion
    - tenacity>=8.3          # Retry logic
    - python-multipart>=0.0.9 # File upload support
    - editdistance>=0.6      # WER computation in acceptance tests
  patterns:
    - lazy singleton (double-checked locking) for WhisperModel
    - asyncio.to_thread for non-blocking CPU-bound inference
    - threading.Lock per instance for concurrent access safety
    - lazy settings import in get_stt_service() — avoids startup cost at import time
    - conftest lazy fixture import — unit tests run without .env file

key_files:
  created:
    - velar-backend/app/voice/__init__.py
    - velar-backend/app/voice/stt.py
    - velar-backend/app/voice/schemas.py
    - velar-backend/tests/test_voice_stt.py
    - velar-backend/tests/fixtures/turkish_audio/.gitkeep
  modified:
    - velar-backend/app/config.py  # anthropic_api_key, elevenlabs_api_key, whisper_model_size
    - velar-backend/requirements.txt  # Phase 2 voice pipeline dependencies
    - velar-backend/.env.example  # Phase 2 API key placeholders
    - velar-backend/tests/conftest.py  # lazy app import fix

decisions:
  - "device=cpu, compute_type=int8 selected for WhisperModel — Mac/Windows compatible, no CUDA dependency"
  - "language= parameter NOT set in model.transcribe() — auto-detection handles Turkish/English code-switching (VOICE-05)"
  - "anthropic_api_key and elevenlabs_api_key default to empty string — app starts without voice keys, only voice endpoints fail"
  - "get_stt_service() lazy singleton prevents 5-20s model load at import time — critical for test collection"
  - "conftest.py lazy app import fix applied — voice unit tests run without .env, no Supabase credentials needed"

metrics:
  duration_minutes: 5
  completed_date: "2026-03-02"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 4
---

# Phase 2 Plan 01: STT Service Summary

**One-liner:** faster-whisper large-v3-turbo STT service with async threading, built-in Silero VAD, pydub format fallback, and Turkish WER acceptance test scaffold using editdistance.

## What Was Built

### STTService (`app/voice/stt.py`)

The core speech-to-text component for the VELAR voice pipeline:

- `STTService` class wraps `faster-whisper.WhisperModel` with `device="cpu"`, `compute_type="int8"` for cross-platform compatibility
- `async transcribe(audio_bytes: bytes) -> STTResult` dispatches work via `asyncio.to_thread` — never blocks FastAPI's event loop
- `_transcribe_sync` uses a `threading.Lock` to prevent concurrent WhisperModel access corruption
- `vad_filter=True` with `min_silence_duration_ms=500` trims silence via built-in Silero VAD
- Language auto-detection (no forced `language=` param) supports Turkish, English, and code-switching
- Audio format handling: soundfile for WAV/FLAC/OGG, pydub fallback for WebM/M4A/MP4
- `get_stt_service()` lazy singleton with double-checked locking — model loads only on first call

### Voice Pipeline Schemas (`app/voice/schemas.py`)

Shared Pydantic models consumed by all three plans in Phase 2:

- `STTResult` — text, language code, language_probability
- `ChatRequest` — validated message (min=1, max=4000 chars), optional history, optional language override
- `ChatResponse` — text, audio_base64 (MP3), detected_language
- `VoiceMetadata` — transcript, response_text, detected_language

### Config Updates (`app/config.py`)

Three new Settings fields with safe defaults (app starts without them; only voice endpoints fail):
- `anthropic_api_key: str = ""`
- `elevenlabs_api_key: str = ""`
- `whisper_model_size: str = "large-v3-turbo"`

### Test Suite (`tests/test_voice_stt.py`)

6 tests — 4 fast (always pass), 2 conditional (skip gracefully):

| Test | Type | Status |
|------|------|--------|
| `test_stt_service_creation` | unit | always runs |
| `test_stt_result_schema` | unit | always runs |
| `test_chat_request_validation` | unit | always runs |
| `test_audio_format_conversion` | unit | always runs |
| `test_language_detection_returns_valid_code` | slow | skips unless `WHISPER_MODEL_AVAILABLE=true` |
| `test_turkish_stt_wer` | acceptance | skips unless audio fixtures present |

Turkish WER acceptance test targets < 15% avg WER across 5 reference utterances.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lazy settings import in STTService module**
- **Found during:** Task 1 verification
- **Issue:** `from app.config import settings` at module level caused pydantic-settings validation at import time. Since `Settings` has 5 required fields (no defaults), importing `app.voice.stt` without a `.env` file raised `ValidationError` — blocking test collection for unit tests that don't need real credentials.
- **Fix:** Moved `from app.config import settings` into `get_stt_service()` body (lazy import). Module import now succeeds without env vars; config validation only occurs when the singleton is actually created.
- **Files modified:** `velar-backend/app/voice/stt.py`
- **Commit:** dd81030

**2. [Rule 1 - Bug] conftest.py eager app import blocked voice unit test collection**
- **Found during:** Task 2 test run
- **Issue:** `from app.main import app` at module level in `conftest.py` triggered `settings = Settings()` during pytest collection — even for tests that never use the `client` fixture. Running `pytest tests/test_voice_stt.py` failed with `ValidationError` unless Supabase env vars were set.
- **Fix:** Moved `from app.main import app` inside the `client` fixture body (lazy import). The fixture now only loads the app when actually requested. Voice unit tests run without any `.env` file.
- **Files modified:** `velar-backend/tests/conftest.py`
- **Commit:** 4415524

## Self-Check: PASSED

All created files found on disk. All task commits verified in git history.

| Check | Result |
|-------|--------|
| `velar-backend/app/voice/stt.py` | FOUND |
| `velar-backend/app/voice/schemas.py` | FOUND |
| `velar-backend/app/voice/__init__.py` | FOUND |
| `velar-backend/tests/test_voice_stt.py` | FOUND |
| `velar-backend/tests/fixtures/turkish_audio/.gitkeep` | FOUND |
| Commit dd81030 (Task 1) | FOUND |
| Commit 4415524 (Task 2) | FOUND |
