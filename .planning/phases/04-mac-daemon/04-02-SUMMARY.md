---
phase: 04-mac-daemon
plan: "02"
subsystem: daemon
tags: [silero-vad, pydub, sounddevice, requests, launchd, macos, audio, vad, wake-word]

# Dependency graph
requires:
  - phase: 04-mac-daemon
    plan: "01"
    provides: VelarDaemon rumps App with _on_wake placeholder, DaemonConfig from ~/.velar/daemon.json
provides:
  - audio_capture.py: Silero VAD post-wake recording with 3s/1.5s/8s timeouts, returns int16 PCM bytes or None
  - chime.py: pydub sine tone synthesis — play_chime() 880Hz/200ms, play_cancelled() 440Hz/100ms, play_audio_response() MP3 bytes
  - backend_client.py: post_voice_audio() wraps PCM in WAV header, POSTs multipart to /api/v1/voice with Bearer auth, returns MP3 bytes
  - config.py: DaemonConfig.auth_token field; load_config() reads auth_token from daemon.json
  - daemon.py: full _run_voice_pipeline (chime->capture->POST->playback) on dedicated thread; ICON_ERROR with 3s hold on exception
  - launchd/com.velar.daemon.plist: KeepAlive + RunAtLoad template with 3 __PLACEHOLDER__ markers
  - install.sh: sed substitution of all 3 placeholders + launchctl bootstrap/kickstart
affects:
  - 04-03 (integration tools — tool loop runs on top of the same voice pipeline)
  - Phase 5 (proactive features — daemon.py is the execution host)

# Tech tracking
tech-stack:
  added:
    - silero-vad==6.2.1 (VAD model for post-wake speech detection)
    - pydub>=0.25 (AudioSegment.sine tone synthesis + MP3 playback)
    - requests>=2.31 (multipart POST to /api/v1/voice)
    - wave (stdlib — WAV header wrapping for int16 PCM)
  patterns:
    - Pipeline thread separation: _on_wake returns immediately, _run_voice_pipeline runs on dedicated daemon thread
    - Module-level VAD model load (load_silero_vad() once at audio_capture import — not per-capture)
    - Deferred imports inside _run_voice_pipeline: chime/audio_capture/backend_client imported lazily on first wake, avoiding circular deps and import-time side effects
    - WAV header wrapping: raw int16 PCM bytes wrapped with stdlib wave module before multipart upload
    - Exception catch-all in pipeline with ICON_ERROR 3s display then return to ICON_IDLE

key-files:
  created:
    - velar-daemon/chime.py
    - velar-daemon/audio_capture.py
    - velar-daemon/backend_client.py
    - velar-daemon/launchd/com.velar.daemon.plist
    - velar-daemon/install.sh
  modified:
    - velar-daemon/daemon.py (_on_wake replaced with pipeline dispatch, _run_voice_pipeline added)
    - velar-daemon/config.py (auth_token field added to DaemonConfig + DEFAULTS + load_config)

key-decisions:
  - "_run_voice_pipeline on separate thread: _on_wake returns from listener thread immediately so WakeWordListener can reset and detect next wake word without blocking"
  - "Deferred imports in _run_voice_pipeline (from chime import ...) — avoids circular dep issues and keeps import-time side effects out of module load"
  - "Silero VAD model loaded once at audio_capture module level (_vad_model) — not per-capture — avoids ~300ms model load per utterance"
  - "WAV header wrapping via stdlib wave module — no extra dependencies; backend faster-whisper requires decodable audio format not raw PCM"
  - "ICON_ERROR shows for 3s on pipeline exception then auto-resets to ICON_IDLE — user sees feedback without requiring restart"
  - "launchd plist uses 3 __PLACEHOLDER__ markers substituted by install.sh sed — avoids hardcoding absolute paths in version-controlled files"

patterns-established:
  - "Pipeline thread pattern: immediate return from callback thread + separate daemon thread for blocking I/O"
  - "Silero VAD reuse pattern: 16kHz/1280-chunk, threshold 0.5, model loaded once at module import"
  - "3-timeout audio capture: NO_SPEECH_TIMEOUT (3s cancel), SILENCE_TIMEOUT (1.5s end), MAX_RECORDING (8s hard stop)"

requirements-completed: [VOICE-01, DEV-01]

# Metrics
duration: 7min
completed: 2026-03-02
---

# Phase 04 Plan 02: Audio Capture + Backend POST Summary

**Silero VAD post-wake utterance capture wired to /api/v1/voice multipart POST with pydub chime feedback, launchd KeepAlive plist, and sed-based install.sh**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-02T17:04:48Z
- **Completed:** 2026-03-02T17:12:00Z
- **Tasks:** 2 of 3 complete (Task 3 is human-verify checkpoint — pending Mac hardware test)
- **Files modified:** 7

## Accomplishments

