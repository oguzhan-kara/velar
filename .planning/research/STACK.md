# Stack Research

**Domain:** Proactive personal AI assistant — Apple ecosystem (Mac, iPhone, Apple Watch)
**Researched:** 2026-03-01
**Confidence:** MEDIUM (training data through Aug 2025; external tools unavailable for live verification — versions flagged for manual check)

---

## Research Note

WebSearch, WebFetch, Bash, and Context7 were unavailable in this session. All recommendations draw from training knowledge (cutoff: August 2025). Version numbers marked [VERIFY] must be checked against official sources before locking. Architectural recommendations are higher confidence than specific version pins.

---

## Recommended Stack

### Layer 1: AI Reasoning — Claude API (Backend Service)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `anthropic` Python SDK | `>=0.30.0` [VERIFY] | Claude API access, tool use, streaming | Official SDK; best support for tool use / function calling which is the architectural core of VELAR's "do stuff" capability |
| Claude 3.5 Sonnet / Haiku | API model [VERIFY current] | Reasoning brain | Sonnet for complex reasoning (morning briefing, social advice); Haiku for latency-sensitive voice responses. Both support tool use. |
| Python 3.11+ | 3.11 or 3.12 | Backend runtime | Async support is stable; 3.11 has ~25% perf improvements; most ML libraries (Whisper, etc.) have tested support |
| FastAPI | `0.111+` [VERIFY] | REST + WebSocket API for all clients | Async-first, auto-generates OpenAPI docs, native WebSocket support for streaming voice responses, excellent type hints |
| Uvicorn | `0.30+` [VERIFY] | ASGI server for FastAPI | De facto standard for FastAPI; production-grade with `--workers` flag |

**Why Python for the backend:** The builder has Python experience. All critical ML libraries (Whisper, voice activity detection, embeddings) are Python-native. Wrapping everything in FastAPI means Flutter/Swift clients speak HTTP/WebSocket — clean separation.

**Why not Node.js/TypeScript backend:** No ecosystem advantage for STT/TTS/ML. Would require bridging to Python anyway for Whisper. Double the runtime complexity.

---

### Layer 2: Speech — STT and TTS

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `faster-whisper` | `1.0+` [VERIFY] | Speech-to-text transcription | 4-8x faster than openai-whisper on CPU/GPU; CTranslate2 backend; same model quality; Turkish support is strong in Whisper large-v3 |
| Whisper model: `large-v3` | — | Turkish + English STT | Best accuracy for Turkish (an under-resourced language). Use `medium` during development for speed, `large-v3` in production |
| ElevenLabs API | v1 REST [VERIFY] | Text-to-speech (Jarvis voice) | Premium voice quality; streaming PCM output supported; custom voice cloning possible; Turkish language support [LOW confidence — verify Turkish quality] |
| Edge-TTS (fallback) | `6.1+` [VERIFY] | Free TTS fallback | Microsoft Azure neural voices via unofficial API; supports Turkish (`tr-TR-AhmetNeural`); acceptable quality; zero cost |
| `sounddevice` | `0.4.6` [VERIFY] | Audio I/O on Mac | Cross-platform; works with macOS CoreAudio; needed for microphone capture and speaker playback in Mac service |
| `webrtcvad` or `silero-vad` | — | Voice activity detection | Needed to know when user stops speaking before sending to Whisper. `silero-vad` is more accurate [VERIFY availability] |

**ElevenLabs vs Edge-TTS decision:** Use ElevenLabs for production quality (this is the "Jarvis feel"). Use Edge-TTS as local fallback when offline or during development to avoid API costs. The architecture should abstract TTS behind an interface so switching is trivial.

**Why not OpenAI Whisper API:** Network latency per transcription adds 500-1500ms; for voice-first this is unacceptable. Local Whisper on Mac keeps STT under 500ms for short utterances. Privacy benefit too — audio never leaves device.

