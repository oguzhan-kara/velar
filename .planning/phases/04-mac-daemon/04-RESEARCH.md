# Phase 4: Mac Daemon and Integrations - Research

**Researched:** 2026-03-02
**Domain:** macOS daemon (launchd + rumps + openwakeword + sounddevice) + API integrations (Google Calendar, OpenWeatherMap, Google Places, AppleScript Reminders) + Anthropic tool_use
**Confidence:** MEDIUM (locked decisions well-researched; openwakeword macOS ARM64 compatibility requires empirical validation)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Daemon Architecture**
- Thin client model: daemon owns hardware (mic, speakers) and wake word; FastAPI backend owns STT/Claude/TTS
- Daemon sends captured audio to existing `/api/v1/voice` endpoint — no duplicated pipeline logic
- Daemon is a Python process launched via launchd for boot persistence
- Library: `rumps` for menu bar icon (Python-native, no Objective-C bridge required)
- Menu bar icon states: gray dot (idle), pulsing blue dot (listening), spinning (processing)
- Daemon designed for local backend (same Mac in dev) but backend URL is configurable via env

**Wake Word Behavior**
- Model: openwakeword with `hey_jarvis` pretrained model — closest phonetically to "Hey VELAR"; custom model training deferred
- On wake: 200ms metallic chime plays immediately to confirm listening started
- Audio capture: sounddevice continuous stream, Silero VAD (reuse Phase 2 params) detects speech boundaries
- Auto-timeout: 8 seconds max recording, stops after 1.5s silence post-speech
- If no speech detected within 3s of wake: short "cancelled" tone → return to idle (no API call made)
- Menu bar includes "Pause wake word" toggle for silent work sessions — icon shows muted state
- macOS automatically shows mic indicator in menu bar when sounddevice opens stream — no manual handling

**Calendar Integration**
- Google Calendar only in Phase 4 — Apple Calendar requires native EventKit (macOS Swift), deferred to Phase 6
- OAuth2 via `google-auth-oauthlib`; tokens stored in macOS Keychain via `keyring` library
- First-run setup: daemon prints auth URL to stdout, opens browser automatically via `webbrowser.open()`; token persists after one-time flow
- Token refresh: silent background refresh when <5 minutes to expiry
- Lookahead defaults: `get_calendar_events(days_ahead=1)` for today, `days_ahead=7` for week view
- Only events from the primary calendar (default); multi-calendar support deferred

**Weather Integration**
- Provider: OpenWeatherMap One Call API 3.0 — current + hourly + 7-day in one call
- Location: user's current city stored in backend user profile (set once); no live GPS in daemon
- Cache: 30-minute TTL in-process cache — weather doesn't need to be real-time for most queries
- Response includes: current temp, condition, high/low, precipitation probability for next 24h

**Reminders Tool**
- macOS Reminders via AppleScript — no OAuth required, works out of the box on Mac
- `set_reminder(text: str, minutes_from_now: int)`: creates reminder with due date = now + N minutes
- Reminders appear in macOS Reminders.app and sync to iPhone via iCloud automatically
- No list selection — adds to default Reminders list

**Places Integration**
- Google Places API (Nearby Search + Place Details)
- Location: same city-level location as weather (not GPS tracking)
- Tool: `get_places(query: str)` — returns top 3 results with name, rating, address
- Results include opening hours when available (closed venues filtered by default)

**Tool Invocation in Claude Loop**
- Four tools registered in Phase 4: `get_calendar_events`, `get_weather`, `set_reminder`, `get_places`
- Claude uses tool_use natively (Anthropic tool use API) — daemon passes tool definitions to backend with each voice request
- Backend executes tools, returns results back to Claude for response synthesis
- Voice responses for tool results: 1-3 sentences, optimized for listening (no lists, no markdown)
- Fallback: if tool call fails, Claude responds "I couldn't fetch that right now" — no retries in voice loop

**Daemon Lifecycle**
- launchd plist in `~/Library/LaunchAgents/` — loads on user login, restarts on crash
- Graceful shutdown: SIGTERM handler stops audio capture, closes sounddevice stream, saves state
- Backend connectivity check on startup: if backend unreachable, menu bar shows warning icon, retries every 30s in background
- Daemon config: `~/.velar/daemon.json` — backend URL, wake word sensitivity, audio device index

### Claude's Discretion

None explicitly marked — all major decisions are locked in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)

