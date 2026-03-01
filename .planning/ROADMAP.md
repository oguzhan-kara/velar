# Roadmap: VELAR

## Overview

VELAR is built bottom-up along a strict dependency chain. The foundation comes first (backend, auth, cloud storage, security), then the core interaction loop (voice + language), then the memory system that makes every downstream feature meaningful. From there the Mac daemon establishes the ambient always-on experience, the proactive engine delivers the signature morning briefing, and the iPhone app brings full mobile capability. The Apple Watch and advice features (food, social, place) close out v1 — these depend on accumulated memory data and are rightly last.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Backend, Supabase, auth, security, and cloud data layer (completed 2026-03-01)
- [ ] **Phase 2: Voice Pipeline** - STT, TTS, Claude tool loop, and bilingual language support
- [ ] **Phase 3: Memory System** - Personal knowledge graph with semantic retrieval
- [ ] **Phase 4: Mac Daemon and Integrations** - Always-on Mac service, wake word, and external data tools
- [ ] **Phase 5: Proactive Engine** - Morning briefing, push notifications, and proactive scheduling
- [ ] **Phase 6: iPhone App** - Flutter mobile client with voice, chat, sync, and push
- [ ] **Phase 7: Watch App and Advice Features** - Apple Watch satellite and memory-backed food, social, place advice

## Phase Details

### Phase 1: Foundation
**Goal**: A secure, running backend that can store personal data and authenticate a user
**Depends on**: Nothing (first phase)
**Requirements**: SYNC-02
**Success Criteria** (what must be TRUE):
  1. FastAPI service runs locally and in Docker, returns 200 on /health
  2. User can authenticate via Supabase and receive a session token that the API accepts
  3. Personal data tables (user profile, facts, conversations) exist in Supabase with row-level security policies that block access from a non-owner test account
  4. All secrets (API keys, DB credentials) are injected via environment variables — none hardcoded in source
  5. Memory and personal data schema is accessible from any authenticated device (Supabase cloud-backed)
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md — FastAPI project scaffold, Docker dev environment, pydantic-settings config, async database layer, health endpoint, and Supabase schema migration (all personal data tables with pgvector)
- [ ] 01-02-PLAN.md — Supabase Auth integration (login endpoint), JWT dependency injection, /users/me protected endpoint, and pytest suite including RLS isolation test

### Phase 2: Voice Pipeline
**Goal**: Users can speak to VELAR and receive a premium voice response in Turkish or English
**Depends on**: Phase 1
**Requirements**: VOICE-01, VOICE-02, VOICE-03, VOICE-04, VOICE-05, LANG-01, LANG-02, LANG-03
**Success Criteria** (what must be TRUE):
  1. User can activate VELAR with the wake word "Hey VELAR" on Mac without touching the keyboard
  2. User can speak a natural sentence and VELAR transcribes it accurately via Whisper STT (Turkish WER under 15% on 50 common assistant commands)
  3. VELAR responds with a premium, natural-sounding voice (ElevenLabs or verified fallback) — not robotic
  4. A complete voice round-trip (speak → hear response) completes in under 4 seconds perceived latency
  5. User can speak a mixed Turkish-English sentence (e.g., "VELAR, bugün calendar'da ne var?") and VELAR understands and responds coherently
**Plans**: TBD

Plans:
- [ ] 02-01: faster-whisper STT integration with Turkish acceptance test and VAD
- [ ] 02-02: Claude tool-use loop scaffold (no tools yet) and ElevenLabs/Edge-TTS integration
- [ ] 02-03: Language handling (Turkish, English, code-switching) and voice round-trip end-to-end test

### Phase 3: Memory System
**Goal**: VELAR stores, retrieves, and learns from personal facts about the user permanently and accurately
**Depends on**: Phase 2
**Requirements**: MEM-01, MEM-02, MEM-03, MEM-04, MEM-05
**Success Criteria** (what must be TRUE):
  1. User can tell VELAR a personal fact ("I'm allergic to nuts") and VELAR recalls it correctly in a later session
  2. User can ask "What do you know about me?" and receive an accurate summary of stored facts — no invented facts
  3. After a conversation, VELAR automatically extracts and stores new facts without the user explicitly saying "remember this"
  4. User can correct or delete a stored fact ("That's wrong, I'm not allergic anymore") and VELAR stops using the old fact
  5. Stored memory is accessible from any device — a fact learned on Mac appears when querying from iPhone
**Plans**: TBD

Plans:
- [ ] 03-01: Supabase schema (entity-attribute-value triples), pgvector embeddings, and semantic retrieval with 2000-token cap
- [ ] 03-02: Async memory extraction pipeline, fact versioning (supersede pattern), hallucination guard, and /memory CRUD API

