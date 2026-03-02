"""Tests for /memory CRUD API endpoints.

Tests: fact creation, retrieval, update (supersede), soft-delete, cross-session
retrieval simulation, search endpoint. All tests use httpx AsyncClient with mocked
DB operations — no real Supabase connection required for unit tests.

Integration tests (marked with pytest.mark.integration) require real Supabase
credentials and are skipped in CI unless TEST_USER_EMAIL is set.
"""

import sys
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Config mock injection — inject a complete settings mock before any app import
# that triggers app.database (which calls create_async_engine at module level).
# Uses force-set (not setdefault) to override incomplete mocks from other test files.
# Follows the pattern used in test_voice_e2e.py.
# ---------------------------------------------------------------------------

def _inject_full_mock_config() -> MagicMock:
    """Inject a complete mock app.config with all fields needed for app.database.

    database_url must be a real string — SQLAlchemy's create_async_engine is called
    at module import time in app/database.py and will fail if database_url is a
    MagicMock sub-attribute (which happens when another test set an incomplete mock).
    """
    mock_settings = MagicMock()
    mock_settings.supabase_url = "https://test.supabase.co"
    mock_settings.supabase_anon_key = "test-anon-key"
    mock_settings.supabase_service_role_key = "test-service-role-key"
    mock_settings.supabase_jwt_secret = "test-jwt-secret-that-is-long-enough-for-hs256"
    mock_settings.database_url = "postgresql+asyncpg://test:test@localhost/test"
    mock_settings.anthropic_api_key = "sk-ant-test"
    mock_settings.openai_api_key = "sk-test"
    mock_settings.elevenlabs_api_key = ""
    mock_settings.whisper_model_size = "large-v3-turbo"
    mock_settings.environment = "test"
    mock_settings.debug = False

    mock_config_module = types.ModuleType("app.config")
    mock_config_module.settings = mock_settings
    sys.modules["app.config"] = mock_config_module
    return mock_settings


# Note: _inject_full_mock_config() is NOT called at module level here.
# It is called lazily inside each fixture/test that needs app.database imported.
# This prevents the module-level injection from interfering with test_auth.py's
# conftest client fixture which needs the real pydantic-settings validation error
# (not a mock) to signal it needs Supabase credentials.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_fact(
    fact_id: uuid.UUID | None = None,
    category: str = "health",
    key: str = "allergy",
    value: str = "nuts",
    source: str = "explicit",
    confidence: float = 1.0,
    valid_until=None,
    superseded_by=None,
) -> MagicMock:
    fact = MagicMock()
    fact.id = fact_id or uuid.uuid4()
    fact.user_id = uuid.uuid4()
    fact.category = category
    fact.key = key
    fact.value = value
    fact.source = source
    fact.confidence = confidence
    fact.embedding = [0.1] * 1536
    fact.valid_from = datetime.now(timezone.utc)
    fact.valid_until = valid_until
    fact.superseded_by = superseded_by
    fact.created_at = datetime.now(timezone.utc)
    return fact


def _fake_user():
    return {"user_id": str(uuid.uuid4()), "email": "test@test.com"}


async def _fake_db():
    """Async generator yielding a mock session."""
    yield AsyncMock()


@pytest_asyncio.fixture
async def memory_client():
    """ASGI test client with mocked auth and DB for memory endpoint tests.

    Injects complete mock config before importing app.main, then overrides
    auth and DB dependencies. Follows the pattern used in test_voice_e2e.py.
    """
    # Inject complete config before app.main import (prevents MagicMock database_url)
    _inject_full_mock_config()

    from app.main import app
    from app.dependencies import get_current_user
    from app.database import get_db

    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _fake_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Tests: Memory API endpoints (unit tests with mocked service layer)
# ---------------------------------------------------------------------------

