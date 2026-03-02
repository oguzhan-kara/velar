"""Unit tests for sentence-boundary streaming module.

Tests cover:
- Sentence boundary detection (split_into_sentences helper)
- stream_conversation_to_audio with mocked Claude and TTS
- Sentence order preservation in concatenated audio
- Single-sentence graceful degradation

All tests run without a .env file — no real API keys required.
Both Claude streaming and TTS are mocked.
"""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper — mock config injection (same pattern as test_tts.py)
# ---------------------------------------------------------------------------

def _inject_mock_config() -> None:
    """Inject minimal app.config mock to avoid pydantic-settings validation."""
    mock_settings = MagicMock()
    mock_settings.anthropic_api_key = "test-key"
    mock_settings.elevenlabs_api_key = ""

    mock_config_module = types.ModuleType("app.config")
    mock_config_module.settings = mock_settings
    sys.modules["app.config"] = mock_config_module


# Inject once at module import time — streaming.py imports settings at call time,
# but the module-level import of VELAR_SYSTEM_PROMPT triggers conversation.py import.
_inject_mock_config()


# ---------------------------------------------------------------------------
# Test 1: Sentence boundary detection
# ---------------------------------------------------------------------------

class TestSentenceBoundaryDetection:
    """Unit tests for the split_into_sentences helper."""

    def test_two_sentences_period(self):
        """'Hello. World.' splits into two sentences."""
        from app.voice.streaming import split_into_sentences  # noqa: PLC0415

        result = split_into_sentences("Hello. World.")
        assert result == ["Hello.", "World."], f"Unexpected: {result}"

    def test_two_sentences_mixed_punctuation(self):
        """'Merhaba! Nasılsın?' splits on exclamation and question marks."""
        from app.voice.streaming import split_into_sentences  # noqa: PLC0415

        result = split_into_sentences("Merhaba! Nasılsın?")
        assert result == ["Merhaba!", "Nasılsın?"], f"Unexpected: {result}"

    def test_single_sentence_no_boundary(self):
        """Text without sentence boundary returns as single item."""
        from app.voice.streaming import split_into_sentences  # noqa: PLC0415

        result = split_into_sentences("One sentence only")
        assert result == ["One sentence only"], f"Unexpected: {result}"

    def test_three_sentences(self):
        """Three-sentence text splits into three items."""
        from app.voice.streaming import split_into_sentences  # noqa: PLC0415

        result = split_into_sentences("First. Second. Third.")
        assert result == ["First.", "Second.", "Third."], f"Unexpected: {result}"

    def test_empty_string(self):
        """Empty string returns empty list."""
        from app.voice.streaming import split_into_sentences  # noqa: PLC0415

        result = split_into_sentences("")
        assert result == [], f"Unexpected: {result}"

    def test_sentence_with_trailing_space(self):
        """Trailing space after last sentence is handled gracefully."""
        from app.voice.streaming import split_into_sentences  # noqa: PLC0415

        result = split_into_sentences("Hello. ")
        # After stripping, result should be a single sentence
        assert "Hello." in result


# ---------------------------------------------------------------------------
# Test 2: stream_conversation_to_audio — mocked Claude + TTS
# ---------------------------------------------------------------------------

