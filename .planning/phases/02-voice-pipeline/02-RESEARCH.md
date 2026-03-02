# Phase 2: Voice Pipeline - Research

**Researched:** 2026-03-02
**Domain:** Speech-to-text (faster-whisper), LLM conversation loop (Claude API), Text-to-speech (ElevenLabs + Edge TTS), bilingual Turkish/English handling, FastAPI audio endpoints
**Confidence:** HIGH (core stack verified via official docs and PyPI; Turkish STT quality MEDIUM; ElevenLabs Turkish quality MEDIUM)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Input Modes**
- Both voice and text input supported from day one
- Voice input via faster-whisper STT (local, best Turkish accuracy per research)
- Text input via API endpoint — same Claude tool loop, just skips STT
- Input mode is transparent to the Claude conversation layer — it receives text either way

**Voice Character**
- Male voice — VELAR is a male-persona assistant (Jarvis reference)
- Warm, confident, slightly formal but not stiff — think concierge, not robot
- ElevenLabs as primary TTS provider — select a premium multilingual voice that handles both Turkish and English naturally
- Edge TTS as fallback when ElevenLabs is unavailable or rate-limited
- Single consistent voice across languages (no voice switching between Turkish and English)

**Conversation Flow**
- Request-response model in Phase 2 (not continuous conversation — that's the daemon's job in Phase 4)
- API endpoint receives audio blob or text → STT (if audio) → Claude → TTS → return audio + text
- No wake word in this phase — direct API invocation (wake word is Phase 4)
- Voice Activity Detection (VAD) on the STT side to trim silence and detect end-of-speech
- Streaming TTS response where possible to reduce perceived latency (start speaking before full response is generated)

**Response Style**
- Concise by default — 1-3 sentences for simple questions
- Longer when the topic demands it, but always conversational, never lecture-style
- VELAR has personality: warm, slightly witty, anticipatory
- Responses are optimized for listening — short sentences, natural pauses, no jargon dumps
- Text responses can be slightly longer/more detailed than spoken responses

**Language Behavior**
- VELAR mirrors the user's language — speak Turkish, get Turkish back; speak English, get English back
- Code-switching handled gracefully: dominant language of the sentence wins
- No explicit language toggle needed — automatic detection per utterance
- Turkish STT target: WER under 15% on common assistant commands
- System prompt instructs Claude to be naturally bilingual, not translating but thinking in both languages

**Latency Targets**
- Full voice round-trip (speak → hear response) under 4 seconds perceived latency
- STT processing: target under 1 second for typical utterances
- Claude response: streaming, first token under 500ms
- TTS: streaming playback, first audio chunk before full text is ready

### Claude's Discretion
- Exact faster-whisper model size (tiny/base/small/medium/large-v3/large-v3-turbo)
- VAD implementation details (silero-vad or webrtcvad)
- ElevenLabs voice ID selection from available multilingual voices
- Audio format and encoding choices (opus, wav, mp3)
- Exact API endpoint design for voice/text input
- Error handling for STT failures, TTS failures, Claude timeouts
- Conversation context window management (how many turns to keep)

### Deferred Ideas (OUT OF SCOPE)
- Wake word detection ("Hey VELAR") — Phase 4 (Mac Daemon)
- Continuous listening / always-on microphone — Phase 4
- Tool use (calendar, weather, etc.) — Phases 4-5 (scaffold only here)
- Conversation memory / context persistence — Phase 3 (Memory System)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VOICE-01 | User can activate VELAR with wake word on Mac | Deferred to Phase 4 — pipeline built here IS what wake word triggers |
| VOICE-02 | User can speak naturally and VELAR understands via Whisper STT | faster-whisper 1.2.1 + large-v3-turbo model; built-in Silero VAD; Turkish language code "tr" |
| VOICE-03 | VELAR responds with premium natural voice via ElevenLabs/Edge TTS | ElevenLabs SDK v2.37.0; eleven_multilingual_v2 or eleven_turbo_v2_5 models; Turkish confirmed supported |
| VOICE-04 | User can have hands-free voice conversation | Full round-trip endpoint: audio in → STT → Claude → TTS → audio out; streaming reduces perceived latency |
| VOICE-05 | User can mix Turkish and English in a single sentence | Whisper handles code-switched audio natively; Claude handles bilingual text natively; system prompt instructs language mirroring |
| LANG-01 | VELAR understands and responds in Turkish | faster-whisper large-v3-turbo; Claude handles Turkish natively; ElevenLabs Multilingual v2 supports Turkish |
| LANG-02 | VELAR understands and responds in English | Default Whisper capability; Claude native English |
| LANG-03 | VELAR handles code-switching (Turkish-English mixed sentences) | Whisper detects dominant language automatically; Claude system prompt handles mixed response |
</phase_requirements>

---

## Summary