- Apple Calendar via EventKit — Phase 6 (iPhone App, requires native Swift/macOS)
- Custom "Hey VELAR" wake word model training — post-Phase 4 (openwakeword hey_jarvis suffices)
- Live GPS location for weather/places — Phase 6 (iPhone provides GPS)
- Hotkey activation as wake word alternative — can add later if wake word reliability is poor
- Multi-calendar support (work + personal) — Phase 5/6
- Daemon system tray on Windows/Linux — out of scope for v1 (Mac only)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VOICE-01 | User can activate VELAR with wake word ("Hey VELAR") on Mac | openwakeword hey_jarvis model + sounddevice InputStream + Silero VAD pipeline documented |
| DEV-01 | Mac daemon runs as always-on background service with wake word detection | launchd plist pattern with KeepAlive + RunAtLoad documented; rumps menu bar integration confirmed |
| INTG-01 | VELAR reads the user's calendar events (Google Calendar or Apple Calendar) | Google Calendar API OAuth2 + google-api-python-client documented; keyring for token storage confirmed |
| INTG-02 | VELAR fetches current weather and forecast for user's location | OpenWeatherMap One Call API 3.0 endpoint and response structure documented |
| INTG-03 | VELAR can set timers and reminders | AppleScript via subprocess osascript pattern documented; macOS Reminders integration confirmed |
| INTG-04 | VELAR queries nearby places via Google Places API or similar | Google Places API (New) Nearby Search POST request with field masks documented |
</phase_requirements>

---

## Summary

Phase 4 divides into two major work streams: (1) the Mac daemon process itself — wake word detection, audio capture, menu bar management, and boot persistence — and (2) the four integration tools wired into the Claude conversation loop. The daemon is a thin process that owns the microphone hardware and delegates all intelligence to the existing FastAPI backend. The tools run on the backend and are called via Anthropic's tool_use API.

The core technical challenge is the wake word pipeline: openwakeword listens on a continuous 16kHz sounddevice stream, feeds 80ms audio chunks to the hey_jarvis model, and on detection hands off to Silero VAD to record the full utterance before POSTing to `/api/v1/voice`. The rumps library handles the macOS menu bar status icon cleanly from Python without requiring Objective-C bridges, though it is no longer under active development (last release 0.4.0 in 2022). The launchd plist pattern for per-user agents is well-established and stable.

On the integration side, Google Calendar uses a standard OAuth2 InstalledAppFlow with token.json storage serialized into macOS Keychain via the `keyring` library. OpenWeatherMap One Call API 3.0 requires a separate "One Call by Call" subscription (1,000 free calls/day). Google Places API (New) uses POST requests with mandatory X-Goog-FieldMask headers. AppleScript-based Reminders creation is the pragmatic choice — it requires zero OAuth setup and integrates with iCloud sync automatically. The biggest open risk is openwakeword's untested behavior on macOS Apple Silicon (ARM64) — the official documentation focuses on Linux/Windows, and tflite is Linux-only; macOS likely uses onnxruntime which should work but needs empirical validation.

**Primary recommendation:** Build the daemon as a single Python process with a threading model — main thread runs rumps (NSApplication event loop), background threads handle the audio stream and wake word detection, and an asyncio event loop in a daemon thread handles the API calls. Validate openwakeword on the target Mac hardware before committing to the audio pipeline design.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openwakeword | 0.6.0 | Wake word detection with hey_jarvis model | Only mature open-source Python wake word library; pre-trained models included |
| sounddevice | 0.5.5 | Continuous microphone audio stream at 16kHz | PortAudio wrapper; supports callback-based InputStream; used in Phase 2 TTS too |
| silero-vad | 6.2.1 | Voice activity detection for speech boundary detection | Already chosen in Phase 2; MIT license; <1ms/chunk on CPU; 16kHz native |
| rumps | 0.4.0 | macOS menu bar status icon | Python-native, no Objective-C; only viable pure-Python option for macOS status bar |
| google-auth-oauthlib | latest | Google OAuth2 InstalledAppFlow for Calendar API | Official Google library; handles token refresh automatically |
| google-api-python-client | latest | Google Calendar API v3 client | Official Google client; provides typed service builder |
| google-auth-httplib2 | latest | HTTP transport for Google auth | Required companion to google-api-python-client |
| keyring | 25.7.0 | macOS Keychain token storage | Cross-platform secret storage; macOS Keychain backend automatic; no extra config |
| requests | >=2.31 | OpenWeatherMap and Google Places HTTP calls | Standard HTTP client; already likely in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | >=1.26 | Audio buffer manipulation | Converting sounddevice int16 chunks to openwakeword format (already in requirements.txt) |
| torch / torchaudio | >=1.12 / >=0.12 | Silero VAD dependency | Required by silero-vad package automatically |
| pydub | >=0.25 | Audio playback for chime/cancelled tones | Already in requirements.txt from Phase 2 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| openwakeword hey_jarvis | Porcupine (Picovoice) | Porcupine has better macOS ARM64 support and custom keyword training, but requires paid API key; openwakeword is fully open-source |
| sounddevice | pyaudio | sounddevice has cleaner numpy callback API and no CFFI complications; pyaudio requires portaudio headers to compile |
| AppleScript via osascript | EventKit (Swift) | EventKit is more reliable but requires building a Swift helper binary; osascript works out of the box with no compilation |
| Google Places API (New) | Foursquare / Yelp API | Google Places has best coverage and matches decision; alternatives not in scope |

