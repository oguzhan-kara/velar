"""Text-to-speech service for VELAR voice pipeline.

Provider selection via TTS_PROVIDER env var:
- "edge"       (default): Use Edge TTS directly — free, no API key required.
- "elevenlabs": Use ElevenLabs primary with Edge TTS automatic fallback.

When TTS_PROVIDER=elevenlabs the fallback chain activates automatically on any
ElevenLabs failure: rate limit, network error, invalid API key, or key not
configured.

Usage:
    from app.voice.tts import tts_service

    audio_bytes = await tts_service.synthesize("Merhaba!", language="tr")
    # audio_bytes is MP3 audio ready for streaming or base64 encoding
"""

import asyncio
import io
import logging

import edge_tts
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Voice / model constants
# ---------------------------------------------------------------------------

# George — male multilingual voice, good Turkish pronunciation.
# Test and replace with best Turkish male voice at phase start.
# Try ElevenLabs Voice Library Turkish male voices for comparison.
ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"

# 75ms first-audio latency, 32 languages including Turkish.
# If Turkish pronunciation is not acceptable, switch to eleven_multilingual_v2
# (higher quality, ~300ms latency).
ELEVENLABS_MODEL = "eleven_flash_v2_5"

# Edge TTS fallback voices — Microsoft Neural, no key required
EDGE_TTS_VOICE_TR = "tr-TR-AhmetNeural"   # Turkish male
EDGE_TTS_VOICE_EN = "en-US-GuyNeural"     # English male


# ---------------------------------------------------------------------------
# TTS Service
# ---------------------------------------------------------------------------

class TTSService:
    """TTS service supporting Edge TTS (free default) and ElevenLabs (paid).

    TTS_PROVIDER=edge (default): Goes straight to Edge TTS, no ElevenLabs init.
    TTS_PROVIDER=elevenlabs: Uses ElevenLabs primary with Edge TTS fallback.

    Instantiation is lightweight: just creates an HTTP client, no model loading.
    Safe to create at module level as a singleton.
    """

    def __init__(self) -> None:
        from app.config import settings  # lazy import — avoid startup validation
        self._tts_provider = getattr(settings, "tts_provider", "edge")

        if self._tts_provider == "elevenlabs" and settings.elevenlabs_api_key:
            try:
                from elevenlabs import ElevenLabs
                self._elevenlabs = ElevenLabs(api_key=settings.elevenlabs_api_key)
                logger.info("ElevenLabs TTS client initialized (TTS_PROVIDER=elevenlabs).")
            except Exception as exc:
                logger.warning("Failed to initialize ElevenLabs client: %s — using Edge TTS only.", exc)
                self._elevenlabs = None
        elif self._tts_provider == "elevenlabs" and not settings.elevenlabs_api_key:
            logger.warning("TTS_PROVIDER=elevenlabs but no ELEVENLABS_API_KEY — using Edge TTS only.")
            self._elevenlabs = None
        else:
            # TTS_PROVIDER=edge (default): skip ElevenLabs entirely
            logger.info("TTS_PROVIDER=%s — using Edge TTS directly.", self._tts_provider)
            self._elevenlabs = None

    async def synthesize(self, text: str, language: str = "tr") -> bytes:
        """Convert text to MP3 audio bytes.

        When TTS_PROVIDER=edge (default): goes straight to Edge TTS.
        When TTS_PROVIDER=elevenlabs: tries ElevenLabs first, falls back to
        Edge TTS on any failure (rate limit, network error, auth error, empty key).

        Args:
            text:     The text to synthesize. Turkish UTF-8 passed as-is.
            language: Language code ("tr" or "en") for fallback voice selection.

        Returns:
            MP3 audio bytes.
        """
        if self._elevenlabs is not None:
            try:
                return await self._elevenlabs_synthesize(text)
            except Exception as exc:
                logger.warning(
                    "ElevenLabs TTS failed (%s) — falling back to Edge TTS.", exc
                )

        return await self._edge_tts_synthesize(text, language)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=0.5, max=2))
    async def _elevenlabs_synthesize(self, text: str) -> bytes:
        """Synthesize via ElevenLabs, with tenacity retry for transient failures.

        Uses asyncio.to_thread because the ElevenLabs SDK is synchronous.
        Collects the generator output (bytes) into a single bytes object.
        """
        def _sync_call() -> bytes:
            audio_generator = self._elevenlabs.text_to_speech.convert(
                voice_id=ELEVENLABS_VOICE_ID,
                text=text,
                model_id=ELEVENLABS_MODEL,
            )
            # .convert() returns a generator of bytes chunks — collect them all
            return b"".join(audio_generator)

        return await asyncio.to_thread(_sync_call)

    async def _edge_tts_synthesize(self, text: str, language: str) -> bytes:
        """Synthesize via Edge TTS (Microsoft Neural voices, natively async).

        Selects voice based on language: Turkish or English.
        Returns MP3 bytes collected from the async audio stream.
        """
        voice = EDGE_TTS_VOICE_TR if language.startswith("tr") else EDGE_TTS_VOICE_EN
        communicate = edge_tts.Communicate(text=text, voice=voice)

        audio_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        return b"".join(audio_chunks)


import threading as _threading

# Module-level singleton — populated lazily on first call to get_tts_service()
# TTSService.__init__ imports settings (which requires Supabase env vars), so we
# cannot instantiate at module level — that would block test collection for unit
# tests that run without a .env file. Same pattern as stt.py / get_stt_service().
_tts_service: "TTSService | None" = None
_tts_lock = _threading.Lock()


def get_tts_service() -> "TTSService":
    """Return the module-level TTSService singleton, creating it on first call."""
    global _tts_service
    if _tts_service is None:
        with _tts_lock:
            if _tts_service is None:
                _tts_service = TTSService()
    return _tts_service


# Convenience alias used by router.py — behaves as a singleton accessor
class _LazyTTSProxy:
    """Proxy that forwards attribute access to the lazily-created TTSService.

    This allows ``from app.voice.tts import tts_service`` followed by
    ``await tts_service.synthesize(...)`` without triggering settings
    validation at import time.
    """

    async def synthesize(self, text: str, language: str = "tr") -> bytes:
        return await get_tts_service().synthesize(text, language)


tts_service = _LazyTTSProxy()
