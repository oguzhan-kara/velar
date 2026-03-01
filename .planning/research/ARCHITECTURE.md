# Architecture Research

**Domain:** Proactive personal AI assistant (multi-device, voice-first)
**Researched:** 2026-03-01
**Confidence:** MEDIUM — established patterns from well-known domains; network tools unavailable, based on training knowledge of stable technologies (FastAPI, Firebase, Claude API tool use, APNs, WebSockets). Flag LOW-confidence items for phase-specific verification.

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                  │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  Mac Service │  │ iPhone App   │  │   Apple Watch App        │   │
│  │  (Python)    │  │ (Flutter)    │  │   (Swift/WatchKit)       │   │
│  │              │  │              │  │                          │   │
│  │ Wake word    │  │ Voice input  │  │ Complication display     │   │
│  │ detection    │  │ Chat UI      │  │ Quick commands           │   │
│  │ Audio capture│  │ Push recv    │  │ Briefing glance          │   │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘   │
└─────────┼────────────────┼──────────────────────── ┼──────────────── ┘
          │                │                          │
          │  HTTPS/WS      │  HTTPS/WS                │ (via iPhone BLE
          │                │                          │  or APNs proxy)
          ▼                ▼                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      API GATEWAY LAYER                               │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                   FastAPI Backend                              │  │
│  │                                                                │  │
│  │   /voice        - Audio upload → STT → AI → TTS → response    │  │
│  │   /chat         - Text in → AI → text out (streaming SSE)     │  │
│  │   /briefing     - Scheduled morning digest trigger            │  │
│  │   /memory       - CRUD for personal facts / life graph        │  │
│  │   /proactive    - Scheduler endpoint for push triggers        │  │
│  │   /ws/{device}  - WebSocket channel per device                │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     INTELLIGENCE LAYER                               │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  Claude API  │  │  Whisper STT │  │   TTS Service            │   │
│  │  (Reasoning) │  │  (local or   │  │   (ElevenLabs or         │   │
│  │  Tool use    │  │   API)       │  │    Edge TTS)             │   │
│  │  Streaming   │  │              │  │                          │   │
│  └──────┬───────┘  └──────────────┘  └──────────────────────────┘   │
│         │                                                            │
│         │ Tool calls                                                 │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    Tool Executor                              │    │
│  │  get_weather | get_calendar | get_memory | send_notification  │    │
│  │  search_places | get_health_data | draft_message | ...        │    │
│  └──────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                     │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  Firestore   │  │  Cloud       │  │   Redis / APScheduler    │   │
│  │  (User data, │  │  Storage     │  │   (Job queue, proactive  │   │
│  │  memory,     │  │  (Audio      │  │    scheduler, caching)   │   │
│  │  life graph) │  │   files)     │  │                          │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   NOTIFICATION LAYER                                  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │   Firebase Cloud Messaging (FCM) → APNs → iOS / Mac / Watch   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Mac Service | Wake word detection, audio capture, local voice pipeline | Python daemon + `pvporcupine` (Picovoice) wake word, `pyaudio` capture |
| iPhone App | Primary user interface, voice input, push notification display | Flutter + `flutter_sound` or `record` package |
| Apple Watch App | Quick briefing glance, short voice commands, complication | Swift + WatchKit, WCSession for iPhone bridge |
| FastAPI Backend | All AI orchestration, session management, routing | Python 3.11+, FastAPI with async, Uvicorn |
| Claude API + Tools | Core reasoning, intent, proactive suggestions | Anthropic Python SDK, tool use loop, streaming |
| Whisper STT | Convert audio → text; high accuracy, bilingual | `faster-whisper` (local) or OpenAI Whisper API |
| TTS Service | Convert AI text response → premium voice audio | ElevenLabs API for production; Edge TTS as fallback |
| Tool Executor | Execute Claude tool calls against real data/services | Python functions registered as Claude tools |
| Firestore | Store user profile, memory facts, conversation history | Firebase Firestore (NoSQL, real-time sync) |
| Proactive Scheduler | Trigger timed checks (morning briefing, reminders) | APScheduler (in-process) or Cloud Scheduler |
| FCM / APNs | Deliver push notifications to all Apple devices | Firebase Admin SDK → FCM → APNs gateway |