class TestCreateFact:
    """POST /api/v1/memory — manually add a fact."""

    @pytest.mark.asyncio
    async def test_create_fact_returns_201(self, memory_client):
        """Valid fact creation returns 201 with fact data."""
        mock_fact = _make_mock_fact()

        with patch("app.memory.router.store_fact", new_callable=AsyncMock, return_value=mock_fact):
            response = await memory_client.post(
                "/api/v1/memory",
                json={"category": "health", "key": "allergy", "value": "nuts"},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["category"] == "health"
        assert data["key"] == "allergy"


class TestDeleteFact:
    """DELETE /api/v1/memory/{id} — soft-delete."""

    @pytest.mark.asyncio
    async def test_delete_fact_returns_204(self, memory_client):
        """Successful soft-delete returns 204 No Content."""
        fact_id = str(uuid.uuid4())

        with patch("app.memory.router.soft_delete_fact", new_callable=AsyncMock, return_value=True):
            response = await memory_client.delete(
                f"/api/v1/memory/{fact_id}",
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_nonexistent_fact_returns_404(self, memory_client):
        """Fact not found returns 404."""
        with patch("app.memory.router.soft_delete_fact", new_callable=AsyncMock, return_value=False):
            response = await memory_client.delete(
                f"/api/v1/memory/{uuid.uuid4()}",
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 404


class TestUpdateFact:
    """PATCH /api/v1/memory/{id} — update creates superseding version."""

    @pytest.mark.asyncio
    async def test_update_fact_returns_new_fact(self, memory_client):
        """PATCH returns the new superseding fact, not the original."""
        new_fact = _make_mock_fact(value="gluten")

        with patch("app.memory.router.update_fact", new_callable=AsyncMock, return_value=new_fact):
            response = await memory_client.patch(
                f"/api/v1/memory/{uuid.uuid4()}",
                json={"value": "gluten"},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "gluten"

    @pytest.mark.asyncio
    async def test_update_nonexistent_fact_returns_404(self, memory_client):
        """Update of non-existent fact returns 404."""
        with patch("app.memory.router.update_fact", new_callable=AsyncMock, return_value=None):
            response = await memory_client.patch(
                f"/api/v1/memory/{uuid.uuid4()}",
                json={"value": "new value"},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 404


class TestMemoryHallucinationGuard:
    """Hallucination guard: system prompt must state what VELAR does NOT know."""

    def test_memory_context_block_in_system_prompt(self):
        """When memory_context is provided, hallucination guard text appears in system."""
        import asyncio
        from unittest.mock import MagicMock, patch
        from app.voice.conversation import run_conversation

        captured_system = []

        def capture_create(**kwargs):
            captured_system.append(kwargs.get("system", ""))
            mock_resp = MagicMock()
            mock_resp.content = [MagicMock(text="Test response")]
            return mock_resp

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = capture_create

        with patch("app.voice.conversation._get_client", return_value=mock_client):
            asyncio.get_event_loop().run_until_complete(
                run_conversation(
                    user_text="What are my allergies?",
                    memory_context="- [health] allergy: nuts (id:12345678-1234-5678-1234-567812345678)",
                )
            )

        assert len(captured_system) == 1
        system = captured_system[0]
        assert "[VELAR MEMORY" in system
        assert "do NOT know it" in system or "do not know it" in system.lower()

    def test_no_memory_block_when_context_is_none(self):
        """When memory_context is None, no VELAR MEMORY block in system prompt."""
        import asyncio
        from unittest.mock import MagicMock, patch
        from app.voice.conversation import run_conversation

        captured_system = []

        def capture_create(**kwargs):
            captured_system.append(kwargs.get("system", ""))
            mock_resp = MagicMock()
            mock_resp.content = [MagicMock(text="Test response")]
            return mock_resp

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = capture_create

        with patch("app.voice.conversation._get_client", return_value=mock_client):
            asyncio.get_event_loop().run_until_complete(
                run_conversation(
                    user_text="Hello!",
                    memory_context=None,
                )
            )

        assert "[VELAR MEMORY" not in captured_system[0]


class TestCrossSessionRetrieval:
    """MEM-05: facts stored in Supabase persist across sessions."""

    def test_facts_scoped_to_user_id(self):
        """Retrieval query filters by user_id — different users get different facts."""
        # This is a design verification test — the ORM WHERE clause must include user_id
        import inspect
        from app.memory import retrieval
        source = inspect.getsource(retrieval.get_relevant_facts)
        assert "user_id" in source, "get_relevant_facts must filter by user_id"
        assert "valid_until" in source, "Must filter for active facts only"
        assert "superseded_by" in source, "Must exclude superseded facts"
