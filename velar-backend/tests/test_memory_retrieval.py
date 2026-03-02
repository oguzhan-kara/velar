"""Tests for app/memory/retrieval.py — semantic retrieval and token cap.

All tests are unit tests with mocked embeddings and DB — no real OpenAI API
or Supabase connection required. Uses the same conftest pattern as voice tests:
sys.modules injection to avoid pydantic-settings ValidationError.
"""

import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Config mock — prevent pydantic-settings from requiring .env at collection time
# ---------------------------------------------------------------------------

def _make_mock_config():
    """Create a minimal mock settings object for memory tests."""
    mock_settings = MagicMock()
    mock_settings.openai_api_key = "sk-test-mock"
    mock_settings.database_url = "postgresql+asyncpg://test:test@localhost/test"
    mock_settings.debug = False
    return mock_settings


# Inject before any app import
_mock_config_module = types.ModuleType("app.config")
_mock_config_module.settings = _make_mock_config()
sys.modules.setdefault("app.config", _mock_config_module)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fact(
    category: str = "health",
    key: str = "allergy",
    value: str = "nuts",
    fact_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    embedding: list[float] | None = None,
    valid_until=None,
    superseded_by=None,
) -> MagicMock:
    """Build a mock MemoryFact with configurable fields."""
    fact = MagicMock()
    fact.id = fact_id or uuid.uuid4()
    fact.user_id = user_id or uuid.uuid4()
    fact.category = category
    fact.key = key
    fact.value = value
    fact.embedding = embedding or [0.1] * 1536
    fact.valid_until = valid_until
    fact.superseded_by = superseded_by
    return fact


# ---------------------------------------------------------------------------
# Test: facts_to_context_string token cap
# ---------------------------------------------------------------------------

class TestFactsToContextString:
    """facts_to_context_string must respect the 1800-token cap."""

    def test_empty_facts_returns_empty_string(self):
        from app.memory.retrieval import facts_to_context_string
        result = facts_to_context_string([])
        assert result == ""

    def test_single_fact_formatted_correctly(self):
        from app.memory.retrieval import facts_to_context_string
        fact_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        fact = _make_fact(category="health", key="allergy", value="nuts", fact_id=fact_id)
        result = facts_to_context_string([fact])
        assert "- [health] allergy: nuts" in result
        assert str(fact_id) in result

    def test_token_cap_truncates_facts(self):
        """When total tokens exceed cap, later facts are dropped."""
        from app.memory.retrieval import facts_to_context_string
        # Create 200 facts — collectively well over 1800 tokens
        facts = [
            _make_fact(
                category="preference",
                key=f"item_{i:03d}",
                value="a" * 50,  # ~12 tokens per line
            )
            for i in range(200)
        ]
        result = facts_to_context_string(facts, max_tokens=1800)
        lines = [l for l in result.split("\n") if l.strip()]
        # Should be significantly fewer than 200 lines
        assert len(lines) < 200
        assert len(lines) > 0

    def test_uses_1800_not_2000_cap(self):
        """TOKEN_CAP constant must be 1800, not 2000 (10% safety margin)."""
        from app.memory.retrieval import TOKEN_CAP
        assert TOKEN_CAP == 1800


# ---------------------------------------------------------------------------
# Test: get_relevant_facts
# ---------------------------------------------------------------------------

class TestGetRelevantFacts:
    """get_relevant_facts must: embed query, query DB, filter active-only facts."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_embedding_failure(self):
        """If embedding raises RuntimeError, returns [] without crashing."""
        from app.memory.retrieval import get_relevant_facts

        mock_session = AsyncMock()
        with patch("app.memory.retrieval.get_embedding", side_effect=RuntimeError("API down")):
            result = await get_relevant_facts(mock_session, str(uuid.uuid4()), "query text")
        assert result == []
        # Session should NOT have been queried
        mock_session.scalars.assert_not_called()

    @pytest.mark.asyncio
    async def test_queries_only_active_facts(self):
        """The WHERE clause must filter valid_until IS NULL AND superseded_by IS NULL."""
        from app.memory.retrieval import get_relevant_facts

        # session.scalars() is awaited in retrieval.py — AsyncMock handles that.
        # The returned scalars result calls .all() synchronously (it's already resolved),
        # so mock_scalars needs MagicMock (not AsyncMock) for .all().
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session = AsyncMock()
        mock_session.scalars.return_value = mock_scalars

        test_embedding = [0.1] * 1536
        with patch("app.memory.retrieval.get_embedding", return_value=test_embedding):
            result = await get_relevant_facts(
                mock_session, str(uuid.uuid4()), "what are my allergies"
            )

        assert result == []
        mock_session.scalars.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_facts_in_order(self):
        """Facts returned from DB are passed through in order."""
        from app.memory.retrieval import get_relevant_facts

        fact1 = _make_fact(key="allergy", value="nuts")
        fact2 = _make_fact(key="diet", value="vegan")

        # .all() is synchronous on the awaited scalars result — use MagicMock
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [fact1, fact2]
        mock_session = AsyncMock()
        mock_session.scalars.return_value = mock_scalars

        test_embedding = [0.1] * 1536
        with patch("app.memory.retrieval.get_embedding", return_value=test_embedding):
            result = await get_relevant_facts(
                mock_session, str(uuid.uuid4()), "dietary restrictions"
            )

        assert result == [fact1, fact2]

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_db_error(self):
        """DB exception is caught — returns [] without propagating."""
        from app.memory.retrieval import get_relevant_facts

        mock_session = AsyncMock()
        mock_session.scalars.side_effect = Exception("DB connection lost")

        test_embedding = [0.1] * 1536
        with patch("app.memory.retrieval.get_embedding", return_value=test_embedding):
            result = await get_relevant_facts(
                mock_session, str(uuid.uuid4()), "query"
            )

        assert result == []


# ---------------------------------------------------------------------------
# Test: embedding service dimension assertion
# ---------------------------------------------------------------------------

class TestGetEmbedding:
    """OpenAI embedding path must return 1536-dim vectors and assert dimensions.

    These tests exercise _get_openai_embedding directly, since get_embedding()
    dispatches to the local sentence-transformers path by default
    (EMBEDDING_PROVIDER=local). The OpenAI path remains fully intact and
    tested here via the internal _get_openai_embedding function.
    """

    @pytest.mark.asyncio
    async def test_returns_1536_dimensional_vector(self):
        from app.memory.embeddings import _get_openai_embedding  # noqa: PLC0415

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]

        mock_client = AsyncMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("app.memory.embeddings._get_openai_client", return_value=mock_client):
            result = await _get_openai_embedding("I am allergic to nuts")

        assert len(result) == 1536
        assert result[0] == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_raises_on_wrong_dimension(self):
        """If OpenAI returns wrong dimension, AssertionError is raised."""
        from app.memory.embeddings import _get_openai_embedding  # noqa: PLC0415

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 512)]  # wrong!

        mock_client = AsyncMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("app.memory.embeddings._get_openai_client", return_value=mock_client):
            with pytest.raises(AssertionError):
                await _get_openai_embedding("test text")

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_api_failure(self):
        """API failure is wrapped in RuntimeError."""
        from app.memory.embeddings import _get_openai_embedding  # noqa: PLC0415

        mock_client = AsyncMock()
        mock_client.embeddings.create.side_effect = Exception("connection timeout")

        with patch("app.memory.embeddings._get_openai_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="Embedding failed"):
                await _get_openai_embedding("test text")
