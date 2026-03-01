"""
RLS Isolation Test
==================
Verifies that a user CANNOT access another user's memory_facts via the API.

Requires TWO pre-existing Supabase test accounts:
  TEST_USER_EMAIL / TEST_USER_PASSWORD    — primary user
  TEST_USER2_EMAIL / TEST_USER2_PASSWORD  — secondary user (the "attacker")

These tests run against the real cloud Supabase project and require the
migration from 01-01 to have been applied (supabase db push).

IMPORTANT: This test addresses the January 2025 RLS misconfiguration incident
where 170+ apps built with Lovable exposed user data due to missing RLS.
Running this test is a Phase 1 acceptance criterion.
"""
import pytest
import os
import asyncio
from supabase import create_client
from app.config import settings

SKIP_REASON = "TEST_USER_EMAIL or TEST_USER2_EMAIL not set — skipping RLS isolation test"
SKIP = not (os.getenv("TEST_USER_EMAIL") and os.getenv("TEST_USER2_EMAIL"))


def get_user_client(jwt: str):
    """Create a Supabase client acting as the given user (RLS applies)."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.auth.set_session(access_token=jwt, refresh_token="")
    return client


def sign_in_sync(email: str, password: str) -> str:
    """Sign in and return access_token."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    resp = client.auth.sign_in_with_password({"email": email, "password": password})
    return resp.session.access_token


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP, reason=SKIP_REASON)
async def test_rls_user_cannot_read_other_user_facts():
    """
    User A inserts a memory fact.
    User B (different account) cannot see User A's fact via select.
    """
    user1_token = await asyncio.to_thread(
        sign_in_sync,
        os.environ["TEST_USER_EMAIL"],
        os.environ["TEST_USER_PASSWORD"],
    )
    user2_token = await asyncio.to_thread(
        sign_in_sync,
        os.environ["TEST_USER2_EMAIL"],
        os.environ["TEST_USER2_PASSWORD"],
    )

    user1_client = get_user_client(user1_token)
    user2_client = get_user_client(user2_token)

    # User 1 inserts a fact
    unique_value = "rls-test-secret-value-do-not-return-to-user2"
    def _insert():
        return user1_client.table("memory_facts").insert({
            "category": "test",
            "key": "rls_test_key",
            "value": unique_value,
            "source": "explicit",
        }).execute()

    insert_result = await asyncio.to_thread(_insert)
    assert insert_result.data, "Insert as user1 failed"
    inserted_id = insert_result.data[0]["id"]

    try:
        # User 2 attempts to read ALL memory_facts — RLS should return empty
        def _read_as_user2():
            return user2_client.table("memory_facts").select("*").execute()

        read_result = await asyncio.to_thread(_read_as_user2)
        # RLS must ensure user2 sees NO rows from user1
        user1_fact_visible = any(
            row.get("value") == unique_value for row in (read_result.data or [])
        )
        assert not user1_fact_visible, (
            "RLS FAILURE: User2 can read User1's memory_facts. "
            "Check that RLS is enabled on memory_facts table and policies are correct."
        )
    finally:
        # Cleanup: user1 deletes the test fact
        def _cleanup():
            user1_client.table("memory_facts").delete().eq("id", inserted_id).execute()
        await asyncio.to_thread(_cleanup)