**Installation (daemon — separate from backend):**
```bash
pip install openwakeword sounddevice silero-vad rumps numpy pydub
```

**Installation (backend additions):**
```bash
pip install google-auth-oauthlib google-api-python-client google-auth-httplib2 keyring requests
```

---

## Architecture Patterns

### Recommended Project Structure
```
velar-daemon/                    # new top-level directory (sibling of velar-backend/)
├── daemon.py                    # entry point: rumps.App subclass, threading orchestration
├── wakeword.py                  # openwakeword + sounddevice InputStream loop
├── audio_capture.py             # post-wake VAD recording until silence/timeout
├── config.py                    # loads ~/.velar/daemon.json; env overrides
├── chime.py                     # plays chime/cancelled tones via pydub
├── backend_client.py            # HTTP client for POST /api/v1/voice
├── launchd/
│   └── com.velar.daemon.plist   # template plist (paths substituted at install)
├── requirements.txt             # daemon-specific deps
└── install.sh                   # copies plist, substitutes paths, runs launchctl bootstrap

velar-backend/app/
├── voice/
│   ├── conversation.py          # EXISTING — Phase 4 activates the tool-use scaffold
│   ├── tools/                   # NEW: tool implementations
│   │   ├── __init__.py
│   │   ├── registry.py          # TOOL_DEFINITIONS list for Anthropic API
│   │   ├── calendar_tool.py     # get_calendar_events()
│   │   ├── weather_tool.py      # get_weather()
│   │   ├── reminder_tool.py     # set_reminder() via AppleScript
│   │   └── places_tool.py       # get_places()
│   └── router.py                # EXISTING — tools injected per request
```

### Pattern 1: Thread Model for Daemon

**What:** rumps runs its own NSApplication event loop on the main thread. Background tasks (audio stream, API calls) must run on separate threads. Use threading.Thread for the audio/wake-word loop and asyncio in a daemon thread for async API calls.

**When to use:** Any macOS menu bar app with background work — rumps.App.run() blocks the main thread permanently.

```python
# daemon.py — Source: rumps official docs + threading pattern
import threading
import rumps
from wakeword import WakeWordListener

class VelarDaemon(rumps.App):
    def __init__(self):
        super().__init__("VELAR", title="●")  # gray dot = idle
        self.menu = [
            rumps.MenuItem("Pause Wake Word", callback=self.toggle_pause),
            None,  # separator
        ]
        self._listener = WakeWordListener(on_wake=self._on_wake)
        self._paused = False

    def _on_wake(self):
        """Called from audio thread — update UI safely."""
        self.title = "◉"  # blue dot = listening
        # ... dispatch audio capture and API call on separate thread

    @rumps.clicked("Pause Wake Word")
    def toggle_pause(self, sender):
        self._paused = not self._paused
        sender.state = self._paused
        self._listener.paused = self._paused
        self.title = "⊘" if self._paused else "●"

    def application_will_finish_launching_(self, notification):
        """Start background listener after rumps main loop starts."""
        t = threading.Thread(target=self._listener.run, daemon=True)
        t.start()

if __name__ == "__main__":
    VelarDaemon().run()
```

### Pattern 2: Wake Word Detection Loop

**What:** sounddevice InputStream feeds 1280-sample (80ms at 16kHz) chunks to openwakeword. Detection fires when prediction score exceeds threshold (default 0.5).

**When to use:** Always-on passive listening before VAD capture.

```python
# wakeword.py
import numpy as np
import sounddevice as sd
from openwakeword.model import Model

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms at 16kHz — openwakeword minimum

class WakeWordListener:
    def __init__(self, on_wake, sensitivity=0.5):
        self.on_wake = on_wake
        self.sensitivity = sensitivity
        self.paused = False
        self._model = Model(wakeword_models=["hey jarvis"])

    def run(self):
        """Blocking loop — run on a daemon thread."""
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SAMPLES,
        ) as stream:
            while True:
                if self.paused:
                    import time; time.sleep(0.1)
                    continue
                audio_chunk, _ = stream.read(CHUNK_SAMPLES)
                prediction = self._model.predict(audio_chunk.flatten())
                score = prediction.get("hey jarvis", 0.0)
                if score >= self.sensitivity:
                    self._model.reset()  # prevent re-trigger
                    self.on_wake()
```

### Pattern 3: Anthropic Tool Use Loop (Backend)

**What:** `run_conversation` in `conversation.py` must be extended to pass tool definitions and loop until `stop_reason == "end_turn"`, executing any tool calls in between.

**When to use:** Every voice request in Phase 4+. The scaffold is already present as commented code in conversation.py.

