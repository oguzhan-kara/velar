# Feature Research

**Domain:** Proactive personal AI assistant (voice-first, ambient, memory-backed)
**Researched:** 2026-03-01
**Confidence:** MEDIUM (training knowledge through Aug 2025; web verification unavailable in this session — flag for validation before implementation)

---

## Research Basis

This analysis covers: Siri (Apple, iOS 18 / macOS Sequoia era), Google Assistant (post-Gemini integration), Amazon Alexa (Alexa+/LLM upgrade 2024), Rabbit R1, Humane AI Pin, and community Jarvis-like personal assistant builds. Confidence is MEDIUM overall — these are well-documented public products, but I could not verify against live sources. Critical claims are marked with confidence levels inline.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that users expect from any AI assistant. Missing these = product feels broken or incomplete before they even get to the differentiating features.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Wake word activation ("Hey VELAR") | Every AI assistant since Alexa (2014) has established this as the minimum entry point | MEDIUM | Requires always-on mic with local keyword detection — high privacy sensitivity; must run on-device |
| Natural language understanding (NLU) | Users expect to speak normally, not issue structured commands | HIGH | Claude API handles this — no custom NLU needed, but prompt engineering for Turkish requires care |
| Voice response with natural TTS | A purely text-responding voice assistant feels broken | MEDIUM | ElevenLabs or Edge TTS; robotic voice is a dealbreaker — Humane AI Pin was criticized harshly for this |
| Calendar integration | Siri and Google Assistant both made this a baseline expectation in 2015 | MEDIUM | EventKit (iOS/macOS) for read access; write access requires user permission flow |
| Weather information | The single most-asked assistant question historically | LOW | Open-Meteo or Apple Weather API; straightforward |
| Timer / reminder setting | Alexa built mass adoption on this; it is now universally expected | LOW | Local notifications + cloud persistence; trivial UX, important reliability |
| Question answering (general knowledge) | ChatGPT (2022) shifted expectations — users now expect substantive answers, not search links | MEDIUM | Claude API handles; context window management needed for long sessions |
| Hands-free operation | Voice-first means no required screen interaction | MEDIUM | Requires clean audio pipeline: mic → VAD → STT → LLM → TTS, all chained |
| Push notifications for alerts | Users expect to be reached when something time-sensitive happens | LOW | APNs (iOS), UNUserNotificationCenter; standard |
| Cross-device continuity | Apple's own Handoff established this expectation in 2014; users expect start-on-Mac / finish-on-iPhone | HIGH | Requires shared backend state; session context must be cloud-synced |
| Conversation history | Since ChatGPT, users expect the assistant to remember the current session at minimum | MEDIUM | Session context in database; straightforward but grows in complexity with long-term memory |
| App/service integrations | Siri can call Uber, play Spotify; users expect their assistant to connect to their apps | HIGH | Tool use via Claude API; each integration is a separate connector — start narrow |
| Multi-language support (Turkish + English) | For a Turkish-speaking user this is non-negotiable; mixing languages in one sentence is common | MEDIUM | Claude handles bilingual well; STT must support both (Whisper does); TTS must pronounce both correctly |

### Differentiators (Competitive Advantage)

