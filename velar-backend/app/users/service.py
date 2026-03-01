import asyncio
from supabase import create_client
from app.config import settings


async def get_user_profile(user_id: str, user_jwt: str) -> dict | None:
    """Fetch user profile using a user-scoped Supabase client so RLS applies."""
    def _fetch():
        # anon_key client + set_session makes queries run as the authenticated user
        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        client.auth.set_session(access_token=user_jwt, refresh_token="")
        result = client.table("user_profiles").select("*").eq("id", user_id).single().execute()
        return result.data
    return await asyncio.to_thread(_fetch)