```python
# velar-backend/app/voice/conversation.py — Phase 4 extension
# Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use

from app.voice.tools.registry import TOOL_DEFINITIONS
from app.voice.tools.registry import execute_tool  # dispatcher

async def run_conversation(user_text, history=None, max_tokens=512,
                           detected_language=None, memory_context=None,
                           user_id=None):  # user_id needed for tool context
    system = _build_system(detected_language, memory_context)
    messages = _build_messages(history, user_text)
    client = _get_client()

    while True:
        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-haiku-4-5-20251001",
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            tools=TOOL_DEFINITIONS,
        )

        if response.stop_reason == "end_turn":
            # Return the text content
            for block in response.content:
                if block.type == "text":
                    return block.text
            return ""  # fallback

        if response.stop_reason == "tool_use":
            # Append assistant message with tool_use blocks
            messages.append({"role": "assistant", "content": response.content})
            # Execute each tool call and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = await execute_tool(block.name, block.input, user_id)
                    except Exception as exc:
                        result = f"Tool error: {exc}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "user", "content": tool_results})
            # Loop continues — Claude will synthesize a voice response
        else:
            # Unexpected stop_reason — bail
            break

    return "I couldn't fetch that right now."
```

### Pattern 4: Tool Registry

**What:** Centralized tool definitions + dispatcher pattern. All four tools defined in one place; `execute_tool()` routes by name.

```python
# velar-backend/app/voice/tools/registry.py
TOOL_DEFINITIONS = [
    {
        "name": "get_calendar_events",
        "description": (
            "Retrieves upcoming events from the user's primary Google Calendar. "
            "Use when the user asks about their schedule, next appointment, today's events, "
            "or what they have planned. Returns a list of events with title, start time, and location. "
            "Do not use for past events. days_ahead=1 means today only; days_ahead=7 means the week."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "How many days of events to fetch (1=today, 7=week)",
                    "default": 1,
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_weather",
        "description": (
            "Fetches current weather conditions and forecast for the user's city. "
            "Use when the user asks about weather, temperature, rain, or whether to bring an umbrella. "
            "Returns current temperature, condition, high/low, and precipitation probability for 24h."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "set_reminder",
        "description": (
            "Creates a reminder in macOS Reminders app with iCloud sync. "
            "Use when the user says 'remind me', 'set a reminder', or 'don't let me forget'. "
            "The reminder will appear in Reminders.app and sync to iPhone. "
            "minutes_from_now must be a positive integer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The reminder text"},
                "minutes_from_now": {
                    "type": "integer",
                    "description": "When to trigger the reminder, in minutes from now",
                },
            },
            "required": ["text", "minutes_from_now"],
        },
    },
    {
        "name": "get_places",
        "description": (
            "Searches for nearby places matching a query (restaurants, cafes, gyms, etc.). "
            "Use when the user asks where to go, what's nearby, or for place recommendations. "
            "Returns top 3 open results with name, rating, and address. "
            "Location is the user's configured city, not real-time GPS."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What kind of place to find (e.g. 'coffee shop', 'italian restaurant')",
                }
            },
            "required": ["query"],
        },
    },
]

async def execute_tool(name: str, inputs: dict, user_id: str) -> str:
    if name == "get_calendar_events":
        from app.voice.tools.calendar_tool import get_calendar_events
        return await get_calendar_events(**inputs)
    elif name == "get_weather":
        from app.voice.tools.weather_tool import get_weather
        return await get_weather()
    elif name == "set_reminder":
        from app.voice.tools.reminder_tool import set_reminder
        return await set_reminder(**inputs)
    elif name == "get_places":
        from app.voice.tools.places_tool import get_places
        return await get_places(**inputs)
    raise ValueError(f"Unknown tool: {name}")
```

### Pattern 5: Google Calendar OAuth2 + Keyring Token Storage

**What:** One-time browser auth flow, token serialized to JSON and stored in macOS Keychain. Silent refresh on expiry.

```python
# velar-backend/app/voice/tools/calendar_tool.py
# Source: https://developers.google.com/calendar/api/quickstart/python
import json
import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import datetime, webbrowser

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
KEYRING_SERVICE = "velar"
KEYRING_KEY = "google_calendar_token"

def _get_credentials() -> Credentials:
    creds = None
    token_json = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY)
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # First-run: open browser for OAuth consent
            flow = InstalledAppFlow.from_client_secrets_file(
                "~/.velar/google_credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0, open_browser=True)
        # Store refreshed/new token in Keychain
        keyring.set_password(KEYRING_SERVICE, KEYRING_KEY, creds.to_json())
    return creds

async def get_calendar_events(days_ahead: int = 1) -> str:
    import asyncio
    return await asyncio.to_thread(_get_calendar_events_sync, days_ahead)

def _get_calendar_events_sync(days_ahead: int) -> str:
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    end = now + datetime.timedelta(days=days_ahead)
    result = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=end.isoformat(),
        maxResults=10,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = result.get("items", [])
    if not events:
        return "No upcoming events found."
    lines = []
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date"))
        lines.append(f"- {e.get('summary', 'Untitled')} at {start}")
    return "\n".join(lines)
```

### Pattern 6: AppleScript Reminders via subprocess

**What:** `osascript -e` executes AppleScript inline. No OAuth, no app registration. Instant.