Features that distinguish VELAR from existing assistants. These are where VELAR wins or loses against Siri, Google Assistant, etc.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Proactive morning briefing | No existing consumer assistant generates a cohesive, personalized daily narrative — Siri gives fragments; Google gives cards; VELAR speaks a unified brief | HIGH | Requires aggregating weather + calendar + health + social + food memory into one coherent LLM prompt; this is the signature demo |
| Personal memory system (long-term) | Siri/Google/Alexa have no persistent personal memory across sessions beyond saved preferences; VELAR knows your allergies, last haircut, your mother's birthday | HIGH | Vector DB (pgvector or Pinecone) + structured profile store; memory extraction from every conversation is a continuous background job |
| Food advice from personal diet history | "What should I eat tonight?" with context of recent meals, allergies, mood, cuisine preferences — nobody does this | HIGH | Requires dietary profile, meal history log, mood tracking integration, restaurant awareness; Claude tool use |
| Place advice from visit history | Suggesting where to go based on past visits, time of day, mood, who you're with — Foursquare tried this but without AI | HIGH | Location history + preference model + external place API (Google Places or Apple Maps API) |
| Social advice / relationship memory | Drafting a message to a friend with context of your relationship history, last conversation, their personality — nothing in market does this | HIGH | Relationship graph in personal memory; requires user to volunteer data or VELAR extracts from conversations |
| Passive learning from conversations | VELAR learns who you are from every interaction without requiring explicit data entry — you mention you hate cilantro, it remembers | HIGH | Background NLP pipeline extracting entities/facts after each conversation; stores to memory system |
| Ambient Apple Watch briefing | Quick spoken briefings on wrist raise — no competitor does truly personalized spoken briefings on Watch | HIGH | WatchOS native app in Swift; TTS must work on Watch; tight latency requirements |
| Bilingual code-switching | Responding naturally when user mixes Turkish and English in one sentence (common among bilingual speakers) | MEDIUM | Claude handles this well; Whisper STT supports it; mostly a prompt design concern |
| Mood-aware responses | Adjusting tone and content based on detected mood from voice or recent health data | HIGH | Sentiment analysis on STT output or Apple Health sleep/HRV data as mood proxy; genuinely novel |
| Unified proactive identity ("VELAR thinks for you") | Competitors are reactive; VELAR reaches out with relevant information unprompted | HIGH | Scheduled inference jobs running in cloud; push delivery; requires rich enough memory to generate genuinely useful proactive messages |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like good ideas but create real problems — either user trust, technical complexity, or product dilution.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Offline mode | Users fear losing access without internet | Offline LLM inference requires 7B+ model on-device; Apple Silicon handles it but latency and quality degrade severely; 80% of use cases need internet anyway (calendar, weather, places) | Graceful degradation: local wake word works offline, notifies user that cloud features need connectivity; save queries for when connection returns |
| Smart home control (HomeKit) | Jarvis controls Iron Man's home; users will request this immediately | Massively increases scope (dozens of device types, authorization flows, failure modes); dilutes proactive assistant identity into a home hub | Defer to v2 explicitly; the MORNING BRIEFING is more Jarvis than turning lights on |
| Financial advice / banking integration | "Track my spending" feels natural for a personal assistant | PCI compliance, open banking API complexity, regulatory risk, privacy landmines; Mint failed, Plaid lawsuits; destroys trust if data leaks | VELAR can note "you mentioned your rent is due" from conversation memory without connecting to bank accounts; never touch financial data directly |
| Real-time everything (live updates, streaming data) | Feels more "alive" and responsive | WebSocket connections from all devices = complex infrastructure, battery drain, always-on data usage; for most proactive use cases batch/scheduled is sufficient | Scheduled proactive jobs (every 15 min background check); push notification when something time-sensitive occurs |
| "Build your own skill" platform (third-party plugins) | Alexa's skill store seemed like a great idea | Alexa has 100,000+ skills and users can't discover them; third-party quality is uneven; support burden explodes; plugin security model is complex | Keep integrations first-party and curated in v1; build plugin system only after core is proven |
| Full conversation transcripts / history UI | Users want to see everything VELAR knows | Privacy: storing full transcripts of intimate personal conversations creates an enormous breach-of-trust risk if compromised | Store extracted facts and structured memories, not full transcripts; offer fact review/delete UI instead |
| Android support (v1) | Larger global market | WatchOS integration is native Swift; Android fragmentation makes ambient always-on mic and Watch integration far harder; splitting focus in v1 kills delivery | Apple-first, Android in v2 after core is proven |
| Computer vision / camera features | "See what I see" felt like the Humane AI Pin's biggest promise | Humane AI Pin failed partly because camera-based inference was slow (3-7 seconds), battery-intensive, and context was shallow; the vision-as-primary-interface model is unproven | Voice-first is proven; add vision as an enhancement later, not a core mode |
| Social media posting / account management | "Post this for me" is a natural voice command | Unintended posts cause real harm; AI-generated social content has trust and authenticity issues; one bad auto-post damages user relationship with VELAR permanently | VELAR drafts messages for review; never posts autonomously without explicit confirmation |

---

## Feature Dependencies

```
[Personal Memory System]
    └──requires──> [Passive Learning Pipeline]
    └──requires──> [Cloud Data Storage (Firebase/Supabase)]
    └──enables──>  [Food Advice]
    └──enables──>  [Social Advice]
    └──enables──>  [Proactive Morning Briefing]
    └──enables──>  [Place Advice]
    └──enables──>  [Mood-Aware Responses]

[Wake Word Detection]
    └──requires──> [Always-on mic (on-device, local)]
    └──enables──>  [Voice-First Interaction]

[Voice-First Interaction]
    └──requires──> [Wake Word Detection]
    └──requires──> [STT (Whisper)]
    └──requires──> [LLM (Claude API)]
    └──requires──> [TTS (ElevenLabs / Edge TTS)]
    └──enables──>  [Morning Briefing]
    └──enables──>  [Apple Watch Briefing]

[Morning Briefing]
    └──requires──> [Voice-First Interaction]
    └──requires──> [Calendar Integration]
    └──requires──> [Weather Integration]
    └──requires──> [Personal Memory System]
    └──requires──> [Push Notifications]

[Apple Watch App]
    └──requires──> [Swift native development]
    └──requires──> [Cloud sync (shared state with iPhone/Mac)]
    └──requires──> [Voice-First Interaction (Watch microphone)]
    └──enhances──> [Morning Briefing]

[Cross-Device Continuity]
    └──requires──> [Cloud Data Storage]
    └──requires──> [Shared session state]
    └──enables──>  [Apple Watch App] (Watch as satellite device)

[Social Advice]
    └──requires──> [Personal Memory System]
    └──enhances──> [Morning Briefing] (adds relationship reminders)

[Food Advice]
    └──requires──> [Personal Memory System]
    └──enhances──> [Morning Briefing] (adds meal suggestions)

[Passive Learning]
    └──requires──> [Voice-First Interaction] (source of data)
    └──feeds──>    [Personal Memory System]

[Mood-Aware Responses]
    └──requires──> [Personal Memory System] (for baseline)
    └──enhances──> [Food Advice], [Social Advice], [Morning Briefing]
```

