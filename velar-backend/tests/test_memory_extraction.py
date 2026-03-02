"""Tests for app/memory/extraction.py and app/memory/service.py.

Tests: background extraction, empty extraction for small-talk,
contradiction detection (supersede trigger), store_extracted_facts background task.
All tests use mocked Claude and mocked DB — no real API keys or Supabase connection.
"""

import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Config mock injection — must be called before any app imports that pull
# app.config (e.g. app.database, app.memory.service).
# Uses force-set (not setdefault) to override any incomplete mock from prior tests.
# ---------------------------------------------------------------------------

def _inject_full_mock_config() -> MagicMock:
    """Inject a complete mock app.config with all fields needed for app.database.

    Called before each lazy import of app.memory.service / app.database to ensure
    database_url is a real string (not a MagicMock sub-attribute from another test).
    This matches the pattern used in test_voice_e2e.py.
    """
    mock_settings = MagicMock()
    mock_settings.supabase_url = "https://test.supabase.co"
    mock_settings.supabase_anon_key = "test-anon-key"
    mock_settings.supabase_service_role_key = "test-service-role-key"
    mock_settings.supabase_jwt_secret = "test-jwt-secret-that-is-long-enough-for-hs256"
    mock_settings.database_url = "postgresql+asyncpg://test:test@localhost/test"
    mock_settings.anthropic_api_key = "sk-ant-test-mock"
    mock_settings.openai_api_key = "sk-test-mock"
    mock_settings.elevenlabs_api_key = ""
    mock_settings.whisper_model_size = "large-v3-turbo"
    mock_settings.environment = "test"
    mock_settings.debug = False

    mock_config_module = types.ModuleType("app.config")
    mock_config_module.settings = mock_settings
    sys.modules["app.config"] = mock_config_module
    return mock_settings


# Note: _inject_full_mock_config() is NOT called at module level here.
# It is called lazily inside each test that needs app.database imported.
# This prevents the module-level injection from interfering with test_auth.py's
# conftest client fixture which needs the real pydantic-settings validation error.


# ---------------------------------------------------------------------------
# Tests: extract_facts_from_conversation
# ---------------------------------------------------------------------------

