# Phase 2: Voice Pipeline - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Voice interaction pipeline for VELAR: speech-to-text (faster-whisper), Claude tool-use loop (no tools yet — just the conversation scaffold), text-to-speech (ElevenLabs primary, Edge TTS fallback), and bilingual language support (Turkish, English, code-switching). Users can speak or type to VELAR and receive a premium voice or text response. Wake word detection is Phase 4 (Mac Daemon) — this phase builds the pipeline that wake word will trigger.

</domain>

<decisions>
## Implementation Decisions

### Input Modes
- Both voice and text input supported from day one
- Voice input via faster-whisper STT (local, best Turkish accuracy per research)
- Text input via API endpoint — same Claude tool loop, just skips STT
- Input mode is transparent to the Claude conversation layer — it receives text either way

### Voice Character
- Male voice — VELAR is a male-persona assistant (Jarvis reference)
- Warm, confident, slightly formal but not stiff — think concierge, not robot
- ElevenLabs as primary TTS provider — select a premium multilingual voice that handles both Turkish and English naturally
- Edge TTS as fallback when ElevenLabs is unavailable or rate-limited
- Single consistent voice across languages (no voice switching between Turkish and English)

### Conversation Flow
- Request-response model in Phase 2 (not continuous conversation — that's the daemon's job in Phase 4)
- API endpoint receives audio blob or text → STT (if audio) → Claude → TTS → return audio + text
- No wake word in this phase — direct API invocation (wake word is Phase 4)
- Voice Activity Detection (VAD) on the STT side to trim silence and detect end-of-speech
- Streaming TTS response where possible to reduce perceived latency (start speaking before full response is generated)

### Response Style
- Concise by default — 1-3 sentences for simple questions
- Longer when the topic demands it, but always conversational, never lecture-style
- VELAR has personality: warm, slightly witty, anticipatory ("I noticed you...", "By the way...")
- Responses are optimized for listening — short sentences, natural pauses, no jargon dumps
- Text responses can be slightly longer/more detailed than spoken responses

### Language Behavior
- VELAR mirrors the user's language — speak Turkish, get Turkish back; speak English, get English back
- Code-switching handled gracefully: if the user mixes languages, VELAR responds in the dominant language of the sentence
- No explicit language toggle needed — automatic detection per utterance
- Turkish STT target: WER under 15% on common assistant commands (per roadmap success criteria)
- System prompt instructs Claude to be naturally bilingual, not translating but thinking in both languages

### Latency Targets
- Full voice round-trip (speak → hear response) under 4 seconds perceived latency (per roadmap)
- STT processing: target under 1 second for typical utterances
- Claude response: streaming, first token under 500ms
- TTS: streaming playback, first audio chunk before full text is ready

### Claude's Discretion
- Exact faster-whisper model size (tiny/base/small/medium) — balance accuracy vs speed
- VAD implementation details (silero-vad or webrtcvad)
- ElevenLabs voice ID selection from available multilingual voices
- Audio format and encoding choices (opus, wav, mp3)
- Exact API endpoint design for voice/text input
- Error handling for STT failures, TTS failures, Claude timeouts
- Conversation context window management (how many turns to keep)

</decisions>

<specifics>
## Specific Ideas

- User explicitly confirmed: "text will work right? voice or text to trigger VELAR" — both input modes from day one
- The Jarvis reference means VELAR should feel like talking to a capable, confident assistant — not a chatbot
- Morning Briefing demo (Phase 5) depends on TTS quality established here — voice must be premium enough to wake up to
- Turkish is the user's primary language — Turkish STT quality is non-negotiable

</specifics>

<deferred>
## Deferred Ideas

- Wake word detection ("Hey VELAR") — Phase 4 (Mac Daemon)
- Continuous listening / always-on microphone — Phase 4
- Tool use (calendar, weather, etc.) — Phases 4-5 (scaffold only here)
- Conversation memory / context persistence — Phase 3 (Memory System)

</deferred>

---

*Phase: 02-voice-pipeline*
*Context gathered: 2026-03-01*
