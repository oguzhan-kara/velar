import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture
async def client():
    """Async test client for FastAPI app.

    The app is imported lazily inside the fixture so that collecting tests that
    do not use this fixture (e.g. voice unit tests) does not trigger
    pydantic-settings validation — which would require a .env file even in
    environments where Supabase credentials are not available.
    """
    from app.main import app  # lazy import — only triggered when fixture is used

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# Note: For auth/RLS tests against real Supabase cloud, set these env vars:
# TEST_USER_EMAIL, TEST_USER_PASSWORD  — primary test account (must pre-exist in Supabase)
# TEST_USER2_EMAIL, TEST_USER2_PASSWORD — secondary test account for RLS cross-user test
# These are loaded from .env automatically via pydantic-settings / python-dotenv