Phase 2 builds a three-stage audio pipeline: speech-to-text (faster-whisper), reasoning (Claude API), and text-to-speech (ElevenLabs primary / Edge TTS fallback). The FastAPI backend from Phase 1 gains two new endpoints: `POST /api/v1/voice` (accepts audio blob) and `POST /api/v1/chat` (accepts text). Both endpoints funnel into the same Claude conversation loop and produce the same TTS audio output. The pipeline must achieve under 4 seconds perceived latency from speech end to first audio output.

The critical insight on latency: the 4-second target is achievable through streaming at every stage. Whisper processes in ~500ms-1s for typical utterances; Claude streams its response starting within ~200-300ms of receiving input; ElevenLabs' Flash v2.5 model achieves 75ms first-audio latency and supports streaming. The pipeline should never wait for a complete response before starting TTS — use sentence-boundary streaming: accumulate Claude's text stream until a sentence boundary is detected, then dispatch each sentence to TTS in parallel.

Turkish language handling is not a separate concern — it falls out of choosing the right model at each stage. faster-whisper with large-v3-turbo handles Turkish STT accurately. Claude handles Turkish natively in its training. ElevenLabs Multilingual v2 explicitly supports Turkish. The key design decision is the system prompt: Claude must be instructed to mirror the language of the user's input, not translate it. Code-switching (mixed Turkish-English sentences) is handled by Whisper detecting the dominant language and Claude continuing in that language.

**Primary recommendation:** Use faster-whisper 1.2.1 with large-v3-turbo model + built-in VAD; Claude Haiku 4.5 for voice responses (fastest latency); ElevenLabs SDK 2.37.0 with eleven_multilingual_v2 or eleven_flash_v2_5 for streaming TTS; implement sentence-boundary streaming to hit the 4-second target.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| faster-whisper | 1.2.1 | Local speech-to-text with Turkish support | 4-8x faster than openai-whisper; built-in Silero VAD; supports large-v3-turbo; Turkish WER best in class for local models |
| anthropic | 0.84.0 | Claude API client with streaming and tool-use scaffold | Official SDK; Haiku 4.5 for voice latency; streaming text allows sentence-boundary TTS dispatch |
| elevenlabs | 2.37.0 | Premium TTS with Turkish support | eleven_multilingual_v2 supports Turkish; Flash v2.5 achieves 75ms first-audio latency; streaming SDK |
| edge-tts | 7.2.7 | Free TTS fallback | Microsoft Edge neural voices; tr-TR-AhmetNeural for Turkish male voice; no API key needed |
| numpy | >=1.26 | Audio array processing | Required by faster-whisper; Whisper works on numpy float32 arrays |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| soundfile | >=0.12 | Read/write audio files (WAV) | Convert uploaded audio bytes to numpy array for Whisper |
| pydub | >=0.25 | Audio format conversion | If client sends MP4/WebM; convert to WAV/PCM before Whisper |
| tenacity | >=8.3 | Retry logic with exponential backoff | Wrap ElevenLabs API calls; handle rate limits gracefully |
| httpx | >=0.27 | Already in Phase 1 | Async HTTP for ElevenLabs if SDK doesn't support async streams natively |
| python-multipart | >=0.0.9 | FastAPI file upload support | Required for `UploadFile` to work in FastAPI endpoints |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| faster-whisper large-v3-turbo | large-v3 (full) | large-v3 has marginally better accuracy but is 6x slower; turbo hits the 1s STT target; prefer turbo |
| faster-whisper large-v3-turbo | medium or small | medium/small are faster but Turkish WER degrades significantly; below 15% WER requires turbo at minimum |
| Claude Haiku 4.5 | Claude Sonnet 4.6 | Sonnet is more capable but adds 300-500ms; for 1-3 sentence voice responses, Haiku quality is sufficient; use Sonnet for complex queries |
| ElevenLabs eleven_flash_v2_5 | eleven_multilingual_v2 | Flash has 75ms latency (vs ~300ms for multilingual_v2) but may have lower naturalness; test both |
| Edge TTS tr-TR-AhmetNeural | Azure Cognitive Services | Azure is higher quality but requires API key; Edge TTS is unofficial but free and works; use as fallback only |

**Installation:**
```bash
pip install faster-whisper==1.2.1 anthropic==0.84.0 elevenlabs==2.37.0 edge-tts==7.2.7 numpy soundfile pydub tenacity python-multipart
```

---

## Architecture Patterns

### Recommended Project Structure
```
velar-backend/
├── app/
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── router.py        # POST /api/v1/voice, POST /api/v1/chat
│   │   ├── schemas.py       # VoiceRequest, ChatRequest, VoiceResponse schemas
│   │   ├── stt.py           # STT service: faster-whisper model wrapper
│   │   ├── tts.py           # TTS service: ElevenLabs + Edge TTS fallback
│   │   └── conversation.py  # Claude conversation loop (tool-use scaffold)
│   ├── main.py              # Add voice router
│   └── config.py            # Add ANTHROPIC_API_KEY, ELEVENLABS_API_KEY
├── tests/
│   ├── test_voice.py        # STT acceptance tests: Turkish WER
│   ├── test_tts.py          # TTS output: audio bytes returned, non-empty
│   └── test_conversation.py # Claude loop: text in → text out
```

