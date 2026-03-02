"""Claude conversation loop unit tests.

Tests cover:
- VELAR system prompt content validation
- Error handling when Anthropic API key is missing/invalid
- Correct wiring when Claude is mocked (no real API calls)
- Authentication required on /voice and /chat endpoints

These tests run without a .env file. Tests that need settings (e.g., the
auth endpoint tests via the 'client' fixture) load app.main lazily through
conftest.py, which requires a valid .env — those tests are skipped when the
.env is absent via the conftest lazy import mechanism.

Tests that do NOT use the 'client' fixture never touch app.config and run
freely without any environment variables.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestVelarSystemPrompt:
    """Verify VELAR_SYSTEM_PROMPT contains the required content."""

    def test_velar_system_prompt_content(self):
        """System prompt must reference VELAR, language mirroring, conciseness."""
        from app.voice.conversation import VELAR_SYSTEM_PROMPT  # noqa: PLC0415

        prompt_lower = VELAR_SYSTEM_PROMPT.lower()

        assert "velar" in prompt_lower, "Prompt must identify assistant as VELAR"
        assert "same language" in prompt_lower, (
            "Prompt must instruct language mirroring ('same language')"
        )
        assert "concise" in prompt_lower or "1-3 sentence" in prompt_lower, (
            "Prompt must emphasize conciseness for voice responses"
        )
        assert "emoji" in prompt_lower, (
            "Prompt must explicitly forbid emoji in voice responses"
        )


class TestRunConversationErrors:
    """Verify run_conversation raises correct HTTP exceptions on API failures."""

    @pytest.mark.asyncio
    async def test_run_conversation_requires_api_key(self):
        """AuthenticationError from Anthropic is mapped to HTTPException(503)."""
        import anthropic
        from fastapi import HTTPException

        import app.voice.conversation as conv_module  # noqa: PLC0415

        # Reset the cached client so our mock is used
        original_client = conv_module._client
        conv_module._client = None

        try:
            # Inject a mock _get_client that returns a client whose .messages.create
            # raises AuthenticationError — simulating missing/invalid API key
            mock_client = MagicMock()
            mock_client.messages.create = MagicMock(
                side_effect=anthropic.AuthenticationError(
                    message="Invalid API key",
                    response=MagicMock(status_code=401, headers={}),
                    body={"error": {"message": "Invalid API key", "type": "authentication_error"}},
                )
            )

            # Call _run_anthropic_conversation directly — this is what the test exercises.
            # run_conversation() now dispatches to Gemini by default; _run_anthropic_conversation
            # is the internal Anthropic path that maps AuthenticationError -> HTTPException(503).
            with patch.object(conv_module, "_get_client", return_value=mock_client):
                with pytest.raises(HTTPException) as exc_info:
                    await conv_module._run_anthropic_conversation(user_text="test input")

            assert exc_info.value.status_code == 503
            assert "api key" in exc_info.value.detail.lower()
        finally:
            conv_module._client = original_client

    @pytest.mark.asyncio
    async def test_conversation_with_mock_claude(self):
        """run_conversation returns the text from Claude's response content."""
        import app.voice.conversation as conv_module  # noqa: PLC0415

        # Build a mock response matching the Anthropic SDK structure.
        # Phase 4: must set block.type = "text" explicitly — the tool loop checks
        # block.type == "text" to extract the response text. MagicMock().type
        # returns a new MagicMock (not "text"), causing the loop to return "".
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "Merhaba! Size nasıl yardımcı olabilirim?"

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_response)

        # Call _run_anthropic_conversation directly to test the Anthropic path
        # (run_conversation dispatches based on LLM_PROVIDER setting)
        with patch.object(conv_module, "_get_client", return_value=mock_client):
            result = await conv_module._run_anthropic_conversation(
                user_text="Merhaba",
                history=[],
            )

        assert result == "Merhaba! Size nasıl yardımcı olabilirim?"
        # Verify messages.create was called with the correct model
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs.get("model") == "claude-haiku-4-5-20251001"


import os as _os

# Integration tests that need a running app with Supabase credentials.
# Skip gracefully when .env is not present (same pattern as test_voice_stt.py).
_SUPABASE_URL_SET = bool(_os.environ.get("SUPABASE_URL", ""))


class TestVoiceEndpointAuth:
    """Verify voice and chat endpoints return 401/403 without authentication.

    These tests use the 'client' fixture from conftest.py, which lazily imports
    app.main (requiring valid .env / Supabase credentials). They are skipped
    when Supabase credentials are not available in the environment.
    """

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not _SUPABASE_URL_SET,
        reason="Set SUPABASE_URL (and other Supabase vars) in .env to run integration tests",
    )
    async def test_chat_endpoint_returns_401_without_auth(self, client):
        """POST /api/v1/chat without Authorization header returns 401 or 403."""
        response = await client.post(
            "/api/v1/chat",
            json={"message": "hello"},
        )
        assert response.status_code in (401, 403), (
            f"Expected 401/403, got {response.status_code}"
        )

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not _SUPABASE_URL_SET,
        reason="Set SUPABASE_URL (and other Supabase vars) in .env to run integration tests",
    )
    async def test_voice_endpoint_returns_401_without_auth(self, client):
        """POST /api/v1/voice without Authorization header returns 401 or 403."""
        # Send a minimal fake audio file (empty bytes — auth check happens first)
        response = await client.post(
            "/api/v1/voice",
            files={"audio": ("test.wav", b"fake audio", "audio/wav")},
        )
        assert response.status_code in (401, 403), (
            f"Expected 401/403, got {response.status_code}"
        )