```python
# velar-backend/app/voice/tools/reminder_tool.py
import subprocess
import datetime

async def set_reminder(text: str, minutes_from_now: int) -> str:
    import asyncio
    return await asyncio.to_thread(_set_reminder_sync, text, minutes_from_now)

def _set_reminder_sync(text: str, minutes_from_now: int) -> str:
    due = datetime.datetime.now() + datetime.timedelta(minutes=minutes_from_now)
    # AppleScript date format: "MM/DD/YYYY HH:MM:SS"
    due_str = due.strftime("%m/%d/%Y %H:%M:%S")
    script = f'''
    tell application "Reminders"
        set newReminder to make new reminder with properties {{name:"{text}", remind me date:date "{due_str}"}}
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript failed: {result.stderr}")
    return f"Reminder set: '{text}' in {minutes_from_now} minutes."
```

### Pattern 7: OpenWeatherMap One Call API 3.0

**What:** Single call returns current + hourly + daily forecast. Requires "One Call by Call" subscription (1,000 free calls/day).

```python
# velar-backend/app/voice/tools/weather_tool.py
import time, requests
from app.config import settings

_cache: dict = {}  # {"data": ..., "expires": float}
CACHE_TTL = 1800  # 30 minutes

async def get_weather() -> str:
    import asyncio
    return await asyncio.to_thread(_get_weather_sync)

def _get_weather_sync() -> str:
    now = time.time()
    if _cache.get("expires", 0) > now:
        return _format_weather(_cache["data"])

    lat, lon = _geocode_city(settings.weather_city)
    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": lat, "lon": lon,
        "appid": settings.openweathermap_api_key,
        "units": "metric",
        "exclude": "minutely,alerts",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _cache["data"] = data
    _cache["expires"] = now + CACHE_TTL
    return _format_weather(data)

def _format_weather(data: dict) -> str:
    cur = data["current"]
    daily = data["daily"][0]
    return (
        f"Current: {cur['temp']:.0f}°C, {cur['weather'][0]['description']}. "
        f"High {daily['temp']['max']:.0f}°C, low {daily['temp']['min']:.0f}°C. "
        f"Rain probability: {int(daily.get('pop', 0) * 100)}%."
    )
```

### Pattern 8: Google Places API (New) Nearby Search

**What:** POST to `https://places.googleapis.com/v1/places:searchNearby` with X-Goog-FieldMask header. Returns displayName, rating, formattedAddress, regularOpeningHours.

```python
# velar-backend/app/voice/tools/places_tool.py
import requests
from app.config import settings

async def get_places(query: str) -> str:
    import asyncio
    return await asyncio.to_thread(_get_places_sync, query)

def _get_places_sync(query: str) -> str:
    lat, lon = _geocode_city(settings.places_city)
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": (
            "places.displayName,places.rating,"
            "places.formattedAddress,places.regularOpeningHours"
        ),
    }
    payload = {
        "textQuery": query,  # Use Text Search if Nearby Search doesn't support textQuery
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": 5000.0,
            }
        },
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    places = resp.json().get("places", [])
    if not places:
        return "No places found matching your query."
    results = []
    for p in places[:3]:
        name = p.get("displayName", {}).get("text", "Unknown")
        rating = p.get("rating", "N/A")
        address = p.get("formattedAddress", "")
        is_open = p.get("regularOpeningHours", {}).get("openNow", None)
        if is_open is False:
            continue  # skip closed venues per decision
        results.append(f"{name} (rating: {rating}) — {address}")
    return "\n".join(results) if results else "No open places found nearby."
```

### Pattern 9: launchd Plist

**What:** XML plist placed in `~/Library/LaunchAgents/`. Loaded on user login, restarts on crash.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.velar.daemon</string>

    <key>ProgramArguments</key>
    <array>
        <string>/path/to/venv/bin/python</string>
        <string>/path/to/velar-daemon/daemon.py</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>VELAR_BACKEND_URL</key>
        <string>http://localhost:8000</string>
    </dict>

    <key>KeepAlive</key>
    <true/>

    <key>RunAtLoad</key>
    <true/>

    <key>WorkingDirectory</key>
    <string>/path/to/velar-daemon</string>

    <key>StandardOutPath</key>
    <string>/Users/USERNAME/Library/Logs/velar-daemon.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/USERNAME/Library/Logs/velar-daemon-error.log</string>
