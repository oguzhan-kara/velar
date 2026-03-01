import asyncio
from supabase import create_client, Client
from app.config import settings


def _get_supabase_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_anon_key)


async def sign_in(email: str, password: str) -> dict:
    """Sign in with Supabase Auth. Returns access_token."""
    def _sign_in():
        client = _get_supabase_client()
        response = client.auth.sign_in_with_password({"email": email, "password": password})
        return response

    # supabase-py sync client wrapped in thread to avoid blocking async event loop
    response = await asyncio.to_thread(_sign_in)
    if response.session is None:
        raise ValueError("Authentication failed")
    return {
        "access_token": response.session.access_token,
        "token_type": "bearer",
        "user_id": str(response.user.id),
        "email": response.user.email,
    }