### Pattern 1: faster-whisper STT Service
**What:** Load WhisperModel once at startup (model init is slow), reuse for all transcriptions. Run in thread pool to avoid blocking FastAPI's async event loop.
**When to use:** Every voice endpoint call.
**Example:**
```python
# Source: https://github.com/SYSTRAN/faster-whisper (README)
# app/voice/stt.py

from faster_whisper import WhisperModel
import asyncio
import numpy as np
import soundfile as sf
import io

class STTService:
    def __init__(self, model_size: str = "large-v3-turbo"):
        # Load once at startup — this takes 5-20 seconds
        # device="cpu" works on Mac without CUDA; compute_type="int8" reduces memory
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    async def transcribe(self, audio_bytes: bytes) -> dict:
        """Transcribe audio bytes to text. Non-blocking via thread pool."""
        return await asyncio.to_thread(self._transcribe_sync, audio_bytes)

    def _transcribe_sync(self, audio_bytes: bytes) -> dict:
        # Decode audio to numpy float32 array
        audio_buffer = io.BytesIO(audio_bytes)
        audio_array, sample_rate = sf.read(audio_buffer, dtype="float32")

        # Transcribe with built-in Silero VAD
        segments, info = self.model.transcribe(
            audio_array,
            vad_filter=True,                  # Built-in Silero VAD — strips silence
            vad_parameters=dict(
                min_silence_duration_ms=500,  # End-of-speech after 500ms silence
            ),
            beam_size=5,
            # Do NOT force language — let Whisper detect Turkish vs English automatically
            # language="tr"  ← only if you want to force Turkish
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return {
            "text": text,
            "language": info.language,        # "tr" or "en"
            "language_probability": info.language_probability,
        }

# Singleton — created at app startup
stt_service = STTService(model_size="large-v3-turbo")
```

### Pattern 2: Claude Conversation Loop (Tool-Use Scaffold)
**What:** Stateless request-response loop. Each call receives full conversation history (Phase 3 will add memory retrieval). Tool-use loop scaffold: detect `stop_reason == "tool_use"` and handle tools, but Phase 2 has no tools yet — the loop runs one turn.
**When to use:** Both voice and text endpoints — input mode is invisible to this layer.
**Example:**
```python
# Source: https://platform.claude.com/docs/en/api/messages (verified 2026-03-02)
# app/voice/conversation.py

import anthropic
from app.config import settings

VELAR_SYSTEM_PROMPT = """You are VELAR, a proactive personal AI assistant.
You are male, with a warm, confident, slightly formal personality — like a skilled concierge, not a robot.

Language rules (critical):
- Always respond in the SAME language the user spoke. If they spoke Turkish, respond in Turkish. If English, respond in English.
- If the user mixes Turkish and English (code-switching), respond in the dominant language of their message.
- Do not translate. Think in whichever language the user used.

Voice response style:
- Keep responses concise: 1-3 sentences for simple questions.
- Speak naturally — short sentences, conversational rhythm, no jargon.
- You can be slightly witty and anticipatory ("By the way...", "I noticed...").
"""

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

async def run_conversation(user_text: str, history: list[dict] | None = None) -> str:
    """
    Send user_text to Claude and return response text.
    history: list of {"role": "user"|"assistant", "content": str} — prior turns.
    Phase 2: no tools. Returns text response only.
    """
    import asyncio

    messages = (history or []) + [{"role": "user", "content": user_text}]

    # Run in thread pool — anthropic SDK is sync
    response = await asyncio.to_thread(
        client.messages.create,
        model="claude-haiku-4-5-20251001",   # Fastest model for voice responses
        max_tokens=512,                         # Short for voice; longer for text mode
        system=VELAR_SYSTEM_PROMPT,
        messages=messages,
        # Tool-use scaffold: tools=[] here; Phase 4+ adds real tools
    )

    # Phase 2: no tool_use stop_reason expected — simple end_turn
    return response.content[0].text
```