class TestExtractFactsFromConversation:
    """extract_facts_from_conversation must call Claude and return structured facts."""

    @pytest.mark.asyncio
    async def test_extracts_health_fact(self):
        """Fact with category, key, value, confidence is returned."""
        _inject_full_mock_config()
        from app.memory.extraction import extract_facts_from_conversation

        expected_facts = [
            {"category": "health", "key": "nut_allergy", "value": "true", "confidence": 0.85}
        ]
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"facts": ' + str(expected_facts).replace("'", '"') + '}')]

        with patch("app.memory.extraction.anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_cls.return_value = mock_client

            result = await extract_facts_from_conversation(
                user_message="Fıstık alerjim var.",
                assistant_response="Anlıyorum, bunu not ettim.",
            )

        assert len(result) == 1
        assert result[0]["category"] == "health"
        assert result[0]["key"] == "nut_allergy"

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_small_talk(self):
        """No facts extracted from generic small talk."""
        _inject_full_mock_config()
        from app.memory.extraction import extract_facts_from_conversation

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"facts": []}')]

        with patch("app.memory.extraction.anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_cls.return_value = mock_client

            result = await extract_facts_from_conversation(
                user_message="Merhaba, nasılsın?",
                assistant_response="İyiyim, teşekkür ederim!",
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_api_failure(self):
        """API failure returns [] — never raises."""
        _inject_full_mock_config()
        from app.memory.extraction import extract_facts_from_conversation

        with patch("app.memory.extraction.anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("Connection timeout")
            mock_anthropic_cls.return_value = mock_client

            result = await extract_facts_from_conversation(
                user_message="Any message",
                assistant_response="Any response",
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_skips_extraction_when_no_api_key(self):
        """Returns [] immediately if anthropic_api_key is empty."""
        settings = _inject_full_mock_config()
        from app.memory.extraction import extract_facts_from_conversation

        # Temporarily override the mock settings to have empty key
        original_key = settings.anthropic_api_key
        settings.anthropic_api_key = ""
        # Also update the module-level settings reference
        sys.modules["app.config"].settings.anthropic_api_key = ""

        try:
            result = await extract_facts_from_conversation(
                user_message="I am allergic to nuts",
                assistant_response="Noted!",
            )
            assert result == []
        finally:
            settings.anthropic_api_key = original_key
            sys.modules["app.config"].settings.anthropic_api_key = original_key


# ---------------------------------------------------------------------------
# Tests: store_extracted_facts (background task)
# ---------------------------------------------------------------------------

class TestStoreExtractedFacts:
    """store_extracted_facts must create its own DB session (not request-scoped)."""

    @pytest.mark.asyncio
    async def test_stores_extracted_facts_in_new_session(self):
        """Background task uses async_session_factory, not Depends(get_db)."""
        _inject_full_mock_config()
        from app.memory import service as memory_service

        extracted = [
            {"category": "health", "key": "allergy", "value": "nuts", "confidence": 0.85}
        ]

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("app.memory.extraction.extract_facts_from_conversation", return_value=extracted), \
             patch("app.memory.service.async_session_factory", return_value=mock_ctx), \
             patch("app.memory.service.store_fact", new_callable=AsyncMock) as mock_store:

            await memory_service.store_extracted_facts(
                user_message="I'm allergic to nuts",
                assistant_response="I'll remember that.",
                user_id=str(uuid.uuid4()),
            )

        # store_fact must be called once for the extracted fact
        mock_store.assert_called_once()
        call_kwargs = mock_store.call_args
        assert call_kwargs.kwargs["category"] == "health"
        assert call_kwargs.kwargs["source"] == "conversation"

    @pytest.mark.asyncio
    async def test_does_not_raise_on_extraction_failure(self):
        """Background task is non-fatal — extraction failure logs but does not raise."""
        _inject_full_mock_config()
        from app.memory.service import store_extracted_facts

        with patch("app.memory.extraction.extract_facts_from_conversation",
                   side_effect=Exception("Claude API down")):
            # Must not raise
            await store_extracted_facts(
                user_message="test",
                assistant_response="test",
                user_id=str(uuid.uuid4()),
            )

    @pytest.mark.asyncio
    async def test_skips_storage_when_no_facts_extracted(self):
        """If extraction returns empty list, no DB operations are performed."""
        _inject_full_mock_config()
        from app.memory import service as memory_service

        with patch("app.memory.extraction.extract_facts_from_conversation", return_value=[]), \
             patch("app.memory.service.store_fact", new_callable=AsyncMock) as mock_store:

            await memory_service.store_extracted_facts(
                user_message="Hello!",
                assistant_response="Hi there!",
                user_id=str(uuid.uuid4()),
            )

        mock_store.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: contradiction detection (supersede logic)
# ---------------------------------------------------------------------------

class TestContradictionDetection:
    """Contradiction detection: similarity > 0.92 triggers supersede, not new fact."""

    @pytest.mark.asyncio
    async def test_uses_output_config_not_output_format(self):
        """extraction.py must use output_config, not the deprecated parameter."""
        _inject_full_mock_config()
        import inspect
        from app.memory import extraction
        source = inspect.getsource(extraction)
        assert "output_config" in source, "Must use output_config for structured output (GA API)"
        assert "output_format" not in source, "Deprecated parameter must not appear in source"

    def test_supersede_threshold_is_0_92(self):
        """SUPERSEDE_SIMILARITY_THRESHOLD must be 0.92 per CONTEXT.md."""
        _inject_full_mock_config()
        from app.memory.service import SUPERSEDE_SIMILARITY_THRESHOLD
        assert SUPERSEDE_SIMILARITY_THRESHOLD == pytest.approx(0.92)