**Why not Google STT / Apple STT:** Google requires cloud; Apple's on-device STT has limited Turkish accuracy and no programmatic batch access from Python.

---

### Layer 3: Wake Word Detection

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `openwakeword` | `0.6+` [VERIFY] | Wake word detection ("Hey VELAR") | Open-source; runs on CPU; supports custom wake words via training; Python-native; low false positive rate |
| `pvporcupine` (Picovoice) | v3 [VERIFY] | Alternative wake word engine | More robust, commercial license (free tier available); pre-built "Hey Jarvis" / "Hey Computer" models; custom models via Picovoice Console |

**Recommendation:** Start with `openwakeword` for zero-cost development. Train a custom "Hey VELAR" model (requires ~200 positive samples). Switch to Picovoice if false positive rate is unacceptable in production.

**Why not "Hey Siri" / Apple Wake Word:** Cannot be triggered programmatically from Python. Entirely separate ecosystem.

---

### Layer 4: Personal Memory / Knowledge Graph

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Supabase | Cloud managed | Primary data store (structured data) | PostgreSQL-backed; pgvector extension for embeddings; real-time subscriptions for cross-device sync; Row Level Security for privacy; Flutter SDK available; free tier generous |
| pgvector (via Supabase) | `0.7+` [VERIFY] | Vector similarity search | Store memory embeddings in same DB as structured data; eliminates a separate vector DB; queries like "find memories similar to this context" |
| `sentence-transformers` | `3.0+` [VERIFY] | Generate memory embeddings | Python library; `all-MiniLM-L6-v2` model is fast and good enough for personal memory search; runs locally |
| Firebase (alternative) | — | Alternative to Supabase | Better if Flutter is primary client; Firestore has excellent Flutter SDK; but lacks pgvector / SQL flexibility for complex memory queries |

**Supabase vs Firebase decision:** Choose Supabase because:
1. pgvector means one DB for both structured data (calendar events, food preferences) and vector search (semantic memory)
2. SQL queries are more expressive for complex memory reasoning
3. Builder has Python background — SQL is natural
4. Real-time subscriptions work for cross-device sync

**Firebase is acceptable** if the Flutter-first workflow matters more and memory queries stay simple. Firebase's Flutter SDK is more mature than Supabase's Flutter SDK. Flag this for a team decision before implementation.

---

### Layer 5: iPhone App (Flutter)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Flutter | `3.22+` [VERIFY] | iOS app framework | Builder's expertise; single codebase (though Watch is separate Swift); Dart is easy to learn; excellent for voice UI |
| Dart | `3.4+` [VERIFY] | Language | Bundled with Flutter |
| `record` package | `5.1+` [VERIFY] | Microphone recording on iOS | Handles iOS audio session, AVAudioSession permissions; outputs PCM/WAV for Whisper |
| `audioplayers` or `just_audio` | latest [VERIFY] | TTS audio playback | `just_audio` preferred for stream-based playback of ElevenLabs streaming response |
| `supabase_flutter` | `2.5+` [VERIFY] | Supabase client | Auth, realtime, storage — well-maintained official SDK |
| `firebase_messaging` | `15+` [VERIFY] | Push notifications (FCM) | If using Firebase for push; required for proactive alerts even when app is backgrounded |
| `flutter_local_notifications` | `17+` [VERIFY] | Local notification scheduling | On-device scheduled reminders |
| `dio` or `http` | `5.4+` / `1.2+` [VERIFY] | HTTP client for FastAPI | `dio` preferred for interceptors, retry logic, streaming; `http` is simpler |
| `riverpod` | `2.5+` [VERIFY] | State management | Most architecturally sound for Flutter; compile-time safety; works well with async voice state |
| `flutter_dotenv` | latest | Environment variables | API keys in `.env`, not source code |
| `permission_handler` | `11+` [VERIFY] | Microphone/notification permissions | Required for iOS microphone access |

**Why not react-native:** Builder uses Flutter; no reason to switch.