</dict>
</plist>
```

**Install commands:**
```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.velar.daemon.plist
launchctl kickstart -k gui/$(id -u)/com.velar.daemon  # force restart
launchctl bootout gui/$(id -u)/com.velar.daemon        # stop
```

### Anti-Patterns to Avoid

- **Calling Google API synchronously in async context:** All Google client library calls are blocking. Always wrap with `asyncio.to_thread()`.
- **Storing OAuth tokens as plain files:** Use `keyring` to store token JSON in macOS Keychain, not ~/.velar/token.json.
- **Passing raw tool result JSON to Claude:** Format tool results as natural-language strings that Claude can directly include in voice responses.
- **Using rumps.App properties from background threads without care:** rumps 0.4.0 added thread-safe title/icon updates — assign `self.title` directly from background threads, but test carefully.
- **Starting audio stream before rumps main loop:** Start the audio stream only after `application_will_finish_launching_` fires, not in `__init__`.
- **Using Places API (Legacy) endpoints:** The new Places API (New) at `places.googleapis.com/v1` is the current standard; Legacy at `maps.googleapis.com` is deprecated.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Wake word detection | Custom ML pipeline | openwakeword hey_jarvis | Requires 200k+ training samples, feature engineering, tflite model training |
| Voice activity detection | Energy/RMS threshold | silero-vad | Energy thresholds fail with HVAC noise, distant speech; Silero handles 6000+ languages |
| macOS token storage | ~/.velar/tokens.json file | keyring (Keychain) | File storage is plaintext; Keychain encrypts at rest and ties to user session |
| Google OAuth2 flow | Manual HTTP redirect loop | InstalledAppFlow | PKCE, state parameter, token refresh — 200+ lines of security-critical code |
| Google Calendar date parsing | Strptime loops | Event["start"].get("dateTime", event["start"].get("date")) | All-day events use "date" key, not "dateTime" — missing this breaks for ~30% of events |
| HTTP geocoding | Manual Nominatim calls | Pre-configured lat/lon from city name | City-level location only needed; store lat/lon at first run; no runtime geocoding needed |
| Tool loop management | Custom while loop | Anthropic SDK messages.create + manual loop | Already implemented — the pattern is 20 lines; don't add unnecessary abstraction |

**Key insight:** The integration surface looks simple but each piece has correctness traps (date formats, token expiry, field masks). The standard libraries handle these edge cases.

---

## Common Pitfalls

### Pitfall 1: openwakeword macOS ARM64 Compatibility
**What goes wrong:** `pip install openwakeword` fails or model inference crashes on Apple Silicon because tflite is Linux-only and onnxruntime-silicon may need specific version.
**Why it happens:** openwakeword's README only documents Linux and Windows platforms explicitly; macOS support is "supported" but undertested.
**How to avoid:** On first install, run `python -c "from openwakeword.model import Model; m = Model(wakeword_models=['hey jarvis']); print('OK')"`. If onnxruntime fails, try `pip install onnxruntime` (not `onnxruntime-silicon`) as the generic wheel often works on ARM64 via Rosetta or native.
**Warning signs:** `ImportError: libonnxruntime` or `RuntimeError: Failed to load model` at startup.

### Pitfall 2: rumps Runs on Main Thread — Audio Thread Deadlock
**What goes wrong:** Starting sounddevice InputStream in a way that blocks before rumps.App.run() causes the process to hang.
**Why it happens:** `rumps.App.run()` calls `NSApplication.run()` which takes over the main thread; any blocking operation before `.run()` deadlocks.
**How to avoid:** Start background threads only from `application_will_finish_launching_` or after a `rumps.Timer` fires post-startup. Never block in `__init__`.
**Warning signs:** The menu bar icon never appears; process hangs silently at startup.

### Pitfall 3: Google Calendar All-Day Events Missing
**What goes wrong:** Code reads `event["start"]["dateTime"]` directly — KeyError for all-day events which use `event["start"]["date"]`.
**Why it happens:** Google Calendar API returns different key names for timed vs. all-day events.
**How to avoid:** Always use `event["start"].get("dateTime", event["start"].get("date"))`.
**Warning signs:** Tool crashes when user has all-day events (common: birthdays, vacations).

### Pitfall 4: OpenWeatherMap API 3.0 Requires Separate Subscription
**What goes wrong:** API key from a free account returns 401 Unauthorized for One Call 3.0 endpoint.
**Why it happens:** One Call 3.0 is on "One Call by Call" subscription — not included in the default free tier.
**How to avoid:** Create the "One Call by Call" subscription at openweathermap.org/api. It has a 1,000 call/day free tier but requires explicit subscription activation.
**Warning signs:** HTTP 401 with `{"cod":401,"message":"...subscription..."}`.

### Pitfall 5: Google Places API Field Mask Required
**What goes wrong:** POST to Nearby Search returns HTTP 400 with "FieldMask is required".
**Why it happens:** The new Places API (unlike the legacy API) requires explicit field selection via X-Goog-FieldMask header; no default response fields exist.
**How to avoid:** Always include `X-Goog-FieldMask` header with at least `places.displayName`.
**Warning signs:** 400 error on first call with no obvious typos in the URL.

### Pitfall 6: AppleScript osascript Text Injection
**What goes wrong:** User says a reminder text containing quotes → AppleScript syntax error.
**Why it happens:** Inline `-e` script embeds user text directly; unescaped quotes break the script.
**How to avoid:** Escape double quotes in `text` parameter: `text.replace('"', '\\"')`. Or write script to a temp file and run `osascript /tmp/script.applescript` to avoid shell escaping.
**Warning signs:** osascript returncode != 0 with "Expected end of line but found ..." error.

### Pitfall 7: Token Refresh Race Condition
**What goes wrong:** If two tool calls happen concurrently, both may attempt token refresh simultaneously, causing one to overwrite the other's stored token with an old one.
**Why it happens:** OAuth2 credentials.refresh() is not thread-safe.
**How to avoid:** Add a threading.Lock() around the `_get_credentials()` call in calendar_tool.py.
**Warning signs:** Intermittent "Token expired" errors after long uptime.

### Pitfall 8: Tool Responses Must Be Voice-Optimized Before Returning
**What goes wrong:** Tool returns raw JSON or multi-line lists → Claude reads it as markdown → TTS produces "dash space item one dash space item two".
**Why it happens:** Claude may pass tool result text through to the voice response without reformatting if the result is already readable.
**How to avoid:** Format tool results as natural prose strings (not JSON, not lists). E.g., `"Current temp: 18°C, partly cloudy. High 22°C. 30% chance of rain."` Claude then synthesizes this into a natural sentence.
**Warning signs:** TTS output sounds robotic or reads markdown syntax aloud.

---

## Code Examples

### Silero VAD for Speech Boundary Detection (16kHz, chunk-based)
```python
# Source: https://pypi.org/project/silero-vad/ (version 6.2.1)
from silero_vad import load_silero_vad
import torch

