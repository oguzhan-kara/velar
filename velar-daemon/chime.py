import io
import logging

from pydub import AudioSegment
from pydub.playback import play

logger = logging.getLogger(__name__)


def _make_tone(frequency: int, duration_ms: int, volume_db: float = -20.0) -> AudioSegment:
    """Generate a pure sine wave tone."""
    return AudioSegment.sine(frequency=frequency, duration=duration_ms) + volume_db


def play_chime():
    """200ms metallic chime at 880Hz — confirms wake word detected."""
    try:
        tone = _make_tone(frequency=880, duration_ms=200, volume_db=-15.0)
        play(tone)
    except Exception as exc:
        logger.warning("Chime playback failed: %s", exc)


def play_cancelled():
    """100ms low tone at 440Hz — signals no speech detected, returning to idle."""
    try:
        tone = _make_tone(frequency=440, duration_ms=100, volume_db=-20.0)
        play(tone)
    except Exception as exc:
        logger.warning("Cancelled tone playback failed: %s", exc)


def play_audio_response(mp3_bytes: bytes):
    """Play MP3 audio bytes received from the backend."""
    try:
        audio = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
        play(audio)
    except Exception as exc:
        logger.error("Audio response playback failed: %s", exc)