**Why Riverpod over Bloc/GetX:** Riverpod is compile-time safe (no runtime type errors), handles async state (voice recording, API calls) cleanly, and doesn't require boilerplate-heavy patterns. For a voice assistant with complex async flows this matters.

---

### Layer 6: Apple Watch App (Swift)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Swift | 5.10+ / 6.0 [VERIFY] | Native Watch development | Only viable option for watchOS apps with full capability |
| SwiftUI | — | Watch UI | Required for watchOS 7+; declarative UI fits Watch's limited interaction model |
| WatchKit / WatchConnectivity | — | iPhone↔Watch communication | `WatchConnectivity` framework transfers data between paired Watch and iPhone app; required for cross-device state sync |
| AVFoundation | — | Audio on Watch | Limited; Watch has microphone but audio processing is constrained |
| UserNotifications | — | Local notifications on Watch | For briefings and reminders on Watch |

**Watch scope reality check (MEDIUM confidence):** Apple Watch apps have significant constraints:
- Cannot make arbitrary HTTP calls easily from watchOS; must proxy through companion iPhone app
- Audio recording is possible but limited duration
- Background tasks are heavily restricted (WKExtendedRuntimeSession for brief background work)
- The Watch app should be a "thin client" — display briefings, receive notifications, trigger commands that the iPhone processes

**Recommendation:** Watch v1 = receive push content + quick voice trigger that hands off to iPhone. Full Watch standalone processing is a v2 concern.

---

### Layer 7: Mac Background Service

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python 3.11+ | — | Mac service runtime | Wake word listener + STT + Claude calls all in Python |
| `launchd` plist | macOS native | Run service on boot | macOS-native daemon manager; more reliable than `cron` for persistent services |
| `rumps` | `0.4+` [VERIFY] | macOS menu bar app | Lightweight Python library for menu bar icon + status; lets user see VELAR status and toggle listening |
| `pyinstaller` (later) | `6.0+` [VERIFY] | Package Mac app | For distributing Mac service as `.app` bundle; avoid early, use only for polish phase |
| `pyobjc` | `10+` [VERIFY] | Python↔macOS bridge | Needed for native macOS notifications (`NSUserNotification`/`UNUserNotificationCenter`) from Python |

**Mac app vs Mac service:** VELAR on Mac should run as a background service with a menu bar icon (like Alfred, Bartender). Not a foreground app. This is the ambient always-on design.

---

### Layer 8: Push Notifications (Cross-device Proactive Alerts)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Firebase Cloud Messaging (FCM) | v1 API [VERIFY] | Push notifications to iPhone | Free; APNs bridge built-in; required for notifying iPhone when app is backgrounded; Python SDK available (`firebase-admin`) |
| APNs (via FCM) | — | iOS/watchOS delivery | FCM routes to APNs automatically; direct APNs requires certificate management |
| `firebase-admin` Python SDK | `6.5+` [VERIFY] | Send pushes from backend | Official SDK; FCM HTTP v1 API |

**Why FCM over direct APNs:** FCM abstracts certificate rotation and token management. For a personal project, the overhead of direct APNs is not worth it.

---

### Layer 9: Scheduling / Proactive Engine

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `APScheduler` | `4.0+` [VERIFY] | Cron-like job scheduler in Python | Run morning briefing at 7am, check weather every hour, etc.; async-compatible; persistent job store via SQLAlchemy |
| `httpx` | `0.27+` [VERIFY] | Async HTTP client for 3rd party APIs | Weather API (OpenWeatherMap), Google Calendar API calls from backend; async-native unlike `requests` |
| `celery` (future) | — | Distributed task queue | Only needed when scheduling volume grows beyond single-process; overkill for personal assistant v1 |

---