### Pattern 3: ElevenLabs TTS with Edge TTS Fallback
**What:** Abstract TTS behind a single interface. ElevenLabs primary (premium quality); Edge TTS fallback (free, offline-capable). Single voice per language (no switching).
**When to use:** After Claude produces response text.
**Example:**
```python
# Source: https://github.com/elevenlabs/elevenlabs-python (verified v2.37.0)
# Source: https://github.com/rany2/edge-tts (verified v7.2.7)
# app/voice/tts.py

from elevenlabs.client import ElevenLabs
import edge_tts
import asyncio
import io
from app.config import settings

# ElevenLabs voice ID — male, multilingual, natural
# Recommendation: "George" (JBFqnCBsd6RMkjVDRZzb) or test available male Turkish voices
# Use eleven_flash_v2_5 for lowest latency; eleven_multilingual_v2 for highest quality
ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # Verify and replace at phase start
ELEVENLABS_MODEL = "eleven_flash_v2_5"          # 75ms first-audio latency; 32 languages incl. Turkish

# Edge TTS fallback: Turkish Istanbul accent male voice
EDGE_TTS_VOICE_TR = "tr-TR-AhmetNeural"
EDGE_TTS_VOICE_EN = "en-US-GuyNeural"


class TTSService:
    def __init__(self):
        self.elevenlabs = ElevenLabs(api_key=settings.elevenlabs_api_key)

    async def synthesize(self, text: str, language: str = "tr") -> bytes:
        """Synthesize text to audio. Returns MP3 bytes. Falls back to Edge TTS on error."""
        try:
            return await self._elevenlabs_synthesize(text)
        except Exception as e:
            # Fallback to Edge TTS on any ElevenLabs error (rate limit, network, etc.)
            return await self._edge_tts_synthesize(text, language)

    async def _elevenlabs_synthesize(self, text: str) -> bytes:
        audio_stream = await asyncio.to_thread(
            self.elevenlabs.text_to_speech.stream,
            text=text,
            voice_id=ELEVENLABS_VOICE_ID,
            model_id=ELEVENLABS_MODEL,
        )
        # Collect streaming chunks into bytes
        audio_bytes = io.BytesIO()
        for chunk in audio_stream:
            if isinstance(chunk, bytes):
                audio_bytes.write(chunk)
        return audio_bytes.getvalue()

    async def _edge_tts_synthesize(self, text: str, language: str) -> bytes:
        voice = EDGE_TTS_VOICE_TR if language == "tr" else EDGE_TTS_VOICE_EN
        communicate = edge_tts.Communicate(text=text, voice=voice)
        audio_bytes = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.write(chunk["data"])
        return audio_bytes.getvalue()

tts_service = TTSService()
```

### Pattern 4: Voice Endpoint — Full Round-Trip
**What:** Single FastAPI endpoint that accepts audio file upload, runs STT → Claude → TTS pipeline, returns audio bytes + transcript metadata.
**When to use:** Voice input from any client.
**Example:**
```python
# Source: FastAPI docs — https://fastapi.tiangolo.com/advanced/custom-response/
# app/voice/router.py

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import io
from app.dependencies import get_current_user
from app.voice.stt import stt_service
from app.voice.tts import tts_service
from app.voice.conversation import run_conversation
from app.voice.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/voice")
async def voice_endpoint(
    audio: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Accept audio file, return audio response.
    Pipeline: audio → STT → Claude → TTS → MP3 bytes
    """
    audio_bytes = await audio.read()

    # 1. STT
    try:
        stt_result = await stt_service.transcribe(audio_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"STT failed: {str(e)}")

    if not stt_result["text"].strip():
        raise HTTPException(status_code=422, detail="No speech detected in audio")

    # 2. Claude
    response_text = await run_conversation(
        user_text=stt_result["text"],
        history=[],  # Phase 2: stateless; Phase 3 adds memory retrieval here
    )

    # 3. TTS
    audio_response = await tts_service.synthesize(
        text=response_text,
        language=stt_result["language"],
    )

    # Return audio with metadata in headers
    return StreamingResponse(
        io.BytesIO(audio_response),
        media_type="audio/mpeg",
        headers={
            "X-Transcript": stt_result["text"],
            "X-Response-Text": response_text,
            "X-Detected-Language": stt_result["language"],
        },
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Text-only input. Returns text + TTS audio base64.
    Same Claude loop as /voice, just skips STT.
    """
    response_text = await run_conversation(
        user_text=request.message,
        history=request.history or [],
    )

    # TTS for text mode too (language detected from input or passed explicitly)
    audio_response = await tts_service.synthesize(
        text=response_text,
        language=request.language or "tr",
    )

    import base64
    return ChatResponse(
        text=response_text,
        audio_base64=base64.b64encode(audio_response).decode(),
        detected_language=request.language or "tr",
    )
```

### Pattern 5: System Startup — Warm the STT Model
**What:** faster-whisper model loading takes 5-20 seconds. Do it in the FastAPI lifespan, not on first request (which would cause a timeout from the caller).
**When to use:** App startup.
**Example:**
```python
# app/main.py — update lifespan

from app.voice.stt import stt_service  # Import triggers model load

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This import ensures the WhisperModel is loaded at startup
    # faster-whisper loads the model file (several hundred MB) on first instantiation
    logger.info(f"STT model loaded: {stt_service.model.model_size_or_path}")
    yield
```