### Dependency Notes

- **Personal Memory System is the foundation:** Nearly every differentiating feature depends on it. If memory is weak, food/social/place advice collapse to generic responses that are no better than ChatGPT. This must be built first and built well.
- **Morning Briefing requires 4+ integrations:** Calendar + Weather + Memory + Voice must all work before the signature demo is possible. Build each integration separately; assemble into briefing last.
- **Apple Watch requires Swift:** Flutter's WatchOS support is insufficient for ambient, always-on features. The Watch app is a dependency blocker that requires dedicated native development.
- **Passive Learning conflicts with Full Transcript Storage:** These two should not coexist — extract facts and discard raw transcripts to minimize privacy exposure.

---

## MVP Definition

### Launch With (v1) — What Validates the Core Concept

The minimum viable VELAR that proves "proactive AI assistant beats reactive assistants" as a thesis.

- [ ] Wake word activation ("Hey VELAR") on Mac — validates always-on ambient pattern
- [ ] Voice-first conversation (Whisper STT → Claude API → ElevenLabs TTS) — validates the interaction model
- [ ] Morning Briefing: weather + calendar + one memory fact — validates proactive identity
- [ ] Personal Memory System (basic): store/retrieve facts from conversations — validates the core differentiator
- [ ] iPhone app: voice + chat interface — validates mobile use case
- [ ] Push notifications for time-sensitive alerts — validates proactive reach-out
- [ ] Turkish + English support — non-negotiable from day one per project constraints
- [ ] Cloud sync (Mac → iPhone) — validates cross-device continuity
- [ ] Food advice (basic): ask VELAR what to eat, get answer using dietary profile + recent meal memory — validates memory-powered advice

### Add After Validation (v1.x)

Add once core morning briefing + memory system is working and getting real daily use.

- [ ] Apple Watch app — trigger when daily voice interaction habits are established
- [ ] Social advice (relationship memory, message drafting) — trigger when memory system has 2+ weeks of data
- [ ] Place advice (location + preference-based suggestions) — trigger when food advice loop is validated
- [ ] Passive learning pipeline (background fact extraction after each conversation) — trigger when manual fact entry proves value
- [ ] Mood-aware responses — trigger when voice interaction data accumulates

### Future Consideration (v2+)

Defer until product-market fit is established with daily active use.

- [ ] Smart home control (HomeKit) — only if users explicitly request and core assistant identity is solid
- [ ] Plugin/skill system for third-party integrations — only if user base justifies the support burden
- [ ] Android app — after Apple ecosystem is polished
- [ ] Computer vision features — after voice-first is proven
- [ ] Full offline mode — after cloud-first model is validated

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Wake word + voice pipeline (STT→LLM→TTS) | HIGH | MEDIUM | P1 |
| Morning Briefing (weather + calendar) | HIGH | MEDIUM | P1 |
| Personal Memory System (store/retrieve facts) | HIGH | HIGH | P1 |
| Push notifications | MEDIUM | LOW | P1 |
| iPhone app (Flutter, voice + chat) | HIGH | MEDIUM | P1 |
| Turkish + English support | HIGH | LOW | P1 |
| Cloud sync (Mac ↔ iPhone) | HIGH | MEDIUM | P1 |
| Food advice (memory-backed) | HIGH | MEDIUM | P1 |
| Passive learning pipeline | HIGH | HIGH | P2 |
| Apple Watch app (Swift) | MEDIUM | HIGH | P2 |
| Social advice / relationship memory | HIGH | HIGH | P2 |
| Place advice | MEDIUM | HIGH | P2 |
| Mood-aware responses | MEDIUM | HIGH | P3 |
| Smart home control (HomeKit) | LOW | HIGH | DEFER |
| Plugin/skill system | LOW | HIGH | DEFER |
| Offline mode | LOW | HIGH | DEFER |

