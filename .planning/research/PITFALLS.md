# Pitfalls Research

**Domain:** Proactive personal AI assistant (voice-first, cross-device, LLM-powered, deep personal data)
**Researched:** 2026-03-01
**Confidence:** MEDIUM — based on established engineering patterns, Claude API documentation knowledge, and known failure modes from analogous systems (Siri, Google Assistant, personal assistant OSS projects). External search tools unavailable; flagged LOW where currency matters most.

---

## Critical Pitfalls

### Pitfall 1: Unbounded Memory Growth Without Retrieval Strategy

**What goes wrong:**
Every conversation appends new "facts" to a flat memory store. After weeks of use, the memory blob grows to tens of thousands of tokens. At retrieval time, either (a) everything gets stuffed into context — blowing the token budget and costs — or (b) naive keyword search returns irrelevant facts. The assistant starts confidently answering with stale or contradicted information.

**Why it happens:**
Memory is modeled as append-only logging (like a database journal) rather than as a living knowledge graph. Developers treat "save everything" as the safe option without defining when facts expire, supersede each other, or lose relevance.

**How to avoid:**
- Use a vector store (Pinecone, Supabase pgvector) with semantic retrieval — never full-dump into context.
- Implement fact versioning: when a new fact contradicts an older one (e.g., "user switched from keto to Mediterranean diet"), mark the old fact as superseded, don't delete.
- Apply TTL-like decay: preference facts should have a review date; stale facts should be flagged, not silently used.
- Cap context injection: define a maximum token budget for memory (e.g., 2000 tokens), retrieved by relevance to current query.
- Separate episodic memory (what happened when) from semantic memory (stable facts about the user).

**Warning signs:**
- Claude API calls exceeding 50k tokens regularly.
- Assistant contradicts itself between sessions.
- Response latency growing week over week (more data → slower retrieval).
- User corrects VELAR about something it "should know."

**Phase to address:**
Memory system phase (before any proactive features are built — proactive features depend on reliable memory).

---

### Pitfall 2: Proactive Notifications That Become Noise

**What goes wrong:**
The "proactive assistant" ships with aggressive notification logic. Within days, the user starts ignoring all push notifications because they're too frequent, poorly timed, or state the obvious. Once users disable notifications or develop notification blindness, VELAR's core value proposition is dead — and re-earning trust requires deliberate re-engagement effort.

**Why it happens:**
Developers optimize for recall (covering every possible helpful moment) rather than precision (only surfacing notifications worth interrupting the user for). The heuristic "more notifications = more helpful" is exactly backwards for ambient assistants.

**How to avoid:**
- Define a notification relevance score before shipping any proactive feature. A notification only fires if it exceeds a threshold that the user can tune.
- Default to low-frequency proactive behavior. The morning briefing is a single daily interrupt at a user-chosen time — not scattered pushes throughout the day.
- Implement a "quiet hours" window from day one (not as a later feature).
- Group related notifications: one push for "3 things you should know this morning," not 3 separate pushes.
- Track notification dismissal rate per category; auto-suppress categories with >70% dismissal.
- Never notify about things the user can trivially check themselves (current temperature, time of next calendar event they can see on their watch).

**Warning signs:**
- User manually turns off notification categories in iOS settings.
- Notification open rate dropping below 30% within the first two weeks.
- User complaints like "VELAR keeps bugging me about X."
- Notification volume exceeding ~3/day on average.

**Phase to address:**
Proactive engine phase. Must be implemented with tuning controls, not added as an afterthought to a notification firehose.

---

### Pitfall 3: LLM Hallucinations Presented as Personal Facts

**What goes wrong:**
Claude is asked "What did I eat last Tuesday?" When memory retrieval returns nothing, Claude confabulates a plausible-sounding answer ("You had pasta, based on your usual Tuesday pattern") rather than returning an honest "I don't have a record of that." The user then makes a decision (skipping pasta today) based on false data. Over time, trust collapses.