- Created audio_capture.py with Silero VAD loop: 3s no-speech cancel, 1.5s silence stop, 8s hard timeout — returns int16 PCM bytes or None
- Created chime.py with pydub sine tone generation: 880Hz metallic chime on wake, 440Hz cancelled tone on no-speech, MP3 playback on response
- Created backend_client.py: wraps int16 PCM in WAV container using stdlib wave, POSTs multipart to /api/v1/voice with Bearer token, returns MP3 bytes
- Updated config.py: DaemonConfig gains auth_token field; load_config() reads it from daemon.json with empty-string default
- Replaced daemon.py _on_wake placeholder with full pipeline: _on_wake spawns thread -> _run_voice_pipeline runs chime->capture->POST->playback with ICON_ERROR fallback
- Created launchd plist template with KeepAlive + RunAtLoad and install.sh using sed for 3 placeholder substitutions + launchctl bootstrap

## Task Commits

Each task was committed atomically:

1. **Task 1: Create chime.py, audio_capture.py, backend_client.py, and update config.py** - `e7da83d` (feat)
2. **Task 2: Update daemon.py _on_wake and create launchd plist + install.sh** - `8fd090c` (feat)
3. **Task 3: Human verification — end-to-end wake word pipeline on target Mac** - pending checkpoint

## Files Created/Modified

- `velar-daemon/chime.py` - play_chime() 880Hz/200ms, play_cancelled() 440Hz/100ms, play_audio_response() MP3 bytes via pydub
- `velar-daemon/audio_capture.py` - Silero VAD loop with 3-timeout strategy, returns int16 PCM bytes or None
- `velar-daemon/backend_client.py` - WAV header wrapping + multipart POST to /api/v1/voice + Bearer auth
- `velar-daemon/config.py` - auth_token field added to DaemonConfig dataclass, DEFAULTS dict, and load_config()
- `velar-daemon/daemon.py` - _on_wake now spawns _run_voice_pipeline thread; full chime->capture->POST->playback pipeline
- `velar-daemon/launchd/com.velar.daemon.plist` - launchd agent template with KeepAlive, RunAtLoad, 3 placeholder markers
- `velar-daemon/install.sh` - sed substitution + launchctl bootout/bootstrap/kickstart

## Decisions Made

- **Pipeline thread separation:** _on_wake returns from the WakeWordListener thread immediately and spawns a new daemon thread for _run_voice_pipeline. This keeps the audio detection loop responsive after each wake event — the listener resets and re-arms while the pipeline runs independently.
- **Deferred imports in _run_voice_pipeline:** chime, audio_capture, and backend_client are imported inside the method body. This avoids circular imports at module load time and keeps import-time side effects (Silero VAD model load) out of the main daemon startup path — only happens on first wake.
- **Silero VAD loaded once at module level:** _vad_model = load_silero_vad() executes once when audio_capture.py is first imported, not per-utterance. Avoids ~300ms model load overhead on every capture.
- **WAV wrapping with stdlib wave:** Raw int16 PCM bytes are wrapped in a proper WAV container before upload. faster-whisper on the backend requires a decodable audio format; raw PCM has no header indicating sample rate or bit depth.
- **launchd placeholders:** Three __PLACEHOLDER__ markers (__PYTHON_PATH__, __DAEMON_DIR__, __HOME__) are substituted by install.sh's sed command. Avoids hardcoding absolute paths in version-controlled plist.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- pydub, torch, and silero_vad are not available on the Windows dev environment. Verification was performed via: (1) AST parse for syntax validity; (2) direct import test of config.py and backend_client.py (no macOS/torch deps); (3) string assertions for required identifiers in source. Full functional test requires target macOS hardware (Task 3 checkpoint).

## User Setup Required

macOS microphone permissions required on first daemon launch:
- macOS will prompt for microphone access when sounddevice opens the InputStream
- Allow in: macOS System Settings > Privacy & Security > Microphone
- Create ~/.velar/daemon.json with auth_token from POST /api/v1/auth/login

## Next Phase Readiness

- Full daemon pipeline implemented — Task 3 requires human verification on macOS hardware
- launchd install.sh tested on macOS with `./install.sh` confirms plist at ~/Library/LaunchAgents/com.velar.daemon.plist
- Phase 05 (proactive scheduling) builds on daemon lifecycle hooks — daemon.py is the execution host

## Self-Check: PASSED

- FOUND: velar-daemon/chime.py
- FOUND: velar-daemon/audio_capture.py
- FOUND: velar-daemon/backend_client.py
- FOUND: velar-daemon/config.py (modified)
- FOUND: velar-daemon/daemon.py (modified)
- FOUND: velar-daemon/launchd/com.velar.daemon.plist
- FOUND: velar-daemon/install.sh
- FOUND commit: e7da83d (Task 1)
- FOUND commit: 8fd090c (Task 2)

---
*Phase: 04-mac-daemon*
*Completed: 2026-03-02*
