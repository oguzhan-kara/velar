---
phase: 04-mac-daemon
plan: "03"
subsystem: voice-tools
tags: [tools, anthropic, calendar, weather, reminders, places, tool-use]
dependency_graph:
  requires:
    - 02-02 (conversation.py Claude client)
    - 02-03 (streaming pipeline + router)
    - 03-01 (memory system + settings pattern)
  provides:
    - TOOL_DEFINITIONS list (4 tools) consumable by any Claude client
    - execute_tool() dispatcher for calendar, weather, reminders, places
    - Active Anthropic tool_use loop in run_conversation
  affects:
    - velar-backend/app/voice/conversation.py (tool loop activated)
    - All /voice and /chat callers gain real-world context tools
tech_stack:
  added:
    - google-auth-oauthlib>=1.0 (Google Calendar OAuth2 flow)
    - google-api-python-client>=2.100 (Calendar v3 API client)
    - google-auth-httplib2>=0.2 (HTTP transport for google-auth)
    - keyring>=25.0 (macOS Keychain token storage)
    - requests>=2.31 (HTTP for OWM + Google Places)
  patterns:
    - Anthropic tool_use loop (while True until stop_reason == "end_turn")
    - Per-tool try/except isolation in execute_tool() dispatcher
    - 30-minute in-process cache dict for weather (avoids excessive API calls)
    - threading.Lock for Google OAuth2 token refresh (prevents race conditions)
    - AppleScript via subprocess with double-quote escaping (injection prevention)
    - Google Places API (New) POST with X-Goog-FieldMask header (required field)
    - Cache-before-import pattern in weather_tool for testability without .env
key_files:
  created:
    - velar-backend/app/voice/tools/__init__.py
    - velar-backend/app/voice/tools/registry.py
    - velar-backend/app/voice/tools/calendar_tool.py
    - velar-backend/app/voice/tools/weather_tool.py
    - velar-backend/app/voice/tools/reminder_tool.py
    - velar-backend/app/voice/tools/places_tool.py
    - velar-backend/tests/test_tools.py
  modified:
    - velar-backend/app/voice/conversation.py (tool loop + user_id param)
    - velar-backend/app/config.py (5 new Phase 4 fields)
    - velar-backend/requirements.txt (5 new packages)
    - velar-backend/tests/test_conversation.py (mock.type = "text" fix)
    - velar-backend/tests/test_language.py (mock.type = "text" + stop_reason fix)
    - velar-backend/tests/test_voice_e2e.py (mock.type = "text" + stop_reason fix)
decisions:
  - "registry.py wraps each tool call in try/except so individual tool failures return prose strings rather than raising exceptions that crash the loop"
  - "weather_tool defers settings import until after cache check — enables unit tests to pre-populate cache without needing a .env file"
  - "places_tool uses Google Places Text Search endpoint (searchText) instead of Nearby Search — Text Search supports keyword queries better"
  - "places_tool falls back to Google Geocoding API when OWM key is not set"
  - "Existing tests updated to set mock_content.type = 'text' and stop_reason = 'end_turn' — required for new tool loop block.type check"
metrics:
  duration: 7 min
  completed_date: "2026-03-02"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 6
---

# Phase 4 Plan 03: Integration Tools + Tool Loop Summary

**One-liner:** Anthropic tool_use loop activated in conversation.py with 4 tools (Google Calendar OAuth2, OpenWeatherMap 30-min cache, AppleScript Reminders, Google Places API New).

## What Was Built

### Tool Registry (registry.py)

`TOOL_DEFINITIONS` list with exactly 4 Anthropic tool_use schema entries. `execute_tool()` dispatcher routes by name with per-tool try/except isolation — any tool failure returns a prose fallback string rather than crashing the conversation loop.

### Calendar Tool (calendar_tool.py)

Google Calendar OAuth2 flow with macOS Keychain token storage via `keyring`. threading.Lock prevents concurrent token refresh races. All-day event handling uses `event["start"].get("dateTime", event["start"].get("date"))` pattern to avoid the common pitfall of missing ~30% of events.

### Weather Tool (weather_tool.py)

OpenWeatherMap One Call 3.0 with 30-minute in-process cache. Cache check happens before the settings import so unit tests can pre-populate the cache without needing a valid `.env` file. City geocoding cached in module-level dict for process lifetime.

### Reminder Tool (reminder_tool.py)

AppleScript via `osascript -e` subprocess with `text.replace('"', '\\"')` escaping to prevent AppleScript injection. Returns confirmation prose for Claude to include in the voice response.

### Places Tool (places_tool.py)

Google Places API (New) at `places.googleapis.com/v1/places:searchText`. Uses required `X-Goog-FieldMask` header (omitting causes HTTP 400). Filters closed venues (`openNow is False`). Falls back to Google Geocoding if OWM key unavailable.

### Conversation Loop (conversation.py)

Replaced single `asyncio.to_thread(client.messages.create, ...)` call with `while True` loop. Passes `TOOL_DEFINITIONS` on every call. Handles `stop_reason == "end_turn"` (extract text block) and `stop_reason == "tool_use"` (execute tools, append results, continue). Unexpected stop_reasons log a warning and bail gracefully. Added `user_id: str | None = None` parameter for Phase 5+ user-scoped tools.

## Test Results

All 5 unit tests in `test_tools.py` pass without real API keys:
- `test_tool_definitions_structure` — 4 tools with correct schema
- `test_reminder_quote_escaping` — double-quote escaping verified
- `test_weather_cache_hit` — cache bypasses HTTP requests
- `test_execute_tool_unknown_raises` — ValueError for unknown names
- `test_execute_tool_routes_correctly` — dispatcher routes to correct module

Full suite: 68 passed, 7 skipped, 4 pre-existing errors (test_auth.py SQLAlchemy URL issue unrelated to this plan).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] weather_tool settings import before cache check**
- **Found during:** Task 2 (test_weather_cache_hit failure)
- **Issue:** `_get_weather_sync()` imported `from app.config import settings` at the top of the function, BEFORE the cache check. This caused pydantic-settings ValidationError when tests pre-populated the cache and called `get_weather()` without a `.env` file.
- **Fix:** Moved the settings import to after the cache check. Cache hits now return immediately without touching settings.
- **Files modified:** `velar-backend/app/voice/tools/weather_tool.py`
- **Commit:** c99a3d6

**2. [Rule 1 - Bug] Existing test mocks incompatible with new tool loop**
- **Found during:** Task 2 (3 test files, 4 failing tests)
- **Issue:** The new tool loop checks `block.type == "text"` to extract the response text. Existing tests used bare `MagicMock()` for content blocks, so `mock_content.type` returned a new `MagicMock` instance (not the string `"text"`), causing the loop to return `""` instead of the mock text. Additionally, some mocks did not set `stop_reason = "end_turn"`, causing the bail-out branch to fire.
- **Fix:** Added `mock_content.type = "text"` and `mock_response.stop_reason = "end_turn"` to all affected mock setups in test_conversation.py, test_language.py, and test_voice_e2e.py.
- **Files modified:** `tests/test_conversation.py`, `tests/test_language.py`, `tests/test_voice_e2e.py`
- **Commit:** c99a3d6

## Self-Check: PASSED

All created files verified present on disk. Both task commits (5468ddb, c99a3d6) confirmed in git log.