**Priority key:**
- P1: Must have for launch — without these, the core thesis cannot be validated
- P2: Should have — add these to make daily use compelling beyond the initial wow-moment
- P3: Nice to have — adds depth but not critical path
- DEFER: Explicitly out of v1 scope

---

## Competitor Feature Analysis

| Feature | Siri (iOS 18) | Google Assistant | Alexa | Rabbit R1 | Humane AI Pin | VELAR Approach |
|---------|--------------|-----------------|-------|-----------|---------------|----------------|
| Wake word | "Hey Siri" (on-device) | "Hey Google" | "Alexa" | Physical button | Physical button | "Hey VELAR" (on-device, Mac + iPhone) |
| Proactive morning briefing | "Good Morning" routine (fragmentary) | Daily briefing (fragmentary) | Flash briefing (news-focused) | None | None | Unified personalized spoken narrative |
| Long-term personal memory | Minimal (saved preferences only) | Limited (Google account signals) | Limited (history, no inference) | None | None | Core differentiator — full personal knowledge graph |
| Food advice | None | Basic (recipe search) | Basic (Alexa skill) | None | None | Memory-backed: diet, allergies, recent meals, mood |
| Social advice | None | None | None | None | None | Relationship memory + message drafting |
| Voice quality | Natural (good) | Natural (good) | Improving (LLM upgrade) | Average | Poor (criticized) | Premium (ElevenLabs) — Jarvis-level |
| Passive learning | None | Implicit (Google account) | None | None | None | Explicit: extracts facts from every conversation |
| Cross-device | Handoff (good) | Limited | Echo → app | Single device | Single device | Mac + iPhone + Watch, cloud-backed |
| Multi-language | 40+ languages | 40+ languages | Limited | English-first | English-first | Turkish + English, code-switching |
| Ambient / always-on | Yes (AirPods, HomePod) | Yes (Home devices) | Yes (Echo always on) | No (button press) | No (button press) | Yes — Mac + iPhone + Watch |
| Smart home | HomeKit (good) | Google Home (good) | Alexa ecosystem (best) | Limited | None | Explicitly deferred to v2 |
| Third-party integrations | Siri Shortcuts (limited) | Actions (good) | Skills (100k+, discoverability problem) | LAM (limited) | None | First-party curated in v1 |

### Key Insights from Competitor Analysis

**Where mainstream assistants fail (VELAR's opportunity):**
1. **No persistent memory.** Siri, Alexa, Google Assistant all reset between sessions. A user's dietary restrictions, relationship context, personal preferences — none persist. This is VELAR's largest gap to exploit.
2. **Reactive only.** Every mainstream assistant waits to be asked. Google Assistant's "suggestions" are shallow and card-based, not voice-proactive. Nobody initiates a meaningful daily briefing.
3. **Generic responses.** Because there's no personal memory, all advice is generic. "What should I eat?" gets a recipe search, not a personalized answer.
4. **Rabbit R1 failure lesson (confidence: MEDIUM — based on public reviews through Aug 2025):** The device failed because: (a) the LAM (Large Action Model) was underdeveloped and couldn't reliably take app actions, (b) the AI felt gimmicky without genuine memory or personalization, (c) hardware-as-differentiator failed when the software experience didn't deliver. VELAR is software-only and Apple-native — avoiding the hardware trap.
5. **Humane AI Pin failure lesson (confidence: MEDIUM):** The pin failed because: (a) camera-first was slow and battery-intensive, (b) no memory meant every interaction started cold, (c) premium hardware price without premium software experience. VELAR is voice-first (proven modality) and cloud-backed (no battery constraint for inference).

---

## Sources

- Apple Siri feature set: Training knowledge through Aug 2025 — MEDIUM confidence. Covers iOS 17/18 Siri features post-Apple Intelligence announcement.
- Google Assistant / Gemini: Training knowledge through Aug 2025 — MEDIUM confidence. Covers Gemini Live integration announced at I/O 2024.
- Amazon Alexa: Training knowledge through Aug 2025 — MEDIUM confidence. Covers Alexa+ LLM upgrade announced Nov 2023.
- Rabbit R1: Training knowledge through Aug 2025 — MEDIUM confidence. Product launched April 2024; extensive public reviews available.
- Humane AI Pin: Training knowledge through Aug 2025 — MEDIUM confidence. Product launched April 2024; reviewed by Marques Brownlee and major tech press; company announced sale to HP in 2025.
- Jarvis-like personal assistant patterns: Training knowledge synthesized from open-source projects (e.g., community Jarvis builds using LangChain/Claude) — LOW-MEDIUM confidence.
- Note: Web verification was unavailable in this research session. All findings should be spot-checked against current product pages before implementation decisions are finalized.

---

*Feature research for: Proactive personal AI assistant (VELAR)*
*Researched: 2026-03-01*