**Why it happens:**
The system prompt doesn't enforce strict grounding rules. Claude's default behavior is to be helpful — which in the absence of data means generating plausible-sounding completions. Developers assume the model will naturally say "I don't know" when it doesn't.

**How to avoid:**
- System prompt must explicitly instruct: "Only assert personal facts that appear verbatim in the retrieved memory context. If you cannot find a fact in context, say 'I don't have a record of that' — never infer or guess about the user's personal history."
- Implement a retrieval-required mode for personal-fact queries: if semantic search returns confidence < threshold, return a structured "no data" response before sending to Claude.
- Separate factual retrieval calls (deterministic) from reasoning calls (generative). Claude should reason about retrieved facts, not invent them.
- Log every factual claim Claude makes; periodically audit against actual memory store.

**Warning signs:**
- Claude provides specific dates/amounts/names that can't be found in the memory store.
- User says "I never told you that."
- During testing, queries about unlogged events return confident wrong answers.

**Phase to address:**
Memory system phase AND Claude integration phase. Must be validated before any personal-fact features ship.

---

### Pitfall 4: Voice Recognition Failing on Turkish

**What goes wrong:**
Whisper (and most STT systems) handle Turkish significantly worse than English — especially mixed Turkish-English sentences ("VELAR, bugün meeting'e gitmeli miyim?"). The app ships with acceptable English accuracy but poor Turkish accuracy. Users switch to typing, eroding the voice-first identity.

**Why it happens:**
Turkish is an agglutinative language with very long words and different phonology. Most STT benchmarks are English-heavy. Developers test only with English speech during development.

**How to avoid:**
- Use Whisper large-v3 (not base/small) for Turkish — the quality gap between model sizes is larger for Turkish than English.
- Test Turkish STT accuracy as a first-class metric from day one. Define an acceptable WER (Word Error Rate) threshold — suggested: <15% WER on common assistant commands in Turkish.
- Handle code-switching explicitly: sentences that mix Turkish and English mid-sentence (very common in urban Turkish speakers). Test with actual code-switched sentences.
- If Whisper Turkish accuracy is insufficient, evaluate Whisper with Turkish-specific fine-tuned models or Azure Cognitive Services Turkish endpoint as fallback.
- Build a correction flow: user can tap to see what VELAR heard and correct it. This also provides training signal.

**Warning signs:**
- Turkish test sentences returning wrong transcriptions.
- Whisper replacing Turkish words with phonetically similar English words.
- Agglutinated verb forms being split incorrectly.

**Phase to address:**
Voice/STT foundation phase. Fail early here — do not defer Turkish STT validation.

---

### Pitfall 5: Cross-Device State Becoming Out of Sync

**What goes wrong:**
User starts a task on Mac, gets a push on iPhone, then checks their Watch. Each device has a slightly different view of conversation state, notification status, and memory. The user says something on Watch, it doesn't appear in the Mac session. Or VELAR sends a notification to iPhone about something the user already handled on Mac 2 minutes ago.

**Why it happens:**
Cross-device sync is treated as a data sync problem (Firestore real-time updates) when it's actually a session state problem. Different devices have different sessions, and reconciling which device is "primary" for a given interaction is not modeled.

**How to avoid:**
- Define a canonical session model: a VELAR interaction spans devices, not runs on each device independently. Each session has a UUID; devices join sessions, they don't own them.
- Use Firestore real-time listeners (not polling) for notification acknowledgment propagation: once user acknowledges a notification on any device, mark it acknowledged for all devices immediately.
- Implement an "active device" concept: the device the user last interacted with is active for the current session. Proactive notifications route to the active device, with fallback to iPhone.
- For Watch: Watch is a receive/acknowledge device, not a full session device. Attempting to run a full conversation on Watch is a UX and technical mistake — it should surface the most recent briefing and allow quick yes/no/snooze responses only.
- Test the "handoff" scenario explicitly: Mac → iPhone → Watch and back, with mid-conversation state preserved.

