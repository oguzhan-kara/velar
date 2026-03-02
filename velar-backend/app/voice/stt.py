"""Speech-to-text service using faster-whisper with built-in Silero VAD.

Supports Turkish and English auto-detection. Runs transcription in a thread
pool to avoid blocking FastAPI's async event loop. Uses a threading lock to
prevent concurrent access to a single WhisperModel instance.

Audio format handling:
- WAV, FLAC, OGG: decoded directly via soundfile
- WebM, M4A, MP4, and other browser/phone formats: converted via pydub first

Usage:
    from app.voice.stt import get_stt_service

    stt = get_stt_service()
    result = await stt.transcribe(audio_bytes)
"""

import asyncio
import io
import logging
import threading

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

from app.voice.schemas import STTResult

logger = logging.getLogger(__name__)

# Module-level singleton — populated lazily on first call to get_stt_service()
_stt_service: "STTService | None" = None
_stt_lock = threading.Lock()


class STTService:
    """Wraps faster-whisper for async-safe, thread-safe transcription."""

    def __init__(self, model_size: str = "large-v3-turbo") -> None:
        logger.info("Loading WhisperModel '%s' (cpu, int8) …", model_size)
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self._lock = threading.Lock()
        logger.info("WhisperModel loaded.")

    async def transcribe(self, audio_bytes: bytes) -> STTResult:
        """Transcribe audio bytes asynchronously without blocking the event loop."""
        return await asyncio.to_thread(self._transcribe_sync, audio_bytes)

    def _transcribe_sync(self, audio_bytes: bytes) -> STTResult:
        """Synchronous transcription — called via asyncio.to_thread."""
        audio_array = self._decode_audio(audio_bytes)

        with self._lock:
            segments, info = self.model.transcribe(
                audio_array,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                beam_size=5,
                # language= is intentionally NOT set — let Whisper auto-detect.
                # Forcing "tr" breaks English input and code-switching detection.
            )
            text = " ".join(seg.text.strip() for seg in segments)

        if info.language_probability < 0.8:
            logger.warning(
                "Low language detection confidence: lang=%s prob=%.2f — "
                "utterance may be too short or ambiguous.",
                info.language,
                info.language_probability,
            )

        return STTResult(
            text=text,
            language=info.language,
            language_probability=info.language_probability,
        )

    @staticmethod
    def _decode_audio(audio_bytes: bytes) -> np.ndarray:
        """Decode audio bytes to a float32 numpy array at the original sample rate.

        Tries soundfile first (WAV, FLAC, OGG). Falls back to pydub for formats
        that soundfile cannot handle (WebM, M4A, MP4, etc.).
        """
        buf = io.BytesIO(audio_bytes)
        try:
            data, _ = sf.read(buf, dtype="float32", always_2d=False)
            return data
        except Exception:
            pass  # soundfile failed — try pydub

        try:
            from pydub import AudioSegment  # lazy import — optional dependency

            segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
            wav_buf = io.BytesIO()
            segment.export(wav_buf, format="wav")
            wav_buf.seek(0)
            data, _ = sf.read(wav_buf, dtype="float32", always_2d=False)
            return data
        except Exception as exc:
            raise ValueError(
                "Could not decode audio bytes — unsupported format or corrupted data."
            ) from exc


def get_stt_service() -> STTService:
    """Return the module-level STTService singleton, creating it on first call.

    Lazy initialization prevents the 5-20 second model load from happening at
    import time during tests or app startup before the lifespan hook.
    Settings are imported lazily here (not at module level) so that importing
    this module doesn't trigger config validation — critical for unit tests.
    """
    global _stt_service
    if _stt_service is None:
        with _stt_lock:
            if _stt_service is None:
                from app.config import settings as _settings  # lazy import
                _stt_service = STTService(model_size=_settings.whisper_model_size)
    return _stt_service