---

## Recommended Project Structure

```
velar-backend/
├── main.py                    # FastAPI app entry point
├── config.py                  # Settings (env vars, API keys)
├── routers/
│   ├── voice.py               # POST /voice — audio upload + full pipeline
│   ├── chat.py                # POST /chat — text in, streaming SSE out
│   ├── memory.py              # CRUD /memory — personal facts
│   ├── briefing.py            # POST /briefing — trigger morning digest
│   └── proactive.py           # Internal proactive scheduler endpoints
├── services/
│   ├── claude_service.py      # Claude API wrapper, tool use loop
│   ├── stt_service.py         # Whisper STT (local or API)
│   ├── tts_service.py         # ElevenLabs / Edge TTS abstraction
│   ├── memory_service.py      # Memory read/write, life graph queries
│   ├── notification_service.py # FCM push notification dispatch
│   └── scheduler_service.py   # APScheduler setup + job definitions
├── tools/
│   ├── registry.py            # Claude tool definitions (JSON schema)
│   ├── weather_tool.py        # get_weather implementation
│   ├── calendar_tool.py       # get_calendar implementation
│   ├── memory_tool.py         # get_memory / store_memory implementation
│   ├── places_tool.py         # search_places implementation
│   ├── notification_tool.py   # send_notification implementation
│   └── health_tool.py         # get_health_data (via HealthKit bridge)
├── models/
│   ├── user.py                # User profile schema
│   ├── memory.py              # Memory fact schema (entity, attribute, value)
│   ├── conversation.py        # Conversation turn schema
│   └── notification.py        # Push notification payload schema
├── db/
│   ├── firestore.py           # Firestore client + collection helpers
│   └── cache.py               # Redis / in-memory cache layer
└── tests/

velar-mac/
├── main.py                    # Mac daemon entry point
├── wake_word.py               # Picovoice Porcupine wake word loop
├── audio_capture.py           # Microphone capture + VAD (voice activity)
├── api_client.py              # HTTP client to FastAPI backend
└── tray_app.py                # Optional: macOS system tray UI

velar-mobile/  (Flutter)
├── lib/
│   ├── main.dart
│   ├── services/
│   │   ├── api_service.dart    # HTTP + WebSocket client
│   │   ├── audio_service.dart  # Record + playback
│   │   └── push_service.dart   # FCM push handler
│   ├── screens/
│   │   ├── home_screen.dart
│   │   ├── voice_screen.dart
│   │   └── memory_screen.dart
│   └── watch/
│       └── watch_bridge.dart   # WCSession bridge to Watch

velar-watch/  (Swift / WatchKit)
├── VelarWatch WatchKit App/
│   ├── ContentView.swift       # Main watch UI
│   ├── VoiceInputView.swift    # Dictation + quick commands
│   └── BriefingView.swift      # Morning briefing glance
└── VelarWatch WatchKit Extension/
    ├── ExtensionDelegate.swift
    ├── WatchConnectivity.swift  # WCSession to iPhone
    └── ComplicationController.swift
```

### Structure Rationale

- **routers/:** HTTP endpoint definitions only — no business logic; kept thin
- **services/:** All business logic and external API wrappers; testable in isolation
- **tools/:** Claude tool implementations separated from service layer; each tool is independently testable and swappable
- **models/:** Pydantic models for all data shapes; single source of truth for data contracts
- **db/:** All persistence operations behind an abstraction layer — swappable Firestore vs Supabase without rewriting services

---

## Architectural Patterns

### Pattern 1: Claude Tool Use Loop (Agentic Pattern)

**What:** Claude does not call APIs directly. Instead, the backend runs a loop: call Claude with tools defined → Claude returns a tool_use block → backend executes the tool → feed result back to Claude → repeat until Claude returns a final text response.

**When to use:** Every interaction that requires real-world data (weather, calendar, memory lookup, health stats). This is the core reasoning pattern for VELAR.