### Phase 4: Mac Daemon and Integrations
**Goal**: VELAR runs as an always-on ambient service on Mac and can fetch real-world context (calendar, weather, places, reminders)
**Depends on**: Phase 3
**Requirements**: DEV-01, INTG-01, INTG-02, INTG-03, INTG-04
**Success Criteria** (what must be TRUE):
  1. VELAR starts automatically on Mac boot and runs silently in the menu bar without any user action
  2. User can say "Hey VELAR" from across the room with no apps open and get a response
  3. VELAR can tell the user their next calendar event when asked
  4. VELAR can report current weather and forecast for the user's location
  5. User can ask VELAR to set a reminder and it is created
**Plans**: TBD

Plans:
- [ ] 04-01: Mac Python daemon with openwakeword wake word detection, sounddevice audio capture, VAD, and launchd boot persistence
- [ ] 04-02: Integration tools — Google/Apple Calendar (OAuth2), OpenWeatherMap weather, Google Places API, and timer/reminder tool

### Phase 5: Proactive Engine
**Goal**: VELAR proactively delivers a morning briefing and sends time-sensitive alerts without being asked
**Depends on**: Phase 4
**Requirements**: PROACT-01, PROACT-02, PROACT-03, PROACT-04, DEV-03, SYNC-03
**Success Criteria** (what must be TRUE):
  1. At a user-configured time each morning, VELAR delivers a spoken briefing covering weather, calendar events, a health/habit observation, and a social reminder — all personalized from memory
  2. User receives a push notification on iPhone for a time-sensitive event (birthday, appointment) without asking for it
  3. VELAR surfaces a proactive observation at least once ("you haven't logged breakfast in 3 days") that is accurate and relevant
  4. User can configure quiet hours and VELAR respects them — no notifications outside those hours
  5. Notifications are delivered to the most relevant device (iPhone when away from Mac, Mac when active)
**Plans**: TBD

Plans:
- [ ] 05-01: APScheduler proactive engine, morning briefing job (weather + calendar + memory → Claude → FCM), and Firebase Cloud Messaging setup
- [ ] 05-02: Notification relevance scoring, quiet hours config, dismissal rate tracking, and proactive observation triggers

### Phase 6: iPhone App
**Goal**: User can interact with VELAR fully from their iPhone — voice, chat, memory review, and push notifications
**Depends on**: Phase 5
**Requirements**: DEV-02, SYNC-01, SYNC-03
**Success Criteria** (what must be TRUE):
  1. User can open the iPhone app, tap to speak, and complete a full voice conversation with VELAR
  2. User can read and delete facts VELAR has stored about them from within the app
  3. A conversation started on Mac continues seamlessly on iPhone — context is not lost between devices
  4. User receives and can act on push notifications from VELAR on iPhone
**Plans**: TBD

Plans:
- [ ] 06-01: Flutter app scaffold with Supabase auth (Apple Sign-In), Riverpod state, voice recording (record package), and streaming TTS playback
- [ ] 06-02: Chat text interface, memory review/delete UI, FCM push notification handling, and cross-device conversation sync

### Phase 7: Watch App and Advice Features
**Goal**: Users get VELAR on their wrist as a glance device and receive personalized food, social, and place advice backed by real memory data
**Depends on**: Phase 6
**Requirements**: DEV-04, DEV-05, FOOD-01, FOOD-02, FOOD-03, FOOD-04, SOCL-01, SOCL-02, SOCL-03, SOCL-04, PLACE-01, PLACE-02, PLACE-03
**Success Criteria** (what must be TRUE):
  1. User can glance at Apple Watch in the morning and see their briefing headline without touching the phone
  2. User can raise their wrist and speak a quick voice command — it is processed and answered via iPhone relay
  3. User asks "what should I eat?" and receives a suggestion that accounts for their dietary restrictions, recent meals, time of day, and weather — not a generic answer
  4. VELAR reminds the user of an upcoming birthday or anniversary before the day arrives
  5. User asks "where should I go?" and receives place suggestions based on past visits, current location, and the weather
**Plans**: TBD

Plans:
- [ ] 07-01: Swift WatchKit app with WCSession relay, morning briefing headline, and voice command handoff to iPhone
- [ ] 07-02: Food advice tools (dietary profile, meal history, restaurant suggestions) and place advice tools (visit history, Google Places, context-aware suggestions)
- [ ] 07-03: Social advice features (relationship memory graph, birthday/anniversary reminders, message drafting with relationship context)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 2/2 | Complete    | 2026-03-01 |
| 2. Voice Pipeline | 0/3 | Not started | - |
| 3. Memory System | 0/2 | Not started | - |
| 4. Mac Daemon and Integrations | 0/2 | Not started | - |
| 5. Proactive Engine | 0/2 | Not started | - |
| 6. iPhone App | 0/2 | Not started | - |
| 7. Watch App and Advice Features | 0/3 | Not started | - |