### Layer 10: External Data Integrations

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| OpenWeatherMap API | v3 [VERIFY] | Weather data | Free tier (1000 calls/day); excellent API; JSON responses easy to parse |
| Google Calendar API | v3 | Calendar access | Most users have Google Calendar; OAuth2 required; `google-api-python-client` |
| `google-api-python-client` | `2.130+` [VERIFY] | Google APIs | Official Python client |
| `google-auth` | `2.29+` [VERIFY] | OAuth for Google | Handles token refresh |
| HealthKit (iOS) | — | Health data from iPhone | Must be accessed from Flutter via method channel to native iOS code; `health` Flutter package |
| `health` (Flutter package) | `10+` [VERIFY] | HealthKit bridge in Flutter | Reads step count, sleep, heart rate from HealthKit; sends to backend for VELAR context |

---

### Layer 11: Auth and Security

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Supabase Auth | — | User authentication | Built into Supabase; supports Apple Sign-In (critical for iOS App Store), email/password, magic links |
| Apple Sign In | — | iOS auth requirement | App Store requires "Sign in with Apple" if any social auth is offered; Supabase supports this |
| `python-jose` or `pyjwt` | latest [VERIFY] | JWT verification in backend | Verify Supabase JWTs on FastAPI endpoints |
| HTTPS only | — | Transport encryption | All API calls over TLS; FastAPI behind nginx/Caddy in production |
| Supabase RLS | — | Row-level data isolation | Every Supabase table gets `user_id` column + RLS policy; data never crosses users |

---

### Layer 12: Development Infrastructure

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Docker | — | Backend containerization | Consistent dev/prod environment; Whisper model files mount as volume |
| `docker-compose` | v2 [VERIFY] | Local dev orchestration | FastAPI + Supabase local together |
| Supabase CLI | `1.170+` [VERIFY] | Local Supabase dev | Run Supabase locally for development without cloud costs |
| `pytest` + `pytest-asyncio` | latest [VERIFY] | Python testing | FastAPI is async — need async test support |
| `ruff` | `0.5+` [VERIFY] | Python linting + formatting | Replaces flake8 + black + isort in one tool; extremely fast |
| Xcode | 16+ [VERIFY] | Swift/Watch development | Required; no alternative |
| Android Studio / IntelliJ | latest | Flutter development | Flutter plugin works in both; VS Code is also fine |

---