**Trade-offs:** Adds latency per tool call (1-3 round trips typical); but enables Claude to chain reasoning over real data, which is the product's core value.

**Example:**
```python
async def run_claude_with_tools(messages: list, tools: list) -> str:
    while True:
        response = anthropic.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            tools=tools,
            messages=messages,
        )
        if response.stop_reason == "end_turn":
            return response.content[0].text

        # Claude wants to call a tool
        tool_calls = [b for b in response.content if b.type == "tool_use"]
        tool_results = []
        for call in tool_calls:
            result = await execute_tool(call.name, call.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": str(result),
            })

        # Feed results back
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
```

### Pattern 2: Voice Pipeline — Audio → STT → AI → TTS → Audio

**What:** A linear pipeline for voice interactions. Audio arrives at the backend as a raw file (WAV/m4a), passes through STT, then Claude, then TTS, and the audio response is streamed back to the client.

**When to use:** All voice-first interactions from Mac (daemon) and iPhone (push-to-talk or wake word).

**Trade-offs:** End-to-end latency is the product's biggest UX challenge. Each step adds 300ms–2s. Target round-trip under 4s for perceived responsiveness. Local Whisper (faster-whisper) cuts STT to ~200ms; ElevenLabs adds ~500ms. Streaming TTS + streaming Claude response is the correct optimization path.

**Example:**
```python
async def voice_pipeline(audio_bytes: bytes, user_id: str) -> AsyncGenerator[bytes, None]:
    # Step 1: STT
    transcript = await stt_service.transcribe(audio_bytes)  # ~200ms local

    # Step 2: AI reasoning (streaming)
    text_chunks = []
    async for chunk in claude_service.stream_response(transcript, user_id):
        text_chunks.append(chunk)
        # Optional: start TTS as text arrives (sentence chunking)

    full_text = "".join(text_chunks)

    # Step 3: TTS
    audio_response = await tts_service.synthesize(full_text)
    yield audio_response
```

### Pattern 3: Proactive Scheduler — Event-Driven Push

**What:** A background scheduler (APScheduler or Cloud Scheduler) triggers proactive checks independent of user requests. On trigger, the scheduler runs a "proactive evaluation" — calls Claude with context about the user's day — and Claude decides whether to push a notification.

**When to use:** Morning briefing, weather alerts, calendar reminders, passive suggestions ("you haven't eaten since 6am"). This pattern is what makes VELAR "proactive" rather than reactive.

**Trade-offs:** Needs careful throttling — too many notifications destroys trust. Claude should be the decision-maker on whether to notify (not hardcoded rules), but you need rate limits to prevent abuse.

**Example:**
```python
@scheduler.scheduled_job("cron", hour=7, minute=0, timezone="Europe/Istanbul")
async def morning_briefing_job():
    for user_id in await get_active_users():
        context = await gather_morning_context(user_id)  # weather, calendar, health, memory
        decision = await claude_service.proactive_check(context, user_id)
        if decision.should_notify:
            await notification_service.push(
                user_id=user_id,
                title="Good morning",
                body=decision.summary,
                target_device="all",
            )
```

### Pattern 4: Memory Extraction — Passive Learning Loop

**What:** After every conversation turn, a lightweight Claude call extracts structured facts ("user mentioned they are lactose intolerant", "user's sister birthday is March 15"). These are stored as typed memory facts in Firestore with entity-attribute-value triples.

**When to use:** Always, after every completed interaction. This is the long-term differentiator — VELAR gets smarter over time.