### Anti-Patterns to Avoid
- **Loading WhisperModel per request:** Model init takes 5-20 seconds. Load once at startup, reuse as a singleton. Never instantiate in a route handler.
- **Calling sync whisper.transcribe() from async route without thread pool:** Blocks FastAPI's event loop for 1-3 seconds during transcription, freezing all other requests.
- **Forcing language="tr" in Whisper:** This breaks English input and code-switching detection. Let Whisper auto-detect. Only force language if auto-detect accuracy is poor (it rarely is with large-v3-turbo).
- **Waiting for complete Claude response before sending to TTS:** Adds the full Claude generation time to perceived latency. Use sentence-boundary streaming for sub-4s round-trips.
- **Returning raw audio without metadata headers:** Callers need the transcript and response text. Include them in headers or a wrapper response.
- **Using large-v3 (full) over large-v3-turbo:** Full large-v3 is 6x slower with <1% accuracy improvement. For voice assistant use (short utterances), turbo always wins on latency without meaningful quality loss.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Voice activity detection | Custom silence detection | faster-whisper built-in VAD (Silero VAD v6) | Dual-threshold algorithm; handles background noise; < 1ms per 30ms chunk |
| Audio format handling | Custom decoder | soundfile + pydub | Format negotiation (WAV, MP4, WebM, OGG) has edge cases; soundfile handles most; pydub fills the gap |
| Turkish language routing | Manual language detection | Whisper's automatic language detection | Whisper already identifies language with probability score; trust it |
| Retry logic for ElevenLabs | Custom backoff loops | tenacity `@retry` decorator | Exponential backoff, jitter, max attempts — ElevenLabs returns 429 rate limits |
| Streaming audio buffer | Custom byte accumulation | `io.BytesIO` with generator | Simple, correct, and zero-dependency |

**Key insight:** The three-stage pipeline (Whisper → Claude → ElevenLabs) has well-established Python SDKs for each stage. The complexity is in wiring them together correctly (threading model, streaming, fallbacks), not in any single stage.

---

## Common Pitfalls

### Pitfall 1: WhisperModel Not Thread-Safe Under Concurrent Load
**What goes wrong:** If two requests arrive simultaneously and both try to use the same WhisperModel instance, transcription outputs can corrupt.
**Why it happens:** CTranslate2 backend is not designed for concurrent use of a single model instance.
**How to avoid:** Use `asyncio.to_thread()` with a threading lock around the model, OR pre-warm a small pool (2 model instances). For a personal assistant, concurrent requests are rare — a single instance with a lock is sufficient.
**Warning signs:** Garbled or truncated transcriptions under load.

### Pitfall 2: Audio Format Mismatch
**What goes wrong:** Client sends WebM/OGG (browser MediaRecorder default) or M4A (iPhone default); soundfile fails to read it.
**Why it happens:** Whisper expects WAV/PCM; browsers and iPhones record in compressed formats.
**How to avoid:** At the STT endpoint, detect audio format from Content-Type header or magic bytes. If not WAV/PCM, convert via pydub: `AudioSegment.from_file(io.BytesIO(audio_bytes)).export(format="wav")`.
**Warning signs:** `soundfile.SoundFileError: Error opening` in logs.

### Pitfall 3: ElevenLabs Rate Limits Breaking the Voice Loop
**What goes wrong:** ElevenLabs free tier has 10,000 chars/month; paid tiers have per-minute rate limits. When limit is hit, TTS returns 429 and VELAR goes silent.
**Why it happens:** No fallback implemented, or fallback not tested.
**How to avoid:** Always implement the Edge TTS fallback in the same code path. Test it manually by temporarily disabling the ElevenLabs API key. The `try/except` in Pattern 3 must be in the synthesize() method, not the caller.
**Warning signs:** 429 errors in logs with no audio returned to client.

### Pitfall 4: Perceived Latency Exceeds 4s Due to Sequential Pipeline
**What goes wrong:** STT finishes (1s), Claude generates full response (1.5s), TTS converts full text (1s) = 3.5s + network = 4.5s+ perceived.
**Why it happens:** Naive pipeline waits for each stage to complete before starting the next.
**How to avoid:** Stream Claude output. When Claude returns a complete sentence (detected by `.`, `!`, `?`), immediately send that sentence to TTS while Claude continues generating. The user hears the first sentence while the rest is being processed. This reduces perceived latency to: STT (1s) + Claude first sentence (300ms) + TTS first sentence (75-300ms) = ~1.5-1.6s perceived.
**Warning signs:** Consistent 3-5 second delays even with fast network.

### Pitfall 5: Turkish Characters Breaking Audio Responses
**What goes wrong:** Turkish characters (ğ, ş, ı, ö, ü, ç) in TTS input cause encoding errors or mispronunciation in some TTS backends.
**Why it happens:** Edge TTS SSML encoding issues; some text normalization strips diacritics.
**How to avoid:** Pass text to TTS as UTF-8 without normalization. ElevenLabs handles Turkish Unicode natively. For Edge TTS, verify tr-TR-AhmetNeural pronounces Turkish diacritics correctly at acceptance test time.
**Warning signs:** Missing or garbled syllables in Turkish audio output.