## Supporting Libraries (Python Backend)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic` | `2.7+` [VERIFY] | Data validation / settings | Always — FastAPI uses it; also for `BaseSettings` config management |
| `python-dotenv` | `1.0+` | Load `.env` files | Local development; production uses env vars directly |
| `structlog` | `24+` [VERIFY] | Structured logging | JSON logs; much better than stdlib `logging` for production |
| `tenacity` | `8.3+` [VERIFY] | Retry logic | Wrap ElevenLabs, Claude API calls with exponential backoff |
| `numpy` | `1.26+` [VERIFY] | Audio array processing | Required by faster-whisper; Whisper works on numpy arrays |
| `asyncio` | stdlib | Async runtime | Use throughout; never block the event loop with synchronous Whisper calls — run in thread pool |

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Supabase | Firebase | Choose Firebase if Flutter-first is paramount and memory queries stay simple key-value; Firebase Flutter SDK is more mature |
| Supabase | Pinecone + PostgreSQL | Only if vector search becomes the primary bottleneck at scale; overkill for personal assistant |
| faster-whisper (local) | OpenAI Whisper API | Only if device resources are severely constrained (e.g., old Mac); costs money per transcription and adds ~1s latency |
| ElevenLabs | Azure Neural TTS | If ElevenLabs Turkish quality is poor (verify); Azure has good `tr-TR` support and cheaper at volume |
| ElevenLabs | Kokoro TTS (local) | Kokoro is an emerging open-source TTS; may reach ElevenLabs quality; check in 2026 — may save API costs [LOW confidence] |
| FastAPI | Flask | Only if builder finds FastAPI async too complex; Flask is simpler but lacks native WebSocket/async for streaming |
| FastAPI | Django | Don't; Django is too heavy for a service API; FastAPI is the right choice |
| openwakeword | Picovoice Porcupine | Use Porcupine if custom "Hey VELAR" training is too difficult or false positive rate is unacceptable |
| riverpod | Bloc | Use Bloc if team already knows it; but for solo developer, Riverpod's boilerplate reduction matters |
| APScheduler | Cloud Scheduler (GCP) | Only if moving fully to cloud-managed infrastructure; overkill for personal use |
| FCM (push) | direct APNs | Direct APNs if FCM latency is an issue; rarely is for personal apps |
| `rumps` (menu bar) | Electron / Tauri | Don't; heavyweight for a background service; Python menu bar is the right scale |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `openai-whisper` (original) | 4-8x slower than faster-whisper on same hardware; same model quality | `faster-whisper` |
| LangChain (for Claude tool use) | Massive abstraction overhead; Claude's native tool use API is excellent and simpler; LangChain adds complexity without benefit for single-model setup | `anthropic` SDK directly |
| LlamaIndex (for memory) | Over-engineered for a personal assistant's memory needs; pgvector + custom retrieval is more controllable | pgvector + custom Python retrieval |
| Qdrant / Weaviate / Pinecone | Separate vector DB is operationally complex; pgvector in Supabase is sufficient for personal-scale | Supabase + pgvector |
| Twilio for push | Expensive and designed for SMS/voice calls, not mobile push | FCM + APNs via `firebase-admin` |
| Flutter for Apple Watch | Flutter's watchOS support is experimental / unofficial; WatchOS apps in Flutter cannot access Watch hardware properly | Swift + SwiftUI + WatchKit |
| `requests` library | Synchronous; blocks FastAPI's async event loop | `httpx` (async) |
| `celery` + `redis` in v1 | Operationally heavy for personal assistant; adds Redis dependency | `APScheduler` (in-process) |
| WebRTC for voice streaming | Complex; not needed when app is mobile-native with local recording | Record audio in app, POST to FastAPI |
| On-device LLM (Ollama etc.) | Quality is not Jarvis-level yet for reasoning tasks; Turkish language quality poor in small models | Claude API |

---

## Stack Patterns by Variant

**If device is Mac (ambient service):**
- Python service + `openwakeword` + `faster-whisper` + `rumps` menu bar
- Audio I/O via `sounddevice`
- Communicate with backend FastAPI over localhost (Mac service IS the backend)

**If device is iPhone (user-initiated):**
- Flutter app records audio → POSTs to FastAPI
- FastAPI runs Whisper → Claude → ElevenLabs → streams audio back
- Push notifications from `firebase-admin` for proactive alerts

**If device is Apple Watch:**
- Thin Swift client; receives data via `WatchConnectivity` from iPhone
- Displays briefing cards via SwiftUI
- Voice input on Watch → WatchConnectivity → iPhone → backend

**For Turkish language:**
- Use Whisper `large-v3` (best Turkish STT accuracy)
- Verify ElevenLabs Turkish TTS voice quality before committing (check `tr` voices)
- Claude handles Turkish natively — no special config needed
- System prompt should instruct: "Respond in the same language the user spoke"

**For proactive engine timing:**
- APScheduler runs jobs: morning briefing at configurable time, hourly context refresh, event-based triggers
- Jobs call Claude with assembled context (weather + calendar + health + memory)
- Result dispatched via FCM to iPhone/Watch

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| faster-whisper `1.0+` | Python `3.9-3.12` | CTranslate2 backend; requires `libcudart` only if GPU mode |
| anthropic SDK `0.30+` | Python `3.8+` | Tool use works since `0.18+`; use latest for streaming tool use |
| FastAPI `0.111+` | Pydantic `2.x` | FastAPI dropped Pydantic v1 support; don't mix |
| Flutter `3.22+` | Dart `3.4+` | Bundled; don't specify Dart separately |
| supabase-flutter `2.x` | Flutter `3.10+` | v2 is breaking change from v1 — don't mix |
| firebase_messaging `15+` | Flutter `3.16+` | FCM HTTP v1 API required; legacy FCM removed |

