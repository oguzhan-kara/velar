# VELAR

## What This Is

VELAR is a proactive personal AI assistant — like Jarvis from Iron Man — that knows everything about its user and thinks ahead. It runs ambient across Mac, iPhone, and Apple Watch, delivering voice-first interactions in Turkish and English. Instead of waiting to be asked, VELAR aggregates weather, calendar, health patterns, relationships, and habits to proactively advise what to eat, where to go, what to say, and what not to forget.

## Core Value

VELAR thinks ahead for you — it doesn't wait to be asked, it anticipates what you need before you realize it yourself.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Voice-first interaction with wake word ("Hey VELAR")
- [ ] Proactive morning briefing (weather, calendar, health, social reminders)
- [ ] Personal memory system that learns everything about the user over time
- [ ] Food advice based on diet, allergies, recent meals, and mood
- [ ] Place advice based on location, preferences, and visit history
- [ ] Social advice (draft messages, birthday reminders, relationship context)
- [ ] Passive learning — extracts facts from every conversation automatically
- [ ] Push notifications for proactive alerts (reminders, suggestions, warnings)
- [ ] iPhone app (Flutter) with voice input and chat interface
- [ ] Apple Watch app (Swift) for quick commands and briefings
- [ ] Mac app/service with wake word detection and voice interaction
- [ ] Cross-device sync — start on Mac, get follow-up on iPhone
- [ ] Turkish and English language support (understand and respond in both)
- [ ] Cloud-backed personal data storage (Firebase/Supabase)
- [ ] Claude API as the reasoning brain with tool use

### Out of Scope

- Native Android app — Apple ecosystem first, Android later
- Smart home control (HomeKit) — defer to v2 after core advice system works
- Financial advice / banking integration — privacy and regulatory complexity
- Video/camera-based features (face detection, gesture control) — v2+
- Offline mode — cloud-first, offline fallback deferred

## Context

- Builder (Oguzhan) has Python, Flutter, AWS, and Docker experience from Mercedes-Benz background
- Flutter is the preferred mobile framework — already in the builder's toolkit
- Apple Watch requires native Swift (Flutter WatchOS support is limited)
- Claude API provides tool use capabilities essential for the "do stuff" part of the assistant
- The "Morning Briefing" is the signature demo: VELAR speaks proactively on wake-up, aggregating weather + calendar + health patterns + restaurant preferences + social memory into one personalized briefing
- Personal-first design, but architecture should support multi-user later
- ElevenLabs or Edge TTS for voice output quality (Jarvis-like voice)
- Whisper for speech-to-text (best quality, can run locally)

## Constraints

- **Platform**: Apple ecosystem first (Mac, iPhone, Apple Watch) — no Android in v1
- **AI Provider**: Claude API for reasoning — central to architecture
- **Languages**: Must support Turkish and English from day one
- **Data**: Cloud-hosted (Firebase/Supabase) — not self-hosted, not local-only
- **Voice Quality**: Must sound premium — ElevenLabs-tier, not robotic
- **Privacy**: Stores deeply personal data — encryption and auth are non-negotiable even for personal use

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Flutter for iPhone app | Builder's existing expertise, fast development | — Pending |
| Swift for Apple Watch | Flutter WatchOS support too limited | — Pending |
| Cloud storage (Firebase/Supabase) | Managed service, easy sync, low ops burden | — Pending |
| Claude API as brain | Tool use capability, reasoning quality, builder preference | — Pending |
| Voice-first interaction | The "Jarvis moment" is the core identity of VELAR | — Pending |
| Proactive over reactive | Morning briefing demo defines the product — thinking ahead is the differentiator | — Pending |

---
*Last updated: 2026-03-01 after initialization*
