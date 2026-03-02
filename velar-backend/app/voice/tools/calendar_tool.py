"""Google Calendar integration tool for VELAR.

Fetches upcoming events from the user's primary Google Calendar via OAuth2.
Tokens are stored securely in macOS Keychain via the keyring library.

Authentication flow:
    1. First run: browser opens for Google OAuth consent.
    2. Token serialized to JSON and stored in Keychain (KEYRING_SERVICE/KEYRING_KEY).
    3. Subsequent runs: load token from Keychain, auto-refresh if expired.

Thread safety:
    _get_credentials() uses a threading.Lock to prevent concurrent token refreshes
    (Pitfall 7 from research: concurrent refresh races can corrupt token state).
"""

import asyncio
import datetime
import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
KEYRING_SERVICE = "velar"
KEYRING_KEY = "google_calendar_token"

_credentials_lock = threading.Lock()


def _get_credentials():
    """Load or refresh Google OAuth2 credentials, serializing to Keychain.

    Thread-safe via _credentials_lock — prevents concurrent refresh races.
    """
    import keyring
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from app.config import settings  # lazy import — avoids startup validation

    with _credentials_lock:
        creds = None
        token_json = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY)
        if token_json:
            creds = Credentials.from_authorized_user_info(
                json.loads(token_json), SCOPES
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing Google Calendar OAuth2 token")
                creds.refresh(Request())
            else:
                # First-run: open browser for OAuth consent
                credentials_path = Path(
                    settings.google_calendar_credentials_path
                ).expanduser()
                logger.info(
                    "Starting Google Calendar OAuth2 flow from %s", credentials_path
                )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0, open_browser=True)

            # Store refreshed/new token in Keychain
            keyring.set_password(KEYRING_SERVICE, KEYRING_KEY, creds.to_json())

        return creds


def _get_calendar_events_sync(days_ahead: int) -> str:
    """Synchronous implementation — called via asyncio.to_thread."""
    from googleapiclient.discovery import build

    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    end = now + datetime.timedelta(days=days_ahead)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = result.get("items", [])
    if not events:
        label = "today" if days_ahead == 1 else f"the next {days_ahead} days"
        return f"No upcoming events found for {label}."

    # Format each event as prose — handle all-day events (Pitfall 3):
    # All-day events use the "date" key instead of "dateTime".
    parts = []
    for event in events:
        title = event.get("summary", "Untitled")
        start_raw = event["start"].get("dateTime", event["start"].get("date", ""))
        # Parse ISO datetime string to human-friendly time
        try:
            if "T" in start_raw:
                dt = datetime.datetime.fromisoformat(start_raw)
                start_str = dt.strftime("%-I:%M %p")
            else:
                # All-day event: just the date
                start_str = start_raw
        except (ValueError, TypeError):
            start_str = start_raw
        location = event.get("location", "")
        if location:
            parts.append(f"{title} at {start_str} ({location})")
        else:
            parts.append(f"{title} at {start_str}")

    count = len(parts)
    label = "today" if days_ahead == 1 else f"over the next {days_ahead} days"
    if count == 1:
        return f"You have 1 event {label}: {parts[0]}."
    joined = ", and ".join([", ".join(parts[:-1]), parts[-1]]) if count > 1 else parts[0]
    return f"You have {count} events {label}: {joined}."


async def get_calendar_events(days_ahead: int = 1) -> str:
    """Fetch upcoming events from the user's primary Google Calendar.

    Args:
        days_ahead: Number of days to look ahead (1=today only, 7=week).

    Returns:
        Voice-optimized prose string with event list or "no events" message.
    """
    return await asyncio.to_thread(_get_calendar_events_sync, days_ahead)