---

## Installation

```bash
# Python backend (requirements.txt)
anthropic>=0.30.0
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
faster-whisper>=1.0.0
sounddevice>=0.4.6
openwakeword>=0.6.0
ElevenLabs>=1.0.0
supabase>=2.5.0
firebase-admin>=6.5.0
APScheduler>=4.0.0
httpx>=0.27.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
python-dotenv>=1.0.0
structlog>=24.0.0
tenacity>=8.3.0
numpy>=1.26.0
google-api-python-client>=2.130.0
google-auth>=2.29.0
rumps>=0.4.0
pyobjc>=10.0
python-jose[cryptography]>=3.3.0
ruff>=0.5.0  # dev dependency
pytest>=8.0.0  # dev dependency
pytest-asyncio>=0.23.0  # dev dependency

# Flutter pubspec.yaml dependencies
# flutter pub add record just_audio supabase_flutter firebase_messaging
# flutter pub add flutter_local_notifications dio riverpod flutter_riverpod
# flutter pub add permission_handler health flutter_dotenv
```

```bash
# Supabase local dev
npx supabase start

# Run FastAPI in dev
uvicorn main:app --reload --port 8000

# Run Mac service
python -m velar.mac_service
```

---

## Architecture Implications

The stack creates three distinct execution contexts:

1. **Mac Python Service** — Always running; wake word + STT + Claude + TTS + APScheduler all in-process. Communicates with Supabase directly. Sends FCM push for cross-device.

2. **FastAPI Cloud Backend** — Handles iPhone/Watch clients; same Python logic but served over HTTP; stateless (state in Supabase).

3. **Flutter iPhone App** — Records audio, displays responses, receives push; no AI logic on-device.

4. **Swift Watch App** — Receives from iPhone via WatchConnectivity; no direct backend calls.

This means the Python backend logic must be written to work both as a local library (Mac service) and as an HTTP API (iPhone/Watch clients). Use service classes that are transport-agnostic.

---

## Sources

- Training data (cutoff August 2025) — PRIMARY SOURCE for all recommendations
- [VERIFY] markers indicate items requiring live doc check before implementation
- Anthropic docs: https://docs.anthropic.com/en/api/ — for Claude SDK and model capabilities
- Supabase docs: https://supabase.com/docs — for pgvector, RLS, Flutter SDK
- faster-whisper GitHub: https://github.com/SYSTRAN/faster-whisper — for version and compatibility
- ElevenLabs docs: https://elevenlabs.io/docs — for Turkish TTS verification
- openwakeword GitHub: https://github.com/dscripka/openWakeWord — for custom wake word training
- Apple Developer docs: https://developer.apple.com/documentation/watchconnectivity — for Watch constraints

**Confidence by area:**
| Area | Confidence | Notes |
|------|------------|-------|
| Claude API + Python SDK | MEDIUM | Architecture is right; specific version number needs verification |
| Flutter iOS development | MEDIUM | Core packages stable; verify supabase_flutter v2 compatibility |
| faster-whisper for Turkish STT | MEDIUM | Known strong Turkish support in Whisper large-v3; local speed advantage confirmed |
| Wake word (openwakeword) | MEDIUM | Project is active open-source; custom training workflow is documented |
| ElevenLabs Turkish TTS | LOW | Turkish voice quality not verified; test before committing |
| Apple Watch constraints | MEDIUM | WatchConnectivity pattern is standard; background task limits are documented |
| Supabase + pgvector for memory | MEDIUM | pgvector in Supabase is production-ready; sufficiency for personal-scale memory is confident |
| APScheduler v4 | LOW | v4 is a rewrite with different API from v3; verify migration guide if upgrading |
| All Python version pins | LOW | Need live PyPI check for latest stable versions |

---

*Stack research for: VELAR — proactive personal AI assistant, Apple ecosystem*
*Researched: 2026-03-01*
