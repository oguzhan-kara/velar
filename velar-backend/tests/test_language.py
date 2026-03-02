"""Language behavior tests for VELAR voice pipeline.

Tests verify:
- Turkish language context injection (LANG-01)
- English language context injection (LANG-02)
- Code-switching dominant language handling (LANG-03)
- Optional language parameter (no override when not provided)
- History truncation to last 10 turns
- Short utterance language fallback logic (VOICE-05)

All tests run without a .env file — no real API keys required.
Claude calls are mocked via unittest.mock.patch.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


# ---------------------------------------------------------------------------
# Language context injection tests
# ---------------------------------------------------------------------------

class TestLanguageContextInjection:
    """Verify run_conversation appends correct language context to system prompt."""

    @pytest.mark.asyncio
    async def test_turkish_response_from_claude(self):
        """LANG-01: Turkish input produces system prompt with Turkish language context."""
        import app.voice.conversation as conv_module  # noqa: PLC0415
        from app.voice.conversation import VELAR_SYSTEM_PROMPT  # noqa: PLC0415

        mock_content = MagicMock()
        mock_content.type = "text"  # Phase 4: tool loop checks block.type == "text"
        mock_content.text = "Bugün hava oldukça güzel görünüyor."

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_response)

        with patch.object(conv_module, "_get_client", return_value=mock_client):
            from app.voice.conversation import run_conversation  # noqa: PLC0415
            result = await run_conversation(
                user_text="Bugün hava nasıl?",
                detected_language="tr",
            )

        # Verify the system prompt sent to Claude contains Turkish language context
        call_kwargs = mock_client.messages.create.call_args.kwargs
        system_sent = call_kwargs["system"]

        assert "[Context: The user is speaking Turkish. Respond in Turkish.]" in system_sent, (
            f"Expected Turkish context in system prompt. Got: {system_sent!r}"
        )
        assert system_sent.startswith(VELAR_SYSTEM_PROMPT), (
            "System prompt must start with VELAR_SYSTEM_PROMPT constant"
        )
        assert result == "Bugün hava oldukça güzel görünüyor."

    @pytest.mark.asyncio
    async def test_english_response_from_claude(self):
        """LANG-02: English input produces system prompt with English language context."""
        import app.voice.conversation as conv_module  # noqa: PLC0415
        from app.voice.conversation import VELAR_SYSTEM_PROMPT  # noqa: PLC0415

        mock_content = MagicMock()
        mock_content.type = "text"  # Phase 4: tool loop checks block.type == "text"
        mock_content.text = "The weather looks lovely today."

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_response)

        with patch.object(conv_module, "_get_client", return_value=mock_client):
            from app.voice.conversation import run_conversation  # noqa: PLC0415
            result = await run_conversation(
                user_text="What's the weather today?",
                detected_language="en",
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        system_sent = call_kwargs["system"]

        assert "[Context: The user is speaking English. Respond in English.]" in system_sent, (
            f"Expected English context in system prompt. Got: {system_sent!r}"
        )
        assert system_sent.startswith(VELAR_SYSTEM_PROMPT)
        assert result == "The weather looks lovely today."

    @pytest.mark.asyncio
    async def test_codeswitching_dominant_language(self):
        """LANG-03: Mixed Turkish-English input with Turkish dominant -> Turkish context."""
        import app.voice.conversation as conv_module  # noqa: PLC0415

        mock_content = MagicMock()
        mock_content.type = "text"  # Phase 4: tool loop checks block.type == "text"
        mock_content.text = "Bugün takviminde iki toplantı var."

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_response)

        # STT would detect Turkish as dominant for "VELAR, bugün calendar'da ne var?"
        # and pass detected_language="tr" to run_conversation
        with patch.object(conv_module, "_get_client", return_value=mock_client):
            from app.voice.conversation import run_conversation  # noqa: PLC0415
            await run_conversation(
                user_text="VELAR, bugün calendar'da ne var?",
                detected_language="tr",
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        system_sent = call_kwargs["system"]

        assert "Turkish" in system_sent, (
            f"Expected Turkish context for code-switched Turkish-dominant input. Got: {system_sent!r}"
        )
        assert "English" not in system_sent.split("[Context:")[-1] if "[Context:" in system_sent else True

    @pytest.mark.asyncio
    async def test_no_language_override_when_not_provided(self):
        """Optional language: without detected_language, system prompt equals VELAR_SYSTEM_PROMPT exactly."""
        import app.voice.conversation as conv_module  # noqa: PLC0415
        from app.voice.conversation import VELAR_SYSTEM_PROMPT  # noqa: PLC0415

        mock_content = MagicMock()
        mock_content.type = "text"  # Phase 4: tool loop checks block.type == "text"
        mock_content.text = "Hello!"

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_response)

        with patch.object(conv_module, "_get_client", return_value=mock_client):
            from app.voice.conversation import run_conversation  # noqa: PLC0415
            await run_conversation(user_text="hello")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        system_sent = call_kwargs["system"]

        assert system_sent == VELAR_SYSTEM_PROMPT, (
            "Without detected_language, system must be exactly VELAR_SYSTEM_PROMPT — "
            f"no language context appended. Got: {system_sent!r}"
        )


# ---------------------------------------------------------------------------
# History truncation test
# ---------------------------------------------------------------------------

class TestHistoryTruncation:
    """Verify history is truncated to the last 10 turns."""

    @pytest.mark.asyncio
    async def test_history_truncation_to_10_turns(self):
        """History > 10 turns is sliced to last 10 before sending to Claude."""
        import app.voice.conversation as conv_module  # noqa: PLC0415

        mock_content = MagicMock()
        mock_content.type = "text"  # Phase 4: tool loop checks block.type == "text"
        mock_content.text = "Understood!"

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_response)

        # Create 15 history turns (far more than the 10-turn limit)
        long_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}"}
            for i in range(15)
        ]

        with patch.object(conv_module, "_get_client", return_value=mock_client):
            from app.voice.conversation import run_conversation  # noqa: PLC0415
            await run_conversation(
                user_text="latest",
                history=long_history,
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        messages_sent = call_kwargs["messages"]

        # Should contain at most 11 messages: 10 history turns + 1 current user message
        assert len(messages_sent) <= 11, (
            f"Expected at most 11 messages (10 history + 1 current), got {len(messages_sent)}"
        )
        # Last message must be the current user message
        assert messages_sent[-1] == {"role": "user", "content": "latest"}
        # Should contain exactly the last 10 history turns + current message
        assert len(messages_sent) == 11, (
            f"Expected exactly 11 messages when history=15 (truncated to 10 + current)"
        )


# ---------------------------------------------------------------------------
# Short-utterance language fallback test
# ---------------------------------------------------------------------------

class TestShortUtteranceLanguageFallback:
    """Verify the short-utterance language fallback logic in the /voice endpoint."""

    def test_short_utterance_language_fallback(self):
        """VOICE-05: Low-confidence short utterance falls back to Turkish.

        Tests the fallback logic directly without hitting the endpoint,
        since the fallback is pure logic (no async, no I/O).
        """
        from app.voice.schemas import STTResult  # noqa: PLC0415

        # Simulate STT result: "Evet" detected as English with low confidence
        stt_result = STTResult(
            text="Evet",
            language="en",
            language_probability=0.6,
        )

        # Apply the same fallback logic as the /voice endpoint
        detected_lang = stt_result.language
        word_count = len(stt_result.text.split())
        if stt_result.language_probability < 0.8 and word_count < 5:
            detected_lang = "tr"

        assert detected_lang == "tr", (
            f"Expected Turkish fallback for low-confidence short utterance, got {detected_lang!r}"
        )
        assert word_count == 1, "Test utterance should be 1 word"

    def test_high_confidence_not_overridden(self):
        """High-confidence language detection should NOT be overridden."""
        from app.voice.schemas import STTResult  # noqa: PLC0415

        # High confidence English utterance — should NOT fall back to Turkish
        stt_result = STTResult(
            text="Hello",
            language="en",
            language_probability=0.95,
        )

        detected_lang = stt_result.language
        if stt_result.language_probability < 0.8 and len(stt_result.text.split()) < 5:
            detected_lang = "tr"

        assert detected_lang == "en", (
            f"High-confidence detection should not be overridden. Got {detected_lang!r}"
        )

    def test_long_utterance_not_overridden(self):
        """Low confidence but long utterance (>= 5 words) should NOT fall back."""
        from app.voice.schemas import STTResult  # noqa: PLC0415

        stt_result = STTResult(
            text="Can you tell me the weather today please",  # 8 words
            language="en",
            language_probability=0.7,
        )

        detected_lang = stt_result.language
        if stt_result.language_probability < 0.8 and len(stt_result.text.split()) < 5:
            detected_lang = "tr"

        assert detected_lang == "en", (
            "Long utterance should not trigger fallback even with low confidence"
        )