**Warning signs:**
- Same notification appearing on all 3 devices simultaneously.
- Watch showing yesterday's briefing because sync listener disconnected.
- User answers a question on iPhone; Mac session doesn't know about it.

**Phase to address:**
Cross-device sync phase — must define the session model before building any device-specific features.

---

### Pitfall 6: API Cost Explosion from Uncontrolled LLM Calls

**What goes wrong:**
Passive learning, proactive briefings, and memory extraction all trigger Claude API calls. Without rate limiting and cost monitoring, a single day of active use generates dozens of expensive calls. The project becomes financially unviable before it's proven useful.

**Why it happens:**
During development, costs are invisible (small data, infrequent testing). The architecture is designed for capability, not for cost efficiency. "Run Claude on every conversation" feels natural but doesn't account for the compounding of memory extraction + context injection + reasoning calls per turn.

**How to avoid:**
- Count Claude API calls per user per day from day one. Set a daily budget cap (e.g., $0.50/user/day) and enforce it with circuit breakers.
- Use Claude Haiku for lightweight tasks (memory extraction, fact classification, notification scoring). Reserve Claude Sonnet/Opus for the primary conversation and morning briefing synthesis.
- Cache LLM outputs where the input is identical or nearly identical: morning briefing content doesn't need regeneration if the underlying data hasn't changed since last run.
- Batch memory extraction: don't extract facts after every single message. Batch at end of conversation session (when user goes idle for 5+ minutes).
- Implement a "cost telemetry" dashboard from day one — track tokens_in/tokens_out per API call category.

**Warning signs:**
- Anthropic billing spiking unexpectedly.
- Memory extraction running synchronously on every user message.
- No per-call cost logging in the backend.
- Daily Claude calls per user exceeding 20-30 without intentional design.

**Phase to address:**
Backend/Claude integration phase. Cost architecture must be a first-class design constraint, not a retrofit.

---

### Pitfall 7: Privacy Breach from Deeply Personal Data Stored Insecurely

**What goes wrong:**
VELAR stores health patterns, relationship details, dietary habits, location history, and personal conversations in Firebase/Supabase. If Firebase Security Rules are misconfigured (a very common mistake), data is readable by any authenticated user or, worse, publicly accessible. With this level of personal data, a breach is catastrophic.

**Why it happens:**
Developers working on personal apps (single user) set overly permissive rules ("allow read, write: if request.auth != null") which effectively grants any logged-in user access to all data. The developer is the only user, so it never triggers during development.

**How to avoid:**
- Firebase Security Rules must scope every read/write to `request.auth.uid == resource.data.userId`. Never use global `if request.auth != null` for personal data collections.
- Run Firebase Emulator with security rules enabled from day one — test rules, don't just deploy them.
- Encrypt sensitive memory entries at rest at the application layer (not just in transit). Firebase encrypts at rest by default, but application-level encryption means even a database breach doesn't expose plaintext personal data.
- For Supabase: use Row Level Security (RLS) policies, not just API key restrictions. Ensure every table has RLS enabled.
- No personal data in Firebase Realtime Database — use Firestore with explicit collection-level rules. RTDB rules are easier to misconfigure.
- API keys for Claude, ElevenLabs must never be embedded in Flutter app binary (easily extracted). Route all API calls through the Python backend.

**Warning signs:**
- Firebase rules written as `allow read, write: if true` or `if request.auth != null` without uid scoping.
- Claude API key or ElevenLabs API key present in Flutter codebase.
- No application-layer encryption for sensitive memory collections.
- Firebase security rules never tested against a non-owner test account.

**Phase to address:**
Foundation/backend phase. Security rules must be written and tested before any personal data is stored.

---

### Pitfall 8: Apple Watch as an Afterthought, Not a Constrained Platform

