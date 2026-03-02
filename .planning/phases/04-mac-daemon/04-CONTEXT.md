# Phase 4: Mac Daemon and Integrations - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

VELAR runs as a persistent background process on Mac: wake word "Hey VELAR" triggers audio capture → voice pipeline → spoken response. Real-world context tools (calendar, weather, places, reminders) are added to the Claude tool loop. The daemon handles hardware interaction; the FastAPI backend (Phase 2) handles STT/Claude/TTS. This phase does not build a GUI beyond a menu bar status icon.

</domain>

<decisions>
## Implementation Decisions

### Daemon Architecture
- Thin client model: daemon owns hardware (mic, speakers) and wake word; FastAPI backend owns STT/Claude/TTS
- Daemon sends captured audio to existing `/api/v1/voice` endpoint — no duplicated pipeline logic
- Daemon is a Python process launched via launchd for boot persistence
- Library: `rumps` for menu bar icon (Python-native, no Objective-C bridge required)
- Menu bar icon states: gray dot (idle), pulsing blue dot (listening), spinning (processing)
- Daemon designed for local backend (same Mac in dev) but backend URL is configurable via env

### Wake Word Behavior
- Model: openwakeword with `hey_jarvis` pretrained model — closest phonetically to "Hey VELAR"; custom model training deferred
- On wake: 200ms metallic chime plays immediately to confirm listening started
- Audio capture: sounddevice continuous stream, Silero VAD (reuse Phase 2 params) detects speech boundaries
- Auto-timeout: 8 seconds max recording, stops after 1.5s silence post-speech
- If no speech detected within 3s of wake: short "cancelled" tone → return to idle (no API call made)
- Menu bar includes "Pause wake word" toggle for silent work sessions — icon shows muted state
- macOS automatically shows mic indicator in menu bar when sounddevice opens stream — no manual handling

### Calendar Integration
- Google Calendar only in Phase 4 — Apple Calendar requires native EventKit (macOS Swift), deferred to Phase 6
- OAuth2 via `google-auth-oauthlib`; tokens stored in macOS Keychain via `keyring` library
- First-run setup: daemon prints auth URL to stdout, opens browser automatically via `webbrowser.open()`; token persists after one-time flow
- Token refresh: silent background refresh when <5 minutes to expiry
- Lookahead defaults: `get_calendar_events(days_ahead=1)` for today, `days_ahead=7` for week view
- Only events from the primary calendar (default); multi-calendar support deferred

### Weather Integration
- Provider: OpenWeatherMap One Call API 3.0 — current + hourly + 7-day in one call
- Location: user's current city stored in backend user profile (set once); no live GPS in daemon
- Cache: 30-minute TTL in-process cache — weather doesn't need to be real-time for most queries
- Response includes: current temp, condition, high/low, precipitation probability for next 24h

### Reminders Tool
- macOS Reminders via AppleScript — no OAuth required, works out of the box on Mac
- `set_reminder(text: str, minutes_from_now: int)`: creates reminder with due date = now + N minutes
- Reminders appear in macOS Reminders.app and sync to iPhone via iCloud automatically
- No list selection — adds to default Reminders list

### Places Integration
- Google Places API (Nearby Search + Place Details)
- Location: same city-level location as weather (not GPS tracking)
- Tool: `get_places(query: str)` — returns top 3 results with name, rating, address
- Results include opening hours when available (closed venues filtered by default)

### Tool Invocation in Claude Loop
- Four tools registered in Phase 4: `get_calendar_events`, `get_weather`, `set_reminder`, `get_places`
- Claude uses tool_use natively (Anthropic tool use API) — daemon passes tool definitions to backend with each voice request
- Backend executes tools, returns results back to Claude for response synthesis
- Voice responses for tool results: 1-3 sentences, optimized for listening (no lists, no markdown)
- Fallback: if tool call fails, Claude responds "I couldn't fetch that right now" — no retries in voice loop

### Daemon Lifecycle
- launchd plist in `~/Library/LaunchAgents/` — loads on user login, restarts on crash
- Graceful shutdown: SIGTERM handler stops audio capture, closes sounddevice stream, saves state
- Backend connectivity check on startup: if backend unreachable, menu bar shows warning icon, retries every 30s in background
- Daemon config: `~/.velar/daemon.json` — backend URL, wake word sensitivity, audio device index

</decisions>

<specifics>
## Specific Ideas

- "Hey VELAR" must feel like Jarvis — instant, not laggy; the chime feedback is critical for this illusion
- Daemon is thin by design: all intelligence stays in the backend so future clients (iPhone, Watch) share the same tool infrastructure
- AppleScript for Reminders is pragmatic: no OAuth2 friction for the most common use case (quick reminders)
- Tool responses must be voice-first — Claude must synthesize calendar/weather data into natural sentences, not read out raw JSON

</specifics>

<deferred>
## Deferred Ideas

- Apple Calendar via EventKit — Phase 6 (iPhone App, requires native Swift/macOS)
- Custom "Hey VELAR" wake word model training — post-Phase 4 (openwakeword hey_jarvis suffices)
- Live GPS location for weather/places — Phase 6 (iPhone provides GPS)
- Hotkey activation as wake word alternative — can add later if wake word reliability is poor
- Multi-calendar support (work + personal) — Phase 5/6
- Daemon system tray on Windows/Linux — out of scope for v1 (Mac only)

</deferred>

---

*Phase: 04-mac-daemon*
*Context gathered: 2026-03-02*
