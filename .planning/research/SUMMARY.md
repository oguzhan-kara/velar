# Project Research Summary

**Project:** VELAR — Proactive Personal AI Assistant
**Domain:** Voice-first, ambient, multi-device personal AI assistant (Apple ecosystem)
**Researched:** 2026-03-01
**Confidence:** MEDIUM

## Executive Summary

VELAR is a proactive personal AI assistant built for the Apple ecosystem (Mac, iPhone, Apple Watch), with Turkish and English bilingual support. The established pattern for this product class is a layered architecture: a Python FastAPI backend handles all AI orchestration, Claude API provides reasoning via a tool-use loop, local Whisper STT keeps voice latency under 500ms and audio off the cloud, ElevenLabs provides premium TTS voice quality, and Supabase (with pgvector) stores both structured personal data and semantic memory embeddings. Clients are thin — Flutter on iPhone records audio and renders responses; a Swift WatchKit app is a satellite display; a Python daemon on Mac runs wake word detection and proxies to the same backend. This separation is the correct approach: AI logic lives in one place, transport is swappable.

The recommended path is to build bottom-up along a strict dependency chain: backend infrastructure and auth first, then the Claude tool-use loop with no tools yet, then voice pipeline (STT+TTS), then the memory system, then proactive scheduling, then mobile clients, and finally the Watch app. Every differentiating feature — food advice, social advice, morning briefing, place suggestions — depends on the personal memory system being reliable. Memory is the foundation. If it is weak, all downstream features degrade to generic responses no better than a stateless chatbot. The memory architecture must use semantic vector retrieval (pgvector), fact versioning (supersede rather than duplicate), and a hard token budget cap for context injection, from the very first implementation.

The primary risks are: (1) LLM hallucination presenting invented facts as personal memory — mitigated by a strict grounding system prompt and retrieval-confidence gates; (2) notification overload destroying user trust in the proactive identity — mitigated by defaulting to one consolidated daily briefing with a user-tunable threshold and automatic suppression of high-dismissal categories; (3) ElevenLabs Turkish TTS and Turkish STT quality — both must be verified and acceptance-tested against real Turkish speech before any voice phase advances; and (4) Apple Watch being treated as a shrunken iPhone — it must be designed as a 3-second glance device from the start, not a capability port.

---

## Key Findings

### Recommended Stack

The stack is a Python-first backend paired with native Apple clients. Python was chosen because the builder has Python expertise and because every critical library — Whisper STT, voice activity detection, embeddings, scheduling — is Python-native. FastAPI (async, WebSocket-capable) is the API layer. Claude 3.5 Sonnet handles complex reasoning (morning briefing, advice synthesis); Claude Haiku handles lightweight background tasks (memory extraction, notification scoring) to control API costs. Supabase provides PostgreSQL with pgvector in a single managed database — eliminating a separate vector store while enabling semantic memory search via SQL. Firebase Cloud Messaging bridges to APNs for push notifications to iPhone and Watch without direct APNs certificate management.

Turkish language support has specific requirements: Whisper `large-v3` is mandatory (not `medium` or `small`) for acceptable Turkish accuracy, especially on code-switched sentences. ElevenLabs Turkish voice quality must be verified before committing — this is explicitly LOW confidence and must be tested in Phase 2. Edge-TTS (`tr-TR-AhmetNeural`) is a zero-cost fallback. All stack items below carry [VERIFY] markers — versions must be confirmed against live PyPI and Flutter pub registries before locking.

**Core technologies:**
- `Claude API (Anthropic SDK >=0.30)`: AI reasoning and tool use — the only model with sufficient quality for Turkish + complex reasoning; use native tool use, not LangChain
- `faster-whisper (>=1.0, large-v3)`: Local STT — 4-8x faster than original Whisper on same hardware; Turkish large-v3 is meaningfully better than smaller models
- `ElevenLabs API`: Premium TTS — verify Turkish voice quality before committing; Edge-TTS is the fallback
- `FastAPI (>=0.111) + Uvicorn`: Async API layer — WebSocket streaming for voice responses; auto OpenAPI docs
- `Supabase + pgvector`: Primary data store + semantic memory — one database for structured data and vector embeddings; pgvector eliminates a separate Pinecone/Qdrant instance
- `Firebase Admin SDK (>=6.5) / FCM`: Push notifications — FCM handles APNs routing; Watch receives via iPhone proxy
- `APScheduler (>=4.0)`: Proactive scheduler — in-process cron for morning briefing and proactive checks; Celery is overkill for v1
- `openwakeword (>=0.6)`: Wake word detection — on-device, CPU-capable, custom "Hey VELAR" training supported; Picovoice Porcupine is the production-grade alternative
- `Flutter (>=3.22) + Riverpod`: iPhone app — builder expertise; Riverpod for compile-time-safe async voice state management
- `Swift + SwiftUI + WatchKit`: Watch app — Flutter watchOS support is insufficient; Watch must be Swift-native