**Trade-offs:** Adds ~300ms post-processing per turn (run async, don't block response). Storage accumulates; need periodic consolidation or deduplication job.

**Example:**
```python
# Memory fact schema
class MemoryFact(BaseModel):
    entity: str        # "user", "sister", "coffee_shop_beşiktaş"
    attribute: str     # "dietary_restriction", "birthday", "last_visited"
    value: str         # "lactose_intolerant", "2026-03-15", "2026-02-20"
    confidence: float  # 0.0-1.0 extracted by Claude
    source: str        # "conversation_2026-03-01"
    created_at: datetime

async def extract_memory_facts(conversation_text: str, user_id: str):
    facts = await claude_service.extract_facts(conversation_text)
    for fact in facts:
        await memory_service.upsert_fact(user_id, fact)
```

### Pattern 5: Multi-Device Session Routing

**What:** Each device registers with the backend via a WebSocket or FCM device token. When an AI response should go to a specific device (e.g., Watch for briefing glance, iPhone for full detail), the backend routes to the registered device token. Cross-device handoff is triggered when a session migrates (e.g., started on Mac, continue on iPhone).

**When to use:** All notification dispatch. Device registry in Firestore with user_id → [device_tokens].

**Trade-offs:** Apple Watch does not receive FCM directly — notifications route through iPhone via APNs and WatchKit shares the notification payload. Watch complications need a native WatchKit extension.

---

## Data Flow

### Request Flow: Voice Interaction (Mac)

```
[User says "Hey VELAR"]
    ↓
[Mac Daemon: wake word detected (Porcupine)]
    ↓
[Mac Daemon: capture audio until silence (VAD)]
    ↓ (POST /voice with audio blob + user_id + device="mac")
[FastAPI: /voice router]
    ↓
[STT Service: Whisper → transcript text]
    ↓
[Claude Service: tool use loop with memory + context]
    ↓ (tool calls as needed)
[Tool Executor: get_weather, get_calendar, get_memory, ...]
    ↓
[Claude Service: final text response]
    ↓
[TTS Service: ElevenLabs → audio bytes]
    ↓ (streaming audio response)
[Mac Daemon: play audio via speakers]
    ↓ (async, background)
[Memory Service: extract + store facts from this turn]
```

### Request Flow: Proactive Push Notification

```
[APScheduler: cron trigger (e.g., 07:00 local time)]
    ↓
[Scheduler Service: gather_morning_context(user_id)]
  → Firestore: user profile, memory facts, recent history
  → Weather Tool: current + forecast
  → Calendar Tool: today's events
  → Health Tool: sleep + activity (bridged from HealthKit)
    ↓
[Claude Service: proactive_briefing(context)]
  → Returns: {should_notify: true, title: "...", body: "...", audio_url: "..."}
    ↓
[Notification Service: FCM dispatch → APNs]
    ↓
[iPhone: receives push → plays audio briefing or shows card]
    ↓ (WatchKit notification forwarding)
[Apple Watch: shows glanceable summary on complication]
```

### Request Flow: Cross-Device Session Handoff

```
[User starts voice session on Mac]
    ↓
[Backend: create session_id, store in Firestore with device="mac"]
    ↓
[User picks up iPhone mid-session]
    ↓
[iPhone App: POST /session/transfer {session_id, new_device="iphone"}]
    ↓
[Backend: fetch conversation history from Firestore by session_id]
    ↓
[Backend: continue Claude context with full history on new device]
    ↓
[iPhone receives response — conversation continues seamlessly]
```

### State Management: Memory Life Graph

```
[Every conversation turn]
    ↓
[Memory Extractor (async Claude call)]
    ↓
[MemoryFact: entity + attribute + value + confidence]
    ↓
[Firestore: /users/{uid}/memory/{fact_id}]
    ↓ (on next interaction)
[Memory Retrieval: semantic search or entity lookup]
    ↓
[System Prompt Injection: "Known facts about user: [relevant facts]"]
    ↓
[Claude: responds with personalized context]
```

### Key Data Flows Summary

1. **Voice loop:** Audio → STT → Claude tool loop → TTS → Audio (all in-request, synchronous to user)
2. **Proactive push:** Scheduler → Context gather → Claude decision → FCM → APNs → Device
3. **Memory write:** Post-turn async → Claude extract → Firestore upsert (never blocks response)
4. **Cross-device sync:** Firestore as shared state; conversation history queryable by session_id
5. **Watch relay:** iPhone receives APNs → WKInterfaceController forwards to Watch extension

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 user (v1) | Monolith FastAPI is fine; APScheduler in-process; Firestore handles all state; no Redis needed yet |
| 10 users | Same monolith; add Redis for session caching to reduce Firestore reads; monitor Claude API rate limits |
| 100 users | Extract proactive scheduler to a separate worker process; add connection pooling; consider Celery for async tasks |
| 1000+ users | Split into microservices (voice pipeline, scheduler, memory service); move to Cloud Run or Kubernetes; Claude API costs become significant |

### Scaling Priorities

1. **First bottleneck:** Claude API rate limits and latency — mitigate by caching repeated context lookups (e.g., weather for same location same day)
2. **Second bottleneck:** Whisper STT throughput — multiple simultaneous voice requests queue; mitigate with local faster-whisper worker pool
3. **Third bottleneck:** Firestore read costs on memory retrieval — add semantic search index or Redis cache for hot memory facts

---

## Anti-Patterns

### Anti-Pattern 1: Blocking the Voice Response on Memory Writes

**What people do:** Write memory facts to Firestore synchronously during the response pipeline, before sending audio back to user.
**Why it's wrong:** Adds 300-500ms to every response. Memory writes are not user-critical path.
**Do this instead:** Fire-and-forget memory extraction after the response is delivered. Use `asyncio.create_task()` to run extraction in the background.

### Anti-Pattern 2: Sending Raw Claude Output as Push Notifications

**What people do:** Push the full Claude response text as a push notification body.
**Why it's wrong:** Push notifications have character limits (APNs body: 4KB total payload, but visible text should be under 100 chars); long text is truncated and looks broken on Watch.
**Do this instead:** Have Claude return structured JSON with both a short_summary (for push/Watch) and full_response (for iPhone app). Use a dedicated proactive response schema.

### Anti-Pattern 3: Storing Full Conversation History in System Prompt

**What people do:** Stuff the entire conversation history into Claude's system prompt or beginning of context window for "memory."
**Why it's wrong:** Expensive (pays for tokens on every request), hits context window limits as history grows, and most history is irrelevant to the current query.
**Do this instead:** Store history in Firestore; retrieve only relevant facts using entity-based lookup. Inject only a small window of recent turns (last 5-10) + relevant memory facts.

### Anti-Pattern 4: Monolithic Tool Function

**What people do:** Write one giant "get_everything" tool that returns all user data at once, every time.
**Why it's wrong:** Bloats Claude's context unnecessarily; Claude performs better when tools are specific and composable.
**Do this instead:** Define small, focused tools (`get_weather`, `get_calendar_for_date`, `lookup_memory_by_entity`). Let Claude decide which tools to call.

### Anti-Pattern 5: Direct Watch-to-Backend Communication

**What people do:** Try to give Apple Watch its own independent backend connection.
**Why it's wrong:** WatchOS has strict network and background execution limitations; the Watch kills long-running network tasks.
**Do this instead:** Route all Watch communication through iPhone via WCSession (WatchConnectivity framework). iPhone does the network call; Watch receives the result via WCSession message.

### Anti-Pattern 6: Wake Word Detection in the Cloud

**What people do:** Stream all ambient audio to the cloud for wake word detection.
**Why it's wrong:** Privacy nightmare; bandwidth cost; latency; App Store and OS restrictions on always-on microphone.
**Do this instead:** Run wake word detection locally on-device (Picovoice Porcupine for Mac; iOS uses on-device SpeechRecognizer or "Hey Siri"-style triggers). Only stream audio after wake word confirmed locally.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Claude API (Anthropic) | REST — Anthropic Python SDK; streaming + tool use | Rate limits: 5 req/s (tier 1); use streaming for UX; tool use adds round trips |
| Whisper STT | Local process via `faster-whisper` OR OpenAI Whisper API | Local preferred for latency + privacy; API fallback if GPU unavailable |
| ElevenLabs TTS | REST API — audio streaming response | Latency ~400-800ms; cache common phrases (greetings, fillers) |
| Edge TTS | Python `edge-tts` library — local synthesis | Free fallback; lower quality but zero latency cost |
| Firebase / Firestore | Firebase Admin SDK (Python backend) + FlutterFire (mobile) | Use Firestore security rules even for single-user; auth always on |
| FCM → APNs | Firebase Admin SDK `messaging.send()` | Requires APNs certificate + FCM setup per app; Watch gets notifications via iPhone |
| Picovoice Porcupine | Python SDK — local wake word | Requires license key; free tier for dev; train custom "Hey VELAR" wake word |
| Apple HealthKit | iOS HealthKit → Flutter `health` package → backend bridge | HealthKit data only accessible on-device; bridge via iPhone app, never direct |
| Weather API | REST (OpenWeatherMap or Apple WeatherKit) | WeatherKit requires Apple Developer account but integrates natively; OpenWeatherMap is simpler |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Mac Daemon → FastAPI Backend | HTTPS REST (POST /voice); WebSocket for real-time | Mac daemon is a thin client; all logic lives in backend |
| Flutter iPhone → FastAPI Backend | HTTPS REST + WebSocket (`web_socket_channel`) | WebSocket for streaming responses; REST for discrete requests |
| Apple Watch → iPhone | WCSession (WatchConnectivity) — message + file transfer | Watch cannot reach backend independently; iPhone is the relay |
| FastAPI → Claude API | Anthropic Python SDK (async) | Always use async client; never block the event loop |
| FastAPI → Firestore | Firebase Admin SDK (async) | Use async Firestore client; batch writes where possible |
| FastAPI → FCM | Firebase Admin SDK `messaging` module | Push from backend only; clients never push to each other |
| Scheduler → Notification | Internal function call (in-process APScheduler) OR Cloud Tasks | Start in-process; migrate to Cloud Tasks if reliability becomes a concern |
| Tool Executor → External APIs | Async HTTP (httpx) | All tool network calls must be async; use timeout + retry |

---

## Build Order Implications

The architecture has hard dependencies that dictate phase ordering:

1. **FastAPI skeleton + Auth + Firestore** — everything else depends on this; must be Phase 1
2. **Claude tool use loop (no tools yet)** — core reasoning pipeline; needed before voice, before memory, before proactive
3. **STT (Whisper) + TTS (ElevenLabs)** — voice pipeline wrapper around the Claude loop; Phase 2
4. **Mac wake word daemon** — needs STT+TTS+backend working first; Phase 2-3
5. **Memory system (extract + store + retrieve)** — can be layered on after Claude loop works; Phase 3
6. **Proactive scheduler + morning briefing** — needs memory + notifications; Phase 4
7. **Push notifications (FCM/APNs)** — needed before Watch; Phase 3
8. **Flutter iPhone App** — can start UI scaffold in parallel with backend; integration Phase 3
9. **Apple Watch App** — depends on iPhone app (WCSession) and notifications; Phase 4-5

**Critical path:** FastAPI → Claude tool loop → Voice pipeline → Memory → Scheduler → Mobile apps → Watch

---

## Sources

- Architecture patterns: training knowledge of FastAPI, Claude API tool use, Firebase, APNs, WatchOS constraints — HIGH confidence (stable, well-established patterns)
- Claude tool use loop pattern: Anthropic documentation pattern (agentic loop) — HIGH confidence
- Apple Watch networking limitations (WCSession requirement): Apple WatchOS design constraints — HIGH confidence
- APNs character limits and Watch notification delivery: Apple documentation pattern — MEDIUM confidence (verify exact payload limits when implementing)
- Picovoice Porcupine for wake word: established library; custom wake word training available — MEDIUM confidence (verify license tier pricing at implementation time)
- HealthKit bridge pattern (on-device only, no server access): Apple platform policy — HIGH confidence
- faster-whisper latency estimates (~200ms on CPU): empirical benchmarks widely reported — MEDIUM confidence (validate on target hardware)
- ElevenLabs latency estimates (~400-800ms): reported by users in production — LOW confidence (test at Phase 2)

---

*Architecture research for: Proactive personal AI assistant (VELAR)*
*Researched: 2026-03-01*