class TestStreamConversationToAudio:
    """Tests for stream_conversation_to_audio with all external calls mocked."""

    @pytest.mark.asyncio
    async def test_stream_conversation_to_audio_mocked(self):
        """Mocked streaming: two sentences -> two TTS calls -> tuple returned."""
        _inject_mock_config()

        import app.voice.streaming as streaming_module  # noqa: PLC0415

        # Mock TTS synthesize
        call_count = [0]
        async def mock_synthesize(text: str, language: str = "tr") -> bytes:
            call_count[0] += 1
            return f"audio-for-{call_count[0]}".encode()

        # Mock Claude streaming: "Hello. How are you?" as character-by-character deltas
        full_text_to_stream = "Hello. How are you?"
        deltas = list(full_text_to_stream)  # Character-by-character

        mock_stream_context = MagicMock()
        mock_stream_context.__enter__ = MagicMock(return_value=mock_stream_context)
        mock_stream_context.__exit__ = MagicMock(return_value=False)
        mock_stream_context.text_stream = iter(deltas)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=mock_stream_context)

        with (
            patch("anthropic.Anthropic", return_value=mock_client),
            patch.object(streaming_module.tts_service, "synthesize", side_effect=mock_synthesize),
        ):
            from app.voice.streaming import stream_conversation_to_audio  # noqa: PLC0415
            result_text, result_audio = await stream_conversation_to_audio(
                user_text="Hello, how are you?",
                language="en",
                detected_language="en",
            )

        # Verify full text is returned
        assert result_text == full_text_to_stream, (
            f"Expected full text {full_text_to_stream!r}, got {result_text!r}"
        )
        # Verify two TTS calls were made (one per sentence)
        assert call_count[0] == 2, (
            f"Expected 2 TTS calls for 2 sentences, got {call_count[0]}"
        )
        # Verify audio is non-empty
        assert len(result_audio) > 0, "Expected non-empty audio bytes"

    @pytest.mark.asyncio
    async def test_streaming_preserves_sentence_order(self):
        """TTS audio chunks are concatenated in sentence order."""
        _inject_mock_config()

        import app.voice.streaming as streaming_module  # noqa: PLC0415

        # Return distinct bytes per sentence so order is verifiable
        sentence_counter = [0]
        async def mock_synthesize(text: str, language: str = "tr") -> bytes:
            sentence_counter[0] += 1
            return f"audio-{sentence_counter[0]}".encode()

        # Two-sentence response
        deltas = list("First. Second.")

        mock_stream_context = MagicMock()
        mock_stream_context.__enter__ = MagicMock(return_value=mock_stream_context)
        mock_stream_context.__exit__ = MagicMock(return_value=False)
        mock_stream_context.text_stream = iter(deltas)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=mock_stream_context)

        with (
            patch("anthropic.Anthropic", return_value=mock_client),
            patch.object(streaming_module.tts_service, "synthesize", side_effect=mock_synthesize),
        ):
            from app.voice.streaming import stream_conversation_to_audio  # noqa: PLC0415
            _, result_audio = await stream_conversation_to_audio(
                user_text="test",
                language="tr",
            )

        # "audio-1" for "First." must come before "audio-2" for "Second."
        assert result_audio == b"audio-1audio-2", (
            f"Expected b'audio-1audio-2' (order preserved), got {result_audio!r}"
        )

    @pytest.mark.asyncio
    async def test_streaming_single_sentence_fallback(self):
        """Single-sentence response with no boundary dispatches as one TTS call."""
        _inject_mock_config()

        import app.voice.streaming as streaming_module  # noqa: PLC0415

        tts_call_count = [0]
        async def mock_synthesize(text: str, language: str = "tr") -> bytes:
            tts_call_count[0] += 1
            return b"single-audio"

        # No sentence boundary — entire text goes as one TTS call (remainder)
        deltas = list("Just a fragment")

        mock_stream_context = MagicMock()
        mock_stream_context.__enter__ = MagicMock(return_value=mock_stream_context)
        mock_stream_context.__exit__ = MagicMock(return_value=False)
        mock_stream_context.text_stream = iter(deltas)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=mock_stream_context)

        with (
            patch("anthropic.Anthropic", return_value=mock_client),
            patch.object(streaming_module.tts_service, "synthesize", side_effect=mock_synthesize),
        ):
            from app.voice.streaming import stream_conversation_to_audio  # noqa: PLC0415
            result_text, result_audio = await stream_conversation_to_audio(
                user_text="test",
                language="tr",
            )

        assert result_text == "Just a fragment"
        assert tts_call_count[0] == 1, (
            f"Single sentence should produce exactly 1 TTS call, got {tts_call_count[0]}"
        )
        assert result_audio == b"single-audio"

    @pytest.mark.asyncio
    async def test_language_context_in_streaming(self):
        """stream_conversation_to_audio appends language context to system prompt."""
        _inject_mock_config()

        import app.voice.streaming as streaming_module  # noqa: PLC0415
        from app.voice.conversation import VELAR_SYSTEM_PROMPT  # noqa: PLC0415

        captured_system = []

        def capture_stream(**kwargs):
            captured_system.append(kwargs.get("system", ""))
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_ctx.text_stream = iter(["Merhaba."])
            return mock_ctx

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(side_effect=capture_stream)

        async def mock_synthesize(text: str, language: str = "tr") -> bytes:
            return b"audio"

        with (
            patch("anthropic.Anthropic", return_value=mock_client),
            patch.object(streaming_module.tts_service, "synthesize", side_effect=mock_synthesize),
        ):
            from app.voice.streaming import stream_conversation_to_audio  # noqa: PLC0415
            await stream_conversation_to_audio(
                user_text="Merhaba",
                language="tr",
                detected_language="tr",
            )

        assert len(captured_system) == 1
        system_sent = captured_system[0]
        assert "[Context: The user is speaking Turkish. Respond in Turkish.]" in system_sent, (
            f"Expected Turkish context in streaming system prompt. Got: {system_sent!r}"
        )
        assert system_sent.startswith(VELAR_SYSTEM_PROMPT)