### Pitfall 6: STT Language Auto-Detection Failures on Short Utterances
**What goes wrong:** For very short utterances (1-3 words), Whisper's language detection is unreliable. A Turkish word like "Evet" might be detected as another language.
**Why it happens:** Language detection requires enough audio context. Short utterances are ambiguous.
**How to avoid:** If `info.language_probability < 0.8`, use the previous turn's detected language, or default to Turkish (primary user language). Add a fallback: `detected_lang = info.language if info.language_probability > 0.8 else last_detected_lang`.
**Warning signs:** Wrong-language responses on short one-word inputs.

---

## Code Examples

Verified patterns from official sources:

### faster-whisper: Transcribe with Built-in VAD
```python
# Source: https://github.com/SYSTRAN/faster-whisper (README, verified 2026-03-02)

from faster_whisper import WhisperModel

model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")

# Auto-detect language; VAD trims silence; beam_size=5 for accuracy
segments, info = model.transcribe(
    "audio.wav",
    beam_size=5,
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500),
)

print(f"Detected language: {info.language} ({info.language_probability:.2f})")
for segment in segments:
    print(f"[{segment.start:.2f}s → {segment.end:.2f}s] {segment.text}")
```

### ElevenLabs: Streaming TTS to Bytes
```python
# Source: https://github.com/elevenlabs/elevenlabs-python (v2.37.0, verified 2026-03-02)

from elevenlabs.client import ElevenLabs
import io

client = ElevenLabs(api_key="YOUR_KEY")

audio_stream = client.text_to_speech.stream(
    text="Merhaba, ben VELAR. Size nasıl yardımcı olabilirim?",
    voice_id="JBFqnCBsd6RMkjVDRZzb",
    model_id="eleven_flash_v2_5",     # 75ms latency, 32 languages including Turkish
)

buffer = io.BytesIO()
for chunk in audio_stream:
    if isinstance(chunk, bytes):
        buffer.write(chunk)
audio_bytes = buffer.getvalue()
```

### Edge TTS: Turkish Fallback
```python
# Source: https://github.com/rany2/edge-tts (v7.2.7, verified 2026-03-02)
import asyncio
import edge_tts
import io

async def synthesize_turkish_fallback(text: str) -> bytes:
    communicate = edge_tts.Communicate(text=text, voice="tr-TR-AhmetNeural")
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    return buffer.getvalue()
```

### Claude: Streaming Conversation with Language Mirroring
```python
# Source: https://platform.claude.com/docs/en/api/messages (verified 2026-03-02)
import anthropic

client = anthropic.Anthropic(api_key="YOUR_KEY")

# Current models (as of 2026-03-02):
# - claude-haiku-4-5-20251001  : Fastest, lowest cost — recommended for voice
# - claude-sonnet-4-6           : Balanced — use for complex queries
# - claude-opus-4-6             : Most powerful — not for voice latency

response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=256,
    system="""You are VELAR. Respond in the same language the user spoke.
Turkish input → Turkish response. English input → English response.
Keep responses to 1-3 concise sentences optimized for listening.""",
    messages=[
        {"role": "user", "content": "Bugün hava nasıl?"}
    ],
)
print(response.content[0].text)
# Expected: Turkish response
```

### FastAPI: Audio Upload Endpoint
```python
# Source: https://fastapi.tiangolo.com/advanced/custom-response/ (verified 2026-03-02)
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
import io

router = APIRouter()

@router.post("/voice")
async def voice(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    # STT → Claude → TTS (see Pattern 4 above for full implementation)
    response_audio = b"..."  # TTS output
    return StreamingResponse(
        io.BytesIO(response_audio),
        media_type="audio/mpeg",
        headers={"X-Transcript": "...", "X-Response-Text": "..."},
    )
```

