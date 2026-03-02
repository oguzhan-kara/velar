"""TTS service unit tests.

Tests cover:
- TTSService instantiation (pure Edge TTS mode when no API key)
- Edge TTS synthesis for Turkish and English (no API key required)
- Fallback behavior when ElevenLabs key is absent

These tests run without a .env file. Because TTSService.__init__ does a lazy
``from app.config import settings`` import, we inject a mock ``app.config``
module into sys.modules *before* importing TTSService — the same strategy used
by test_voice_stt.py to avoid pydantic-settings validation on Supabase fields.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inject_mock_config(elevenlabs_api_key: str = "") -> MagicMock:
    """Replace app.config in sys.modules with a lightweight mock.

    Returns the mock settings object. Call this at the start of each test
    that needs to avoid pydantic-settings validation.

    The caller is responsible for restoring sys.modules if needed, but since
    pytest runs each test function in a fresh call, the module stays injected
    only for the duration of the process — acceptable for this test file.
    """
    mock_settings = MagicMock()
    mock_settings.elevenlabs_api_key = elevenlabs_api_key

    mock_config_module = types.ModuleType("app.config")
    mock_config_module.settings = mock_settings

    sys.modules["app.config"] = mock_config_module
    return mock_settings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTTSServiceCreation:
    """Verify TTSService instantiates correctly without external API keys."""

    def test_tts_service_creation(self):
        """TTSService in pure Edge TTS mode when ELEVENLABS_API_KEY is absent."""
        _inject_mock_config(elevenlabs_api_key="")

        # Re-import to pick up the fresh mock (or use importlib if already imported)
        from app.voice.tts import TTSService  # noqa: PLC0415

        service = TTSService()
        assert service._elevenlabs is None, (
            "Expected _elevenlabs=None when no API key is provided"
        )

    def test_tts_service_no_elevenlabs_with_mock_settings(self):
        """TTSService sets _elevenlabs=None when elevenlabs_api_key is empty."""
        _inject_mock_config(elevenlabs_api_key="")

        from app.voice.tts import TTSService  # noqa: PLC0415

        service = TTSService()
        assert service._elevenlabs is None


class TestEdgeTTSSynthesize:
    """Integration tests for Edge TTS — free, no API key required."""

    @pytest.mark.asyncio
    async def test_edge_tts_synthesize_turkish(self):
        """Edge TTS returns non-empty MP3-like bytes for Turkish text."""
        _inject_mock_config(elevenlabs_api_key="")

        from app.voice.tts import TTSService  # noqa: PLC0415

        service = TTSService()
        audio = await service._edge_tts_synthesize("Merhaba", "tr")

        assert isinstance(audio, bytes), "Expected bytes"
        assert len(audio) > 0, "Expected non-empty audio"
        # Valid MP3: frames start with 0xFF 0xFB/0xF3/0xF2, or ID3 tag header
        assert (
            audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
            or audio[:3] == b"ID3"
        ), f"Audio does not look like MP3 — first 4 bytes: {audio[:4].hex()}"

    @pytest.mark.asyncio
    async def test_edge_tts_synthesize_english(self):
        """Edge TTS returns non-empty MP3-like bytes for English text."""
        _inject_mock_config(elevenlabs_api_key="")

        from app.voice.tts import TTSService  # noqa: PLC0415

        service = TTSService()
        audio = await service._edge_tts_synthesize("Hello, how are you?", "en")

        assert isinstance(audio, bytes), "Expected bytes"
        assert len(audio) > 0, "Expected non-empty audio"
        assert (
            audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
            or audio[:3] == b"ID3"
        ), f"Audio does not look like MP3 — first 4 bytes: {audio[:4].hex()}"


class TestTTSFallback:
    """Verify fallback behavior when ElevenLabs key is empty."""

    @pytest.mark.asyncio
    async def test_tts_fallback_on_missing_key(self):
        """synthesize() routes directly to Edge TTS when no ElevenLabs key.

        Verifies that _elevenlabs is None and that synthesize() still returns
        non-empty audio bytes by going straight to Edge TTS.
        """
        _inject_mock_config(elevenlabs_api_key="")

        from app.voice.tts import TTSService  # noqa: PLC0415

        service = TTSService()
        assert service._elevenlabs is None, "Expected pure Edge TTS mode"

        audio = await service.synthesize("Merhaba", language="tr")

        assert isinstance(audio, bytes), "Expected bytes from synthesize()"
        assert len(audio) > 0, "Expected non-empty audio from Edge TTS fallback"