vad_model = load_silero_vad()  # loads once, reuse across calls

def is_speech(audio_chunk_int16: bytes, sample_rate=16000) -> bool:
    """Returns True if chunk contains speech. audio_chunk is raw int16 PCM bytes."""
    import numpy as np
    arr = np.frombuffer(audio_chunk_int16, dtype=np.int16).astype(np.float32) / 32768.0
    tensor = torch.from_numpy(arr).unsqueeze(0)
    prob = vad_model(tensor, sample_rate).item()
    return prob > 0.5
```

### Post-Wake Audio Capture with VAD + Timeout
```python
# audio_capture.py — record until silence or timeout
import numpy as np
import sounddevice as sd
import time

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms
MAX_RECORDING_SECS = 8
SILENCE_TIMEOUT_SECS = 1.5
NO_SPEECH_TIMEOUT_SECS = 3

def capture_utterance(vad_model) -> bytes | None:
    """Record audio until speech ends or timeout. Returns int16 PCM bytes or None."""
    frames = []
    speech_started = False
    last_speech_time = None
    start_time = time.time()

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=CHUNK_SAMPLES) as stream:
        while True:
            elapsed = time.time() - start_time
            if elapsed > MAX_RECORDING_SECS:
                break

            chunk, _ = stream.read(CHUNK_SAMPLES)
            chunk_bytes = chunk.tobytes()
            frames.append(chunk_bytes)

            if is_speech(chunk_bytes):
                speech_started = True
                last_speech_time = time.time()
            elif speech_started:
                silence_secs = time.time() - last_speech_time
                if silence_secs >= SILENCE_TIMEOUT_SECS:
                    break
            elif not speech_started and elapsed > NO_SPEECH_TIMEOUT_SECS:
                return None  # No speech at all → play cancelled tone

    if not speech_started:
        return None
    return b"".join(frames)
```

### Complete launchctl Workflow
```bash
# Install plist
cp com.velar.daemon.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.velar.daemon.plist

# Check status
launchctl print gui/$(id -u)/com.velar.daemon

# View logs
tail -f ~/Library/Logs/velar-daemon.log

# Restart
launchctl kickstart -k gui/$(id -u)/com.velar.daemon

# Uninstall
launchctl bootout gui/$(id -u)/com.velar.daemon
rm ~/Library/LaunchAgents/com.velar.daemon.plist
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Google Places API (Legacy) at maps.googleapis.com | Google Places API (New) at places.googleapis.com/v1 | 2023 | New API requires POST + field masks; no GET; different URL structure |
| One Call API 2.5 (free, unlimited) | One Call API 3.0 (separate "One Call by Call" subscription) | 2022-2023 | Requires explicit subscription activation even for free tier |
| launchctl load (deprecated) | launchctl bootstrap gui/UID (macOS 10.15+) | macOS Catalina 2019 | Old `launchctl load` still works but prints deprecation warning |
| token.pickle storage for Google credentials | token.json via creds.to_json() | google-auth ~1.x → 2.x | Pickle has security risks; JSON is the official approach |
| openwakeword tflite default (Linux) | openwakeword onnxruntime (macOS/Windows) | N/A | macOS must use onnxruntime; tflite not available |

**Deprecated/outdated:**
- `silero-vad` pre-v4 API (`torch.hub.load()` pattern): replaced by `from silero_vad import load_silero_vad` in the pip package
- Google Places `type` parameter in legacy Nearby Search: replaced by `includedTypes` array in New API
- `launchctl load ~/Library/LaunchAgents/foo.plist`: deprecated; use `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/foo.plist`