### Turkish WER Acceptance Test (pytest pattern)
```python
# tests/test_voice.py
import pytest
import io
from app.voice.stt import STTService

# 50 reference utterances for Turkish WER test would be in a fixture file
# Minimum viable: test WER on 5 core commands

TURKISH_TEST_CASES = [
    ("saat kaç", "saat kaç"),          # Simple time query
    ("bugün hava nasıl", "bugün hava nasıl"),
    ("takvimde ne var", "takvimde ne var"),
    ("hatırlatıcı kur", "hatırlatıcı kur"),
    ("müzik çal", "müzik çal"),
]

def word_error_rate(reference: str, hypothesis: str) -> float:
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()
    # Simple WER: Levenshtein on word level
    import editdistance
    distance = editdistance.eval(ref_words, hyp_words)
    return distance / len(ref_words) if ref_words else 0.0

@pytest.mark.skipif(
    not os.path.exists("tests/fixtures/turkish_audio/"),
    reason="Turkish audio fixtures not yet generated"
)
async def test_turkish_stt_wer():
    """Turkish WER must be under 15% on common assistant commands."""
    stt = STTService(model_size="large-v3-turbo")
    total_wer = 0.0
    for audio_path, reference in TURKISH_TEST_CASES:
        with open(f"tests/fixtures/turkish_audio/{audio_path}.wav", "rb") as f:
            result = await stt.transcribe(f.read())
        wer = word_error_rate(reference, result["text"])
        total_wer += wer
    avg_wer = total_wer / len(TURKISH_TEST_CASES)
    assert avg_wer < 0.15, f"Turkish WER {avg_wer:.1%} exceeds 15% target"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| openai-whisper (original) | faster-whisper 1.2.1 (CTranslate2) | 2023 | 4-8x speed improvement; same model quality; now standard |
| Whisper large-v3 (full) | large-v3-turbo (pruned, 4 decoder layers) | Oct 2024 | 6x speed vs large-v3; <1% WER degradation; standard for real-time voice |
| Sequential STT→LLM→TTS pipeline | Sentence-boundary streaming | 2024-2025 | Reduces perceived latency from 3-5s to <2s |
| ElevenLabs Multilingual v2 (only option) | Flash v2.5 (75ms latency) | 2024 | Flash v2.5 achieves 75ms first-audio; preferred for voice assistants |
| Blocking anthropic client in async | asyncio.to_thread() wrapper | — | Required for FastAPI non-blocking; anthropic SDK 0.84.0 is sync-only for messages |
| Claude 3.5 Haiku | Claude Haiku 4.5 (claude-haiku-4-5-20251001) | Oct 2025 | Current fastest model; 200K context; 64K output; $1/$5 per MTok |

**Deprecated/outdated:**
- `openai-whisper`: Still works but 4-8x slower than faster-whisper on same hardware. No reason to use.
- `claude-3-haiku-20240307`: Deprecated; retirement April 19, 2026. Use `claude-haiku-4-5-20251001`.
- `eleven_monolingual_v1`: English-only; replaced by multilingual models. Do not use for VELAR.
- `webrtcvad`: older VAD library; superseded by Silero VAD built into faster-whisper. No need to add separately.

---

## Open Questions

1. **ElevenLabs voice selection for Turkish male voice**
   - What we know: ElevenLabs has Turkish voices (Istanbul accent available); eleven_flash_v2_5 supports Turkish; "George" (JBFqnCBsd6RMkjVDRZzb) is a verified male English voice that may handle Turkish via multilingual model
   - What's unclear: Which specific voice ID sounds best for Turkish in a male Jarvis-style character — cannot determine this without audible testing
   - Recommendation: At Phase 2 start, test 2-3 available male multilingual voices with Turkish text. The Eleven v3 model supports 70+ languages — try that model too. ElevenLabs "Voice Library" has dedicated Turkish male voices; evaluate those first.

2. **eleven_flash_v2_5 vs eleven_multilingual_v2 Turkish quality tradeoff**
   - What we know: Flash achieves 75ms latency (vs ~300ms for multilingual_v2); Flash supports 32 languages including Turkish
   - What's unclear: Whether Flash's Turkish pronunciation quality is acceptable for VELAR's "premium voice" requirement
   - Recommendation: Test Flash first (latency wins if quality is acceptable); fall back to multilingual_v2 if Turkish sounds robotic.

3. **Whisper large-v3-turbo Turkish WER empirical verification**
   - What we know: large-v3-turbo is fine-tuned for Turkish on Common Voice 17.0 (selimc/whisper-large-v3-turbo-turkish exists as specialized model); OpenAI's large-v3-turbo has strong multilingual coverage; WER benchmarks are English-focused
   - What's unclear: Exact WER on VELAR-specific Turkish assistant commands (calendar queries, time, weather in Turkish); whether standard large-v3-turbo hits the 15% target or if a Turkish fine-tuned variant is needed
   - Recommendation: Build the acceptance test (test_turkish_stt_wer) in Wave 0; run it with standard large-v3-turbo first; if WER > 15%, evaluate selimc/whisper-large-v3-turbo-turkish fine-tuned model as drop-in replacement.

4. **iPhone audio format for Phase 6**
   - What we know: Phase 2 builds the backend pipeline; iPhone Flutter app comes in Phase 6
   - What's unclear: What audio format iPhone Flutter will send (M4A/AAC from `record` package is default)
   - Recommendation: Design the endpoint to accept any format and convert via pydub; document the expected Content-Type in the endpoint schema for Phase 6 implementation.

5. **Conversation history management without Phase 3 memory**
   - What we know: Phase 2 is stateless; Phase 3 adds memory; Phase 2 context window must be managed manually
   - What's unclear: How many history turns the API should accept per request; whether the caller or backend truncates
   - Recommendation: Phase 2 — accept up to 10 history turns from the caller (caller manages state); each turn is max 512 tokens; truncate oldest turns if approaching Claude's 200K context limit (not a real risk for Phase 2).

---

## Validation Architecture

> `workflow.nyquist_validation` is not set in config.json — no validation section required. Standard pytest suite applies.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0 + pytest-asyncio 0.23 (already in Phase 1) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` asyncio_mode = "auto" |
| Quick run command | `pytest tests/test_voice.py tests/test_tts.py tests/test_conversation.py -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VOICE-02 | STT transcribes Turkish accurately | acceptance (WER) | `pytest tests/test_voice.py::test_turkish_stt_wer -x` | Wave 0 |
| VOICE-02 | STT returns non-empty text for speech audio | unit | `pytest tests/test_voice.py::test_stt_returns_text -x` | Wave 0 |
| VOICE-03 | TTS returns non-empty audio bytes | unit | `pytest tests/test_tts.py::test_tts_returns_audio -x` | Wave 0 |
| VOICE-03 | Edge TTS fallback works when ElevenLabs key disabled | unit | `pytest tests/test_tts.py::test_tts_fallback -x` | Wave 0 |
| VOICE-04 | /voice endpoint: audio in → audio out, status 200 | integration | `pytest tests/test_voice.py::test_voice_endpoint_round_trip -x` | Wave 0 |
| VOICE-04 | Round-trip wall-clock time < 6s (CI budget; 4s is prod target) | integration | `pytest tests/test_voice.py::test_voice_latency -x` | Wave 0 |
| VOICE-05 | STT detects language for mixed Turkish-English input | unit | `pytest tests/test_voice.py::test_language_detection -x` | Wave 0 |
| LANG-01 | Claude responds in Turkish when input is Turkish | integration | `pytest tests/test_conversation.py::test_turkish_response -x` | Wave 0 |
| LANG-02 | Claude responds in English when input is English | integration | `pytest tests/test_conversation.py::test_english_response -x` | Wave 0 |
| LANG-03 | Claude responds in dominant language for mixed input | integration | `pytest tests/test_conversation.py::test_codeswitching -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_voice.py tests/test_tts.py tests/test_conversation.py -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before phase completion