**What goes wrong:**
The Apple Watch app is designed by mentally "shrinking" the iPhone app. It tries to show conversation history, long text responses, and complex UI. The Watch app crashes on older Series or drains battery, and the UX is fundamentally wrong for glance-based interaction. Users stop using the Watch app.

**Why it happens:**
Watch development is treated as an extension of the iPhone app rather than a wholly different interaction paradigm. The Watch has: tiny screen, no keyboard, limited compute, restricted background execution, and users who look at it for 2-3 seconds per interaction.

**How to avoid:**
- Design Watch UX from scratch, not by shrinking iPhone screens. Watch interactions must complete in under 3 seconds of visual attention.
- Watch app scope: exactly 3 use cases — (1) receive morning briefing summary (headline only, tap to expand 2 sentences), (2) quick voice command via Siri-style dictation, (3) acknowledge/snooze a proactive notification.
- No streaming text on Watch — show final responses only, under 50 words.
- Use WatchKit Complications for ambient data display (next calendar event, current weather), not the app itself.
- SwiftUI for watchOS is the correct approach; avoid UIKit on Watch.
- Test on real hardware, not just simulator. Watch simulator does not accurately represent performance.

**Warning signs:**
- Watch app attempting to show full conversation history.
- Watch app requiring more than one tap to complete a common action.
- No battery impact testing done on Watch hardware.
- Watch app design mocks showing more than 3 interactive elements per screen.

**Phase to address:**
Apple Watch phase — must be explicitly scoped as a constrained satellite device, not a mini-iPhone.

---

### Pitfall 9: Proactive System Requires Perfect Context — But Context Is Always Imperfect

**What goes wrong:**
The morning briefing is designed to synthesize "everything relevant" about the user's day. In practice: calendar integration is missing some events (iCloud only, no work Google Calendar), location data isn't available yet, health data has gaps because the user didn't wear the Watch overnight. The briefing fires with partial data and sounds incoherent or makes wrong suggestions ("You have a free morning" when there's an unsynced work meeting).

**Why it happens:**
The proactive system is designed for the happy path (all integrations connected, all data available). Edge cases — missing data, stale data, failed API calls — are not modeled in the briefing logic.

**How to avoid:**
- Build the proactive engine with explicit data confidence levels: each data source reports "available/stale/unavailable."
- Briefing content is conditional: if calendar confidence is LOW, say "I couldn't access your full schedule" rather than assuming a free day.
- Define a minimum viable briefing: what's the useful output when only 2 out of 5 data sources are available? The system must degrade gracefully, not fail silently.
- Data source health dashboard in the backend: detect stale integrations before they corrupt briefing quality.
- Never present uncertain information as certain in the briefing. "It looks like you might have a free morning, though I wasn't able to check all your calendars" is better than "You have a free morning."

**Warning signs:**
- Morning briefing logic has no null-checks or fallback paths for missing data.
- Integration failure (e.g., HealthKit query timeout) causes entire briefing to fail.
- Briefing text doesn't qualify uncertainty ("You have X" rather than "Based on your calendar, you have X").

**Phase to address:**
Proactive engine phase AND integration phase. Data confidence handling must be designed before integrations are added.

---

### Pitfall 10: Flutter-to-Python Backend Communication Without Retry/Offline Handling

**What goes wrong:**
Flutter app sends a voice command. The Python backend is slow (LLM call takes 3-8 seconds), times out, or the network drops. The app shows a spinner indefinitely, or throws an unhandled exception that crashes the session. User loses confidence in VELAR's reliability after 2-3 such incidents.

**Why it happens:**
The happy-path API call is the only path tested. Timeout handling, retry logic, and offline states are treated as edge cases to "handle later."