---

## Open Questions

1. **openwakeword hey_jarvis False Positive Rate**
   - What we know: No formal performance metrics published for the model; trained on synthetic data
   - What's unclear: How many false triggers per hour in real office environments; whether sensitivity=0.5 is appropriate
   - Recommendation: Start with sensitivity=0.5 in Wave 1; add a log of trigger events; adjust empirically after dogfooding

2. **openwakeword macOS ARM64 onnxruntime compatibility**
   - What we know: macOS is listed as supported; tflite is Linux-only; onnxruntime is the macOS backend
   - What's unclear: Whether standard `onnxruntime` pip wheel works natively on Apple Silicon or requires Rosetta
   - Recommendation: Wave 0 installation validation task — `python -c "from openwakeword.model import Model; m = Model(wakeword_models=['hey jarvis'])"` on target hardware before building the pipeline

3. **rumps thread-safety for title/icon updates**
   - What we know: rumps 0.4.0 release notes mention "event hooks" but documentation is sparse
   - What's unclear: Whether `app.title = "..."` from a non-main thread triggers AppKit thread safety assertions on macOS Sonoma/Sequoia
   - Recommendation: Use `rumps.App.title` assignment from background thread in Wave 1 and test; if crashes observed, wrap with `objc.callAfterDelay(0, lambda: ...)` or use a `rumps.Timer` to poll a shared state variable

4. **Google Places Nearby Search vs. Text Search for unstructured queries**
   - What we know: Nearby Search (New) uses `includedTypes` for category filtering; Text Search supports free-form text queries
   - What's unclear: `get_places(query="good coffee shop")` needs text search, not category filter — which endpoint to use
   - Recommendation: Use Text Search (New) at `https://places.googleapis.com/v1/places:searchText` with `textQuery` + `locationBias.circle`; it handles natural language better than `includedTypes`

5. **Backend tool execution location — daemon vs. backend**
   - What we know: CONTEXT.md says "Backend executes tools, returns results back to Claude"
   - What's unclear: Google Calendar OAuth tokens are stored on the Mac; how does the backend (potentially running remotely later) access macOS Keychain or call AppleScript?
   - Recommendation: For Phase 4 (local backend on same Mac), this works fine. Document in code that Calendar + Reminders tools are Mac-local; when backend moves to cloud (Phase 5+), these tools must become daemon-side. Plan accordingly.

---

## Sources

### Primary (HIGH confidence)
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use — Anthropic tool_use API: tool definitions, tool_use stop_reason, tool_result pattern, tool runner beta
- https://developers.google.com/calendar/api/quickstart/python — Google Calendar API Python quickstart: InstalledAppFlow, token.json pattern, events().list() call
- https://openweathermap.org/api/one-call-3 — OpenWeatherMap One Call 3.0: endpoint URL, parameters, subscription requirement
- https://developers.google.com/maps/documentation/places/web-service/nearby-search — Places API (New) Nearby Search: POST format, field mask, opening hours field name
- https://pypi.org/project/openwakeword/ — openwakeword 0.6.0: installation, hey_jarvis model, 16kHz/80ms audio requirements
- https://pypi.org/project/silero-vad/ — silero-vad 6.2.1: load_silero_vad(), chunk processing, MIT license
- https://pypi.org/project/keyring/ — keyring 25.7.0: macOS Keychain integration, set_password/get_password API
- https://pypi.org/project/rumps/ — rumps 0.4.0: App class, title/icon, clicked decorator

### Secondary (MEDIUM confidence)
- https://github.com/dscripka/openWakeWord/blob/main/docs/models/hey_jarvis.md — hey_jarvis model architecture, training data, acoustic echo cancellation note
- https://andypi.co.uk/2023/02/14/how-to-run-a-python-script-as-a-service-on-mac-os/ — launchd plist XML format with KeepAlive, RunAtLoad, StandardOutPath
- https://github.com/jaredks/rumps/blob/master/examples/example_dynamic_title_icon.py — Dynamic title/icon update pattern from rumps examples

### Tertiary (LOW confidence)
- WebSearch results for openwakeword macOS ARM64 — No official documentation found; compatibility assumed from onnxruntime being cross-platform; requires empirical validation
- WebSearch results for rumps thread safety on macOS Sonoma/Sequoia — No official documentation found; flagged as open question

---

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM — Core libraries verified via official PyPI/docs; openwakeword macOS ARM64 compatibility not officially documented
- Architecture: MEDIUM — Thread model pattern verified; tool_use loop from official Anthropic docs (HIGH); rumps thread-safety gap (LOW)
- Pitfalls: MEDIUM — Most pitfalls verified from official API docs (field masks, all-day events, subscription tiers); AppleScript injection from general subprocess patterns

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (stable APIs; openwakeword is slow-moving)