### Wave 0 Gaps
- [ ] `tests/test_voice.py` — covers VOICE-02, VOICE-04, VOICE-05
- [ ] `tests/test_tts.py` — covers VOICE-03
- [ ] `tests/test_conversation.py` — covers LANG-01, LANG-02, LANG-03
- [ ] `tests/fixtures/turkish_audio/` — WAV audio fixtures for Turkish WER test (generate with TTS or record real speech)
- [ ] `pip install editdistance` — needed for WER calculation in acceptance test

---

## Sources

### Primary (HIGH confidence)
- https://github.com/SYSTRAN/faster-whisper — version 1.2.1 (released Oct 2025); WhisperModel API; built-in VAD parameters; language code support
- https://platform.claude.com/docs/en/about-claude/models/overview — Claude model names/IDs verified: claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-6 (fetched 2026-03-02)
- https://platform.claude.com/docs/en/api/messages — conversation loop, tool_use stop_reason, streaming API (fetched 2026-03-02)
- https://github.com/elevenlabs/elevenlabs-python — version 2.37.0 (released Feb 27, 2026); text_to_speech.stream() API; model IDs
- https://pypi.org/project/edge-tts/ — version 7.2.7 (released Dec 2025); tr-TR-AhmetNeural voice

### Secondary (MEDIUM confidence)
- https://elevenlabs.io/docs/overview/capabilities/text-to-speech — eleven_flash_v2_5 75ms latency; 32 languages; Turkish confirmed supported
- https://elevenlabs.io/text-to-speech/turkish — Turkish voice availability; Istanbul accent variant exists
- Whisper large-v3-turbo Turkish benchmark: selimc/whisper-large-v3-turbo-turkish exists on Hugging Face (Common Voice 17.0 fine-tune) — validates Turkish WER concern; standard turbo model should be tested first
- Latency benchmarks: Introl.com/blog (2025) — STT 100-500ms + LLM 300ms-1s + TTS 75-200ms = achievable under 4s with streaming

### Tertiary (LOW confidence — flag for validation)
- ElevenLabs Flash v2.5 Turkish naturalness: Quality vs multilingual_v2 unverified; empirical test required at Phase 2 start
- Concurrent WhisperModel thread safety: Documented as concern in community; not in official docs; single-instance + lock recommended until tested

---

## Metadata

**Confidence breakdown:**
- Standard stack (faster-whisper, anthropic, elevenlabs, edge-tts): HIGH — versions verified via PyPI and official docs; APIs verified via official docs and GitHub READMEs
- Architecture patterns (thread pool, sentence streaming, fallback): HIGH — patterns are standard Python async practice; verified against FastAPI docs
- Turkish STT quality: MEDIUM — large-v3-turbo covers Turkish strongly; exact WER on assistant commands not benchmarked; acceptance test will confirm
- ElevenLabs Turkish voice quality: MEDIUM — Turkish confirmed supported by ElevenLabs; exact voice quality requires empirical test
- Latency estimates: MEDIUM — based on published benchmarks (75ms ElevenLabs Flash, 500ms Whisper turbo); actual production numbers depend on hardware and network

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (ElevenLabs releases frequently; faster-whisper model ecosystem evolving; re-verify voice IDs and model names before Phase 2 planning if more than 4 weeks elapse)