**Explicit avoid list:** LangChain (adds abstraction overhead, Claude's native tool use is better), LlamaIndex (over-engineered for personal memory), Pinecone/Qdrant (pgvector is sufficient at personal scale), `openai-whisper` original (use faster-whisper), `requests` library (blocks async event loop, use `httpx`).

### Expected Features

The market benchmark is clear: Siri, Google Assistant, and Alexa all fail at persistent personal memory and proactive initiation. Rabbit R1 and Humane AI Pin both failed — R1 because its LAM was unreliable and lacked personalization; Humane Pin because camera-first was slow and no memory meant every interaction started cold. VELAR's thesis ("proactive, memory-backed assistant beats reactive assistants") is directly validated by those failures. The opportunity is real; the execution risk is high.

**Must have (table stakes — product feels broken without these):**
- Wake word activation ("Hey VELAR") on Mac — on-device, never cloud-streaming ambient audio
- Natural voice conversation: STT → Claude → TTS end-to-end, under 4s perceived latency
- Turkish + English bilingual support including code-switching (mixed-language sentences)
- Morning briefing: weather + calendar + at least one memory-backed personal fact
- Personal memory system: store and retrieve facts from conversations
- iPhone Flutter app with voice and chat interfaces
- Push notifications for time-sensitive proactive alerts
- Cloud sync between Mac and iPhone (shared session state via Supabase)
- Food advice backed by dietary profile and meal history in memory

**Should have (competitive differentiators — what makes VELAR win):**
- Passive learning pipeline: extract facts from every conversation, store without user data entry
- Apple Watch app (Swift): morning briefing glance, quick voice command handoff, notification acknowledgment
- Social advice: relationship memory, message drafting with relationship context
- Place advice: visit history + preference + time-of-day suggestions
- Mood-aware responses: tone and content adjustment based on health data or voice sentiment

**Defer to v2+:**
- Smart home / HomeKit control — dilutes proactive identity; scope creep
- Third-party plugin / skill system — discoverability problem (see Alexa's 100k+ skills failure)
- Android support — Apple-first until core is proven
- Computer vision features — voice-first is proven; camera-primary is unproven (see Humane Pin)
- Full offline mode — cloud-first until product-market fit is established

**Anti-features to explicitly refuse:**
- Financial/banking integration: regulatory and trust risk
- Autonomous social media posting: one bad auto-post permanently damages trust
- Full conversation transcript storage: privacy breach risk; store extracted facts, not raw transcripts

### Architecture Approach

The architecture uses four separated execution contexts that share state through Supabase and FCM. The Mac Python service runs the wake word daemon, audio capture, and proxies to the FastAPI backend. The FastAPI backend hosts all AI orchestration — it is stateless (state lives in Supabase) and serves both the Mac service and the Flutter iPhone app over HTTPS/WebSocket. The Flutter iPhone app is a thin client: record audio, render responses, receive push. The Swift Watch app is a satellite: it receives content from iPhone via WatchConnectivity (WCSession), never connects to the backend directly. This design means all AI logic is written once in Python and exposed through a transport-agnostic service layer.

**Major components:**
1. **Mac Python Daemon** — wake word detection (openwakeword/Porcupine), audio capture (sounddevice), VAD, proxy to FastAPI
2. **FastAPI Backend** — all AI orchestration; routers (voice, chat, memory, briefing, proactive); service layer (claude, stt, tts, memory, notification, scheduler); tool executor (weather, calendar, memory, places, health, notification)
3. **Claude Tool Use Loop** — agentic pattern: Claude calls tools → backend executes → feeds results back → repeat until text response; this is the core reasoning primitive for every VELAR interaction
4. **Memory System** — entity-attribute-value triples in Supabase with pgvector embeddings; semantic retrieval via cosine similarity; fact versioning (supersede, don't duplicate); memory extraction runs async post-conversation, never on request path
5. **Proactive Scheduler (APScheduler)** — cron-triggered context gather → Claude decision → FCM dispatch; morning briefing is the primary scheduled job at user-configured time
6. **Flutter iPhone App** — records audio (record package), plays streaming TTS (just_audio), displays responses, handles FCM push
7. **Swift Watch App** — WCSession relay from iPhone; brief display only (SwiftUI); maximum 3 interactive elements per screen; no direct backend calls

**Critical path (build order):** FastAPI skeleton + auth + Supabase → Claude tool loop (no tools) → STT + TTS voice pipeline → Mac wake word daemon → Memory system (extract, store, retrieve) → FCM push notifications → Proactive scheduler + morning briefing → Flutter iPhone app (can scaffold in parallel) → Apple Watch app

### Critical Pitfalls

1. **Unbounded memory growth collapsing retrieval quality** — Use pgvector semantic retrieval with a hard token budget cap (2000 tokens max injected per query). Implement fact versioning (supersede, not append) and TTL-flagged stale facts. Never full-dump memory into context. Address in Phase 3 (memory) before any dependent features are built.

2. **Proactive notifications destroying user trust through overload** — Default to one consolidated daily briefing. Implement notification relevance scoring and quiet hours from day one. Track dismissal rates per category and auto-suppress above 70% dismissal. Three or fewer notifications per day average is the operating target. Address in Phase 5 (proactive engine).

3. **LLM hallucinating personal facts** — System prompt must explicitly prohibit inventing user facts when memory retrieval returns nothing. Gate personal-fact queries: if semantic retrieval confidence is below threshold, return structured "no data" before calling Claude. Separate factual retrieval (deterministic) from reasoning (generative). Address in Phase 3 (memory + Claude integration).

4. **Turkish STT failure on code-switched speech** — Require Whisper large-v3 (not smaller models). Validate Turkish WER < 15% on 50 common assistant commands before advancing from Phase 2. Implement a user correction flow (tap to see and fix what VELAR heard). Do not defer Turkish validation — discover failures early.

5. **Firebase/Supabase security misconfiguration exposing intimate personal data** — All Supabase tables require RLS with `user_id` scoping from day one. Firebase Security Rules must gate every document on `request.auth.uid == resource.data.userId` — never global authenticated-user access. Run security rules against a non-owner test account before any real personal data is stored. No API keys (Claude, ElevenLabs) in Flutter app binary. Address in Phase 1.

6. **API cost explosion from uncontrolled LLM calls** — Use Claude Haiku for memory extraction and notification scoring; reserve Sonnet for primary conversation and briefing synthesis. Implement per-user daily budget cap with circuit breaker before any proactive LLM features ship. Batch memory extraction to session end, never on every message. Cost telemetry dashboard required in Phase 2.

---

## Implications for Roadmap

Based on research, the dependency chain is strict and must not be reordered. Every downstream feature (memory-backed advice, proactive briefings, Watch app) depends on stable foundations. Suggested phase structure:

### Phase 1: Foundation — Backend, Auth, and Data Layer
**Rationale:** Everything depends on this. FastAPI, Supabase auth, RLS security rules, and Supabase database schema must exist before any feature can be built. Security rules are not a later concern — they must be correct before any personal data is stored.
**Delivers:** Running FastAPI service with auth, Supabase connection, RLS policies validated against non-owner test account, basic /health endpoint, Docker dev environment, Supabase CLI local dev setup.
**Addresses:** Cross-device sync foundation (shared state model), security baseline.
**Avoids:** Firebase/Supabase security misconfiguration (Pitfall 7), cross-device state desync from poor session modeling (Pitfall 5).
**Research flag:** Standard patterns — FastAPI + Supabase + auth is well-documented. Skip deep phase research.

### Phase 2: Voice Pipeline — STT, TTS, and Claude Core Loop
**Rationale:** Voice is the core interaction model. The Claude tool-use loop (with no tools yet) must exist before memory, briefing, or any integrations. STT and TTS quality (especially Turkish) must be validated at this phase — do not advance until Turkish WER < 15%.
**Delivers:** Working voice round-trip (audio in → faster-whisper → Claude → ElevenLabs → audio out), Claude tool-use loop scaffold (no tools yet), Turkish STT acceptance test passing, ElevenLabs Turkish voice quality verified, cost telemetry logging live, Edge-TTS fallback working.
**Uses:** faster-whisper large-v3, ElevenLabs API, Anthropic SDK, FastAPI /voice router.
**Avoids:** Turkish STT failure (Pitfall 4), API cost explosion (Pitfall 6), Flutter-backend resilience failures (Pitfall 10).
**Research flag:** ElevenLabs Turkish TTS quality is LOW confidence — must test at Phase 2 before committing. If Turkish quality is inadequate, evaluate Azure Cognitive Services Turkish TTS.

### Phase 3: Memory System — Personal Knowledge Graph
**Rationale:** The memory system is the foundation of every differentiator. Food advice, social advice, place advice, and morning briefing all degrade to generic responses without reliable, structured, semantically-searchable memory. Build this before any feature that depends on it.
**Delivers:** Entity-attribute-value memory schema in Supabase with pgvector embeddings, semantic retrieval with hard 2000-token injection cap, fact versioning (supersede pattern), async memory extraction running post-conversation (never blocking response path), LLM hallucination guard in system prompt, retrieval-confidence gate for personal-fact queries, basic /memory CRUD API.
**Implements:** Memory service, memory tool (Claude tool), sentence-transformers embedding pipeline.
**Avoids:** Unbounded memory growth (Pitfall 1), LLM hallucinating personal facts (Pitfall 3), flat key-value memory shortcut (Technical debt table).
**Research flag:** Likely needs phase research for pgvector semantic retrieval tuning and fact versioning patterns. This is the most architecturally novel component.

### Phase 4: Mac Daemon and Wake Word
**Rationale:** Mac is the primary ambient device. The wake word daemon requires STT, TTS, and the backend to be working first. Build this after Phase 2-3.
**Delivers:** Python Mac service with openwakeword ("Hey VELAR"), sounddevice audio capture, VAD (silero-vad), local faster-whisper transcription, rumps menu bar icon, launchd plist for boot persistence, full voice round-trip on Mac without opening any app.
**Uses:** openwakeword/Porcupine, sounddevice, rumps, pyobjc, launchd.
**Avoids:** Cloud wake word streaming (Anti-pattern 6 / Pitfall 7 — privacy and App Store violation), blocking audio event loop with synchronous calls.
**Research flag:** Custom "Hey VELAR" wake word training with openwakeword requires ~200 positive samples — flag for scope decision (use a generic trigger word in v1 vs. invest in custom training).

### Phase 5: Proactive Engine and Morning Briefing
**Rationale:** Morning briefing is the signature demo and the core thesis validator. It requires memory (Phase 3), Claude tool loop (Phase 2), weather and calendar integrations, and FCM push. All must be working before this phase.
**Delivers:** APScheduler proactive engine, morning briefing job (weather + calendar + memory context → Claude → FCM push), weather tool (OpenWeatherMap), Google Calendar tool (OAuth2), notification relevance scoring with user-tunable threshold, quiet hours configuration, notification dismissal rate tracking, graceful data-source degradation (briefing still fires with partial data, uncertainty is stated explicitly), short_summary vs. full_response structured Claude output for Watch-safe payloads.
**Implements:** Scheduler service, notification service, weather tool, calendar tool, proactive pattern.
**Avoids:** Notification overload / noise (Pitfall 2), raw Claude output as push payload (Anti-pattern 2), proactive system with imperfect context failing silently (Pitfall 9).
**Research flag:** Google Calendar OAuth2 + token refresh flow is moderately complex — may benefit from focused phase research. APScheduler v4 API changed from v3; verify migration guide.

### Phase 6: Flutter iPhone App
**Rationale:** The iPhone app can be scaffolded in parallel with earlier phases, but full integration requires Phase 2-5 to be stable. This phase completes the iPhone experience.
**Delivers:** Flutter voice interface (record package, push-to-talk and always-listening modes), streaming TTS playback (just_audio), chat text interface, memory review/delete UI ("What VELAR knows about me"), FCM push notification handling, APNs token refresh, optimistic UI with "VELAR is thinking..." within 300ms, 10-second timeout with cancel, Supabase auth (Apple Sign-In), Riverpod state management.
**Uses:** Flutter 3.22+, Riverpod, record, just_audio, supabase_flutter, firebase_messaging, permission_handler, dio, health package.
**Avoids:** Flutter-backend resilience failures (Pitfall 10), no loading state/spinner (UX pitfall), HealthKit all-permissions-upfront rejection (Integration gotcha), API keys in Flutter binary (Security mistake).
**Research flag:** HealthKit on-demand permission pattern and Flutter `health` package integration may need phase research — Apple's review process for HealthKit is strict.

### Phase 7: Apple Watch App
**Rationale:** Watch requires iPhone app (WCSession dependency) and FCM notifications to be working. It is explicitly a satellite device. Design from scratch as a glance device — not a shrunken iPhone.
**Delivers:** Swift WatchKit app, WCSession relay from iPhone (Watch never calls backend directly), three and only three use cases: (1) morning briefing headline with 2-sentence expand, (2) quick voice command handed off to iPhone, (3) acknowledge/snooze proactive notification; WatchKit Complications for ambient data (next event, weather); performance tested on real hardware (not just simulator); battery impact validated.
**Uses:** Swift 5.10+, SwiftUI, WatchKit, WatchConnectivity, UserNotifications.
**Avoids:** Apple Watch as shrunken iPhone (Pitfall 8), Watch-to-backend direct communication (Anti-pattern 5), more than 3 interactive elements per screen (Pitfall 8 warning sign).
**Research flag:** WatchKit Complications API and WCSession real-time reliability patterns may benefit from phase research, especially for the voice handoff UX.

### Phase 8: Memory-Backed Advice Features
**Rationale:** Food advice, social advice, and place advice all depend on the memory system having 2+ weeks of data. These phases should only begin after real daily use has validated the memory foundation. This is v1.x territory.
**Delivers:** Food advice Claude tool (dietary profile + meal history + current mood → meal suggestion), social advice (relationship memory graph, message drafting), place advice (visit history + time-of-day + who you're with), passive learning pipeline improvements (background fact extraction refinements).
**Implements:** places_tool (Google Places API), food preference schema, relationship graph schema, mood proxy from Apple Health HRV/sleep data.
**Avoids:** Generic responses from thin memory (validated by this point), requesting all HealthKit permissions upfront.
**Research flag:** Google Places API integration and relationship graph schema design both likely benefit from phase research.

### Phase Ordering Rationale

- Phases 1-3 form the non-negotiable infrastructure core. Nothing meaningful ships without them.
- Phase 4 (Mac daemon) is the primary ambient device and wake word experience — it comes before mobile because Mac is the "home base" of the proactive identity.
- Phase 5 (proactive engine) is the thesis validator. If morning briefing works and earns daily use, the product hypothesis is confirmed.
- Phase 6 (iPhone) and Phase 7 (Watch) are the mobile layer. iPhone can be scaffolded in parallel with Phases 2-5 but must integrate after they are stable.
- Phase 8 is v1.x: it requires real memory data accumulated from daily use to be meaningful.

### Research Flags

Phases requiring deeper research during planning:
- **Phase 3 (Memory System):** pgvector retrieval tuning, fact versioning patterns, semantic memory architecture — architecturally novel for this use case.
- **Phase 5 (Proactive Engine):** APScheduler v4 API (v4 is a rewrite of v3), Google Calendar OAuth2 token refresh.
- **Phase 6 (iPhone App):** HealthKit on-demand permission UX and App Store review requirements for voice recording + health data.
- **Phase 7 (Watch App):** WatchKit Complications API, WCSession reliability for voice handoff pattern.
- **Phase 8 (Advice Features):** Google Places API, relationship graph schema design.

Phases with standard patterns (skip deep research):
- **Phase 1 (Foundation):** FastAPI + Supabase + auth is extremely well-documented.
- **Phase 2 (Voice Pipeline):** faster-whisper, ElevenLabs, Claude tool loop are all well-documented. Exception: verify ElevenLabs Turkish voice quality empirically at start of phase.
- **Phase 4 (Mac Daemon):** rumps + launchd + sounddevice patterns are stable and documented. Exception: decide on openwakeword vs. Porcupine and custom wake word training scope.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Architecture decisions are high confidence; specific version pins carry [VERIFY] markers throughout and must be checked against live PyPI/pub before locking. APScheduler v4 API and ElevenLabs Turkish TTS quality are LOW confidence. |
| Features | MEDIUM | Competitor feature analysis drawn from training knowledge through Aug 2025; Siri iOS 18, Alexa+, and Gemini Live features are well-documented. Rabbit R1 and Humane AI Pin failure analysis is MEDIUM confidence based on public reviews. |
| Architecture | MEDIUM-HIGH | Core patterns (FastAPI, Claude tool use loop, WCSession for Watch, HealthKit on-device-only, APNs via FCM) are stable and well-established. Latency estimates (faster-whisper ~200ms, ElevenLabs ~400-800ms) are MEDIUM — validate on target hardware. |
| Pitfalls | MEDIUM | Firebase security misconfiguration, LLM hallucination in personal memory, and notification fatigue are well-documented pitfalls (HIGH confidence). Turkish STT failure modes and ElevenLabs Turkish quality are MEDIUM confidence — require empirical testing. |

**Overall confidence:** MEDIUM

### Gaps to Address

- **ElevenLabs Turkish TTS quality:** Must be tested empirically at Phase 2 start. If Turkish voice quality is inadequate, evaluate Azure Cognitive Services `tr-TR` neural voices as replacement. This is the single highest-risk unverified assumption.
- **Whisper large-v3 Turkish WER on code-switched speech:** Known to be better than smaller models, but exact quality on urban Turkish code-switching is not validated. Define a WER acceptance test and pass it before advancing from Phase 2.
- **APScheduler v4 API:** v4 is a documented rewrite from v3 with API changes. Verify migration guide and correct API surface before Phase 5 planning.
- **openwakeword custom wake word training:** Requires ~200 positive audio samples. Scope decision needed early (custom "Hey VELAR" vs. generic trigger in v1). Picovoice Porcupine is the fallback if custom training proves too burdensome.
- **Supabase Flutter SDK maturity:** supabase_flutter v2 is newer than v1; compatibility with Flutter 3.22+ needs live verification. Firebase Firestore's Flutter SDK is more mature — if Supabase Flutter SDK proves problematic, this is the most likely stack swap.
- **Apple Watch voice handoff UX:** WCSession is documented for file and message transfer, but the latency of a voice command handoff (Watch → WCSession → iPhone → FastAPI → response → WCSession → Watch) needs real-hardware measurement before the Watch voice feature is committed.

---

## Sources

### Primary (HIGH confidence)
- Apple Developer documentation (WatchConnectivity, WCSession, HealthKit on-device policy, APNs) — Watch architectural constraints are platform policy, not subject to change
- Firebase Security Rules documentation — security misconfiguration pattern is extensively documented and repeatedly cited
- Claude API tool use pattern (Anthropic) — agentic loop is documented in official Anthropic reference

### Secondary (MEDIUM confidence)
- Training knowledge: FastAPI, Supabase, pgvector, faster-whisper, openwakeword — stable, widely-used libraries with documented APIs as of August 2025
- Training knowledge: Competitor analysis (Siri iOS 18, Google Gemini Live, Alexa+, Rabbit R1 April 2024 reviews, Humane AI Pin 2024 reviews + HP acquisition 2025)
- Training knowledge: Whisper large-v3 Turkish STT quality — well-reported in multilingual benchmarks; Turkish performance advantage of large-v3 over smaller models is established

### Tertiary (LOW confidence — validate before committing)
- ElevenLabs Turkish language voice availability and quality — must be empirically verified
- APScheduler v4 API surface — v4 is a rewrite; verify documentation before Phase 5
- Kokoro TTS (emerging open-source) — mentioned as possible ElevenLabs alternative by 2026; check status before locking TTS vendor
- All Python version pins in STACK.md — marked [VERIFY] throughout; check live PyPI before implementation

---
*Research completed: 2026-03-01*
*Ready for roadmap: yes*