**How to avoid:**
- Define API call timeout budgets: voice command → backend must respond within 10 seconds or return a "still thinking" intermediate response.
- Implement optimistic UI: show "VELAR is thinking..." immediately upon command submission, with a cancel option after 5 seconds.
- Retry with exponential backoff for transient network failures — but not for LLM timeouts (retrying an expensive LLM call when the first one is still running is wasteful).
- Distinguish network failure (retry) from LLM failure (show error, allow retry by user) from logic failure (log and fail gracefully).
- Backend must implement request deduplication: if the Flutter app retries due to timeout, backend doesn't run the LLM call twice.

**Warning signs:**
- No timeout set on Flutter HTTP/Dio client.
- No loading state visible to the user during API calls.
- Backend API has no idempotency keys or request deduplication.
- Testing only on fast local network, never on throttled or offline conditions.

**Phase to address:**
Backend integration phase. Resilience patterns must be built before voice interaction goes end-to-end.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Flat key-value memory store ("user_facts" JSON blob) | Fast to build, easy to update | Retrieval by semantic search impossible; entire blob must be loaded per query; conflicts undetectable | Never — start with structured collections from day one |
| Hardcode the system prompt in Python | No config overhead | A/B testing impossible; rollback requires deployment; persona tuning needs code changes | MVP only — externalize to config/DB by Phase 2 |
| Store raw conversation transcripts only, no extracted facts | No extraction pipeline needed | Every query requires LLM to re-parse full transcript history; cost and latency explode | Never — extract facts at conversation end, always |
| Single Claude API key for all operations | No IAM complexity | No per-feature cost visibility; one runaway call can block all other features | MVP only — move to per-feature rate limits when costs become relevant |
| Firebase Emulator skipped, test against production | Faster iteration | Security rules never validated; data corrupted in prod by bad test writes | Never — emulator must be standard dev practice from day one |
| Skip Turkish TTS testing ("we'll fix it later") | Faster MVP | Turkish voice output may sound wrong or mis-stress words; discovered at demo time | Never — test bilingual from day one |
| Poll for new notifications instead of using Firestore listeners | Simpler implementation | Battery drain on mobile; notification delay; scales poorly | Never for mobile — use real-time listeners |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Claude API (tool use) | Giving Claude too many tools at once (>10), causing confused tool selection | Give Claude only the tools relevant to the current task category; use routing layer to select tool subset |
| Claude API (streaming) | Not handling streaming responses in Flutter — showing nothing until response is complete | Implement SSE/WebSocket streaming from backend to Flutter; show partial responses as they arrive |
| Whisper STT | Running Whisper large-v3 locally on iPhone — too slow (5-15s for 10s audio) | Run Whisper on Python backend; send audio file via upload, receive transcript |
| HealthKit | Requesting all HealthKit permissions upfront — iOS rejects broad requests; users deny everything | Request HealthKit permissions on-demand, contextually, one category at a time |
| ElevenLabs TTS | Generating new TTS audio for every response, including cached/repeated content | Cache TTS audio by content hash; only generate new audio for novel text |
| Firebase Firestore | Using subcollections without planning security rules for each level | Design security rule hierarchy before collection structure — rules follow the data tree |
| Push Notifications (APNs) | Not handling APNs token refresh — token expires, push delivery silently fails | Implement token refresh listener in Flutter, update backend on every app foreground |
| Apple Watch connectivity | Using WatchConnectivity for real-time data instead of Firestore | WatchConnectivity is unreliable for real-time sync; use Firestore listener on Watch side directly |
| Turkish TTS (ElevenLabs) | Using an English-trained voice for Turkish text | ElevenLabs has Turkish-language voices; select a Turkish-capable voice model, not just any multilingual one |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading entire memory store into Claude context | Response times >10s; Claude API costs spike; token limit errors | Implement vector-based semantic retrieval; inject only top-K relevant facts | Beyond ~200 stored facts (week 2-3 of use) |
| Synchronous memory extraction on every message | Voice command response blocked by extraction LLM call | Batch extraction at session end (idle timeout); extraction runs async, never on request path | Immediately — even at MVP scale, this doubles latency |
| Firebase Firestore unbounded queries | iOS app slow to load; Firestore read costs spike | Always paginate; always add .limit() to queries; index compound queries | After ~500 stored memory items |
| ElevenLabs TTS without caching | Identical repeated phrases (greetings, "I don't know") generate new API calls | Cache TTS audio blobs in Firebase Storage keyed by text hash | After ~50 daily interactions |
| Proactive briefing regenerated on every app open | Unnecessary LLM calls when data hasn't changed | Cache last briefing with a freshness timestamp; only regenerate when source data changes | After first week of use |
| Running Whisper locally on Mac for transcription | High CPU/memory on Mac; fan spinning | Run on backend; Mac client sends audio, receives transcript | On any low-spec Mac immediately |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Claude/ElevenLabs API keys in Flutter app binary | Keys extractable by decompiling APK/IPA; attacker runs LLM calls on your bill | All LLM/TTS API calls route through Python backend only; Flutter talks to your backend, never to Anthropic/ElevenLabs directly |
| Firebase Security Rules granting access to all authenticated users | Any account (including attacker's) reads all personal data | Rules must gate every document access on `request.auth.uid == resource.data.userId` |
| Personal memory stored in plaintext | Database breach exposes sensitive health, relationship, and behavioral data | Application-layer AES-256 encryption for sensitive memory fields before write; decrypt only on authenticated read |
| No rate limiting on backend API | Attacker (or runaway client bug) triggers thousands of Claude API calls | Backend must enforce per-user rate limits (e.g., max 30 LLM calls per hour per user) |
| Conversation transcripts not treated as PII | Transcripts stored in logs, analytics, and debug output | Conversation transcripts are PII; mask/exclude from all logging systems; never include in error reports |
| Wake word detection sending audio to cloud continuously | Passive audio streaming to cloud violates privacy and App Store guidelines | Wake word detection must run fully on-device (Porcupine or similar); only post-wake audio is transmitted |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Voice response that takes 8-12 seconds with no feedback | User thinks app crashed; says command again causing duplicate | Show visual "thinking" indicator within 300ms of command end; stream partial text response while TTS is being generated |
| Morning briefing that's too long (>90 seconds) | User skips it; associated with wasted time | Morning briefing must be configurable length; default to 60 seconds; offer a "headlines only" mode |
| VELAR responding in English when user spoke Turkish | User feels the system isn't designed for them | Detect input language; respond in same language by default; allow per-session language lock |
| Proactive suggestion phrased as certainty ("You should go to X") | User resists — nobody likes being told what to do | Frame suggestions as options with reasoning ("Based on your usual preferences, you might enjoy X — it matches your diet and it's nearby") |
| Requiring manual data entry to build memory | User gives up before VELAR becomes useful | Memory must build passively from conversations; explicit entry is for corrections only, not the primary input mechanism |
| No way to see or delete what VELAR knows | User feels surveilled; App Store may reject for privacy | Provide a "What VELAR knows about me" view; allow per-fact deletion and bulk memory clear |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Voice command flow:** Often missing acoustic end-of-speech detection — verify that the STT correctly detects when the user has stopped speaking (not just a fixed-duration recording).
- [ ] **Morning briefing:** Often missing data source failure handling — verify it degrades gracefully when calendar/health/weather API is unavailable.
- [ ] **Memory system:** Often missing fact contradiction resolution — verify that updating a fact (e.g., new dietary preference) supersedes rather than duplicates the old one.
- [ ] **Push notifications:** Often missing silent push handling for background data refresh — verify background fetch works on a locked iPhone without user interaction.
- [ ] **Apple Watch app:** Often missing real-device performance testing — verify response times and battery impact on actual Watch hardware, not simulator.
- [ ] **Turkish language:** Often missing code-switching handling — verify that mixed Turkish-English sentences ("Bu hafta gym'e gittim mi?") transcribe correctly.
- [ ] **Cross-device sync:** Often missing conflict resolution — verify what happens when two devices send commands within 1 second of each other.
- [ ] **Security rules:** Often missing test against non-owner account — verify that a second test Firebase account cannot access first account's data.
- [ ] **API cost controls:** Often missing hard budget cap — verify that a runaway loop cannot generate >$5 of Claude API calls in one hour.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Memory store becomes corrupted with hallucinated facts | HIGH | Add a "VELAR learned this" confidence field to each fact; provide UI to review and delete low-confidence facts; rebuild memory from conversation history (re-extract) |
| Firebase Security Rules misconfiguration discovered | HIGH | Immediate rules lockdown; audit Firestore access logs for unauthorized reads; notify user; rotate Firebase credentials |
| API cost explosion (unexpected bill) | MEDIUM | Enable budget alerts in Anthropic console; implement immediate circuit breaker (disable LLM features past threshold); audit which call category caused spike |
| Turkish STT accuracy unacceptable | MEDIUM | Swap Whisper model size (base → large-v3); evaluate Azure Cognitive Services Turkish STT as drop-in replacement; add correction UI as immediate mitigation |
| Notification permission revoked by user | MEDIUM | Detect permission state on every app foreground; show non-intrusive in-app prompt explaining value; never force-ask more than once per 30 days |
| Apple Watch app rejected by App Review | LOW | Watch apps are reviewed; common rejection: excessive battery drain, misleading claims about health data. Mitigation: test battery impact pre-submission, review HealthKit guidelines |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Unbounded memory growth | Memory system phase | Load test with 1000+ facts; measure retrieval latency and token count |
| Notification noise | Proactive engine phase | Measure notification dismissal rate in 1-week dog-food period |
| LLM hallucinating personal facts | Memory + Claude integration phase | Test queries about unlogged events; verify "I don't have a record of that" response |
| Turkish STT failure | Voice/STT foundation phase | Define WER threshold (<15%); test 50 Turkish commands before advancing |
| Cross-device state sync | Cross-device/sync phase | Run handoff scenario tests (Mac→iPhone→Watch) before adding new platforms |
| API cost explosion | Backend architecture phase | Cost dashboard live before any proactive LLM features ship |
| Firebase security misconfiguration | Backend foundation phase | Run security rules tests against non-owner test account before any real data stored |
| Apple Watch as shrunken iPhone | Apple Watch phase | Design review: each Watch screen must pass "3-second glance" test |
| Proactive system with imperfect context | Proactive engine phase | Test all briefing logic paths with each data source set to "unavailable" |
| Flutter-backend resilience | Backend integration phase | Test on throttled network (Chrome DevTools equivalent for mobile); simulate backend timeout |

---

## Sources

- Anthropic Claude API documentation (tool use, streaming, rate limits) — training knowledge, MEDIUM confidence
- Apple Developer documentation (WatchKit, HealthKit permission patterns, APNs) — training knowledge, MEDIUM confidence
- Firebase Security Rules documentation and common misconfiguration patterns — training knowledge, HIGH confidence (this is a well-documented, frequently-cited pitfall)
- Whisper model performance on low-resource languages including Turkish — training knowledge, MEDIUM confidence (recommend current verification before Turkish STT phase)
- ElevenLabs multilingual TTS capabilities — training knowledge, LOW confidence on current Turkish voice availability (verify at integration phase)
- General LLM memory architecture patterns (RAG, vector retrieval, episodic vs. semantic memory) — training knowledge, MEDIUM confidence
- Apple App Store guidelines for voice recording, HealthKit, and background execution — training knowledge, MEDIUM confidence (guidelines change; verify at submission phase)
- Push notification UX research (notification fatigue, dismissal rates) — training knowledge, MEDIUM confidence

---
*Pitfalls research for: Proactive personal AI assistant (VELAR)*
*Researched: 2026-03-01*
