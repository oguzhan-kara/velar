# Requirements: VELAR

**Defined:** 2026-03-01
**Core Value:** VELAR thinks ahead for you — it anticipates what you need before you realize it yourself.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Voice & Interaction

- [ ] **VOICE-01**: User can activate VELAR with wake word ("Hey VELAR") on Mac
- [x] **VOICE-02**: User can speak naturally and VELAR understands via Whisper STT
- [x] **VOICE-03**: VELAR responds with premium natural voice via ElevenLabs/Edge TTS
- [x] **VOICE-04**: User can have a hands-free voice conversation without touching any screen
- [x] **VOICE-05**: User can mix Turkish and English in a single sentence and VELAR understands

### Memory & Learning

- [ ] **MEM-01**: VELAR stores personal facts about the user permanently (health, preferences, relationships, habits)
- [ ] **MEM-02**: User can ask VELAR what it knows about them and get accurate recall
- [ ] **MEM-03**: VELAR passively extracts facts from every conversation without explicit user action
- [ ] **MEM-04**: User can correct or delete facts VELAR has stored
- [ ] **MEM-05**: Memory persists across devices and sessions via cloud sync

### Proactive Engine

- [ ] **PROACT-01**: VELAR delivers a personalized morning briefing (weather + calendar + health patterns + social reminders + food suggestion)
- [ ] **PROACT-02**: VELAR sends push notifications for time-sensitive alerts (birthdays, appointments, reminders)
- [ ] **PROACT-03**: VELAR proactively surfaces relevant information without being asked (e.g., "you haven't eaten breakfast 3 days in a row")
- [ ] **PROACT-04**: User can configure notification frequency and quiet hours

### Food Advice

- [ ] **FOOD-01**: User can ask "what should I eat?" and get a personalized answer based on diet, allergies, and recent meals
- [ ] **FOOD-02**: VELAR tracks meals the user mentions and builds a dietary history
- [ ] **FOOD-03**: VELAR suggests restaurants near the user based on past visits and ratings
- [ ] **FOOD-04**: VELAR considers time of day, weather, and mood when suggesting food

### Social Advice

- [ ] **SOCL-01**: VELAR remembers people in the user's life (name, relationship, personality, important dates)
- [ ] **SOCL-02**: VELAR reminds the user about birthdays, anniversaries, and other important dates
- [ ] **SOCL-03**: User can ask VELAR to draft a message to someone with relationship context
- [ ] **SOCL-04**: VELAR suggests reconnecting with people the user hasn't contacted in a while

### Place Advice

- [ ] **PLACE-01**: User can ask "where should I go?" and get suggestions based on preferences and location
- [ ] **PLACE-02**: VELAR tracks places the user visits and their ratings/preferences
- [ ] **PLACE-03**: VELAR considers time of day, weather, mood, and companions when suggesting places

### Devices

- [ ] **DEV-01**: Mac daemon runs as always-on background service with wake word detection
- [ ] **DEV-02**: iPhone app (Flutter) provides voice input and chat interface
- [ ] **DEV-03**: iPhone app receives and displays push notifications from VELAR
- [ ] **DEV-04**: Apple Watch app (Swift) displays quick briefings and accepts voice commands
- [ ] **DEV-05**: Apple Watch relays commands to backend via iPhone (WCSession)

### Cross-Device Sync

- [ ] **SYNC-01**: Conversation context syncs across Mac, iPhone, and Apple Watch
- [x] **SYNC-02**: Memory and personal data accessible from any device
- [ ] **SYNC-03**: Notifications delivered to the most appropriate device

### Integrations

- [ ] **INTG-01**: VELAR reads the user's calendar events (Google Calendar or Apple Calendar)
- [ ] **INTG-02**: VELAR fetches current weather and forecast for user's location
- [ ] **INTG-03**: VELAR can set timers and reminders
- [ ] **INTG-04**: VELAR queries nearby places via Google Places API or similar

### Language

- [ ] **LANG-01**: VELAR understands and responds in Turkish
- [ ] **LANG-02**: VELAR understands and responds in English
- [ ] **LANG-03**: VELAR handles code-switching (Turkish-English mixed sentences) naturally

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Smart Home

- **HOME-01**: User can control HomeKit devices via voice ("turn off the lights")
- **HOME-02**: VELAR integrates with Apple Home scenes

### Advanced Features

- **ADV-01**: Mood-aware response adjustment based on voice sentiment or health data
- **ADV-02**: HealthKit integration for sleep/activity data as context
- **ADV-03**: Android companion app

## Out of Scope

| Feature | Reason |
|---------|--------|
| Offline LLM inference | Requires 7B+ model on-device; quality degrades; 80% of features need internet anyway |
| Financial/banking integration | PCI compliance, regulatory risk, privacy landmine — VELAR notes facts from conversation instead |
| Third-party plugin/skill system | Alexa's 100k skills proved discoverability fails; first-party curated integrations only |
| Full conversation transcript storage | Privacy risk — store extracted facts, not raw transcripts |
| Autonomous social media posting | One bad auto-post destroys trust; VELAR drafts for review, never posts autonomously |
| Computer vision / camera features | Humane AI Pin proved camera-first is slow and battery-intensive; voice-first is proven |
| Real-time streaming everywhere | WebSocket from all devices = complexity and battery drain; scheduled checks + push is sufficient |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| VOICE-01 | Phase 2 | Pending |
| VOICE-02 | Phase 2 | Complete |
| VOICE-03 | Phase 2 | Complete |
| VOICE-04 | Phase 2 | Complete |
| VOICE-05 | Phase 2 | Complete |
| MEM-01 | Phase 3 | Pending |
| MEM-02 | Phase 3 | Pending |
| MEM-03 | Phase 3 | Pending |
| MEM-04 | Phase 3 | Pending |
| MEM-05 | Phase 3 | Pending |
| PROACT-01 | Phase 5 | Pending |
| PROACT-02 | Phase 5 | Pending |
| PROACT-03 | Phase 5 | Pending |
| PROACT-04 | Phase 5 | Pending |
| FOOD-01 | Phase 7 | Pending |
| FOOD-02 | Phase 7 | Pending |
| FOOD-03 | Phase 7 | Pending |
| FOOD-04 | Phase 7 | Pending |
| SOCL-01 | Phase 7 | Pending |
| SOCL-02 | Phase 7 | Pending |
| SOCL-03 | Phase 7 | Pending |
| SOCL-04 | Phase 7 | Pending |
| PLACE-01 | Phase 7 | Pending |
| PLACE-02 | Phase 7 | Pending |
| PLACE-03 | Phase 7 | Pending |
| DEV-01 | Phase 4 | Pending |
| DEV-02 | Phase 6 | Pending |
| DEV-03 | Phase 5 | Pending |
| DEV-04 | Phase 7 | Pending |
| DEV-05 | Phase 7 | Pending |
| SYNC-01 | Phase 6 | Pending |
| SYNC-02 | Phase 1 | Complete |
| SYNC-03 | Phase 5 | Pending |
| INTG-01 | Phase 4 | Pending |
| INTG-02 | Phase 4 | Pending |
| INTG-03 | Phase 4 | Pending |
| INTG-04 | Phase 4 | Pending |
| LANG-01 | Phase 2 | Pending |
| LANG-02 | Phase 2 | Pending |
| LANG-03 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 40 total
- Mapped to phases: 40
- Unmapped: 0

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-01 after roadmap creation — all 40 v1 requirements mapped*
