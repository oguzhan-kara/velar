---
phase: 04-mac-daemon
plan: "01"
subsystem: daemon
tags: [rumps, openwakeword, sounddevice, macos, menu-bar, wake-word, onnxruntime]

# Dependency graph
requires:
  - phase: 04-mac-daemon
    provides: Context and research for daemon architecture, threading patterns, openwakeword ARM64 pitfalls
provides:
  - velar-daemon/ directory with daemon.py, wakeword.py, config.py, requirements.txt
  - VelarDaemon rumps.App subclass with menu bar icon states and threading orchestration
  - WakeWordListener with openwakeword hey_jarvis onnx inference and sounddevice loop
  - DaemonConfig dataclass loading from ~/.velar/daemon.json with env var override
affects:
  - 04-02 (audio capture and backend POST wires into daemon._on_wake placeholder)
  - 04-03 (launchd plist and context tools built on top of daemon lifecycle)

# Tech tracking
tech-stack:
  added:
    - rumps==0.4.0 (macOS menu bar Python library)
    - openwakeword==0.6.0 (hey_jarvis pretrained wake word model)
    - sounddevice==0.5.5 (cross-platform audio I/O)
    - silero-vad==6.2.1 (VAD, used in Phase 04-02)
    - numpy>=1.26 (audio array processing)
    - pydub>=0.25 (audio format conversion)
    - requests>=2.31 (backend HTTP communication)
  patterns:
    - Thread separation: rumps main loop on main thread, audio stream on daemon background thread
    - audio started only from application_will_finish_launching_ (never __init__ — deadlock prevention)
    - atomic bool toggle for paused state (CPython GIL makes bool assignment thread-safe)
    - model.reset() before on_wake callback to prevent same-frame re-trigger
    - VELAR_BACKEND_URL env var overrides config file backend_url (dev vs production)
    - inference_framework='onnx' for cross-platform ARM64 macOS compatibility

key-files:
  created:
    - velar-daemon/daemon.py
    - velar-daemon/wakeword.py
    - velar-daemon/config.py
    - velar-daemon/requirements.txt
    - velar-daemon/__init__.py
  modified: []

key-decisions:
  - "inference_framework='onnx' explicitly set in Model() — tflite_runtime unavailable on macOS ARM64; onnxruntime handles .onnx models"
  - "audio stream started only from application_will_finish_launching_, never __init__ — rumps deadlock prevention per research pitfall 2"
  - "_on_wake 2s placeholder (time.sleep) deferred to Phase 04-02 which wires real audio capture + backend POST"
  - "paused flag uses atomic bool assignment (no lock needed in CPython) — toggle from main thread, read from audio thread"
  - "daemon.json loads from ~/.velar/ with DEFAULTS dict fallback — config dir created at daemon install time"

patterns-established:
  - "Thread separation pattern: rumps App on main thread, blocking audio loop on daemon=True background thread"
  - "Icon state constants as module-level strings (ICON_IDLE, ICON_LISTENING, ICON_PROCESSING, ICON_PAUSED, ICON_ERROR)"
  - "SIGTERM wired in __init__ via signal.signal() — graceful shutdown sets listener.paused then rumps.quit_application()"

requirements-completed: [VOICE-01, DEV-01]

# Metrics
duration: 5min
completed: 2026-03-02
---

# Phase 04 Plan 01: Mac Daemon Shell Summary

**rumps menu bar daemon with openwakeword hey_jarvis onnx detection on background thread, DaemonConfig from ~/.velar/daemon.json, and SIGTERM graceful shutdown**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-02T16:54:57Z
- **Completed:** 2026-03-02T16:59:55Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Created `velar-daemon/` module with all 5 required files
- WakeWordListener: openwakeword hey_jarvis model with onnxruntime inference, 16kHz/1280-sample sounddevice loop, pause toggle
- VelarDaemon: rumps.App with ICON_IDLE/LISTENING/PROCESSING/PAUSED/ERROR states, application_will_finish_launching_ thread start, SIGTERM handler
- DaemonConfig: dataclass loaded from ~/.velar/daemon.json with VELAR_BACKEND_URL env override
- Auto-fixed ARM64 compatibility: explicit `inference_framework='onnx'` to avoid tflite_runtime dependency

## Task Commits

Each task was committed atomically:

1. **Task 1: Create velar-daemon scaffold with config loader** - `701f674` (feat)
2. **Task 2: Create WakeWordListener** - `a6ba610` (feat)
3. **Task 3: Create VelarDaemon rumps App** - `898c5b8` (feat)

Auto-fix deviation commit:
- **[Rule 2] onnx inference_framework fix** - `8fc3f75` (fix)

**Plan metadata:** (pending — docs commit)

## Files Created/Modified

- `velar-daemon/config.py` - DaemonConfig dataclass + load_config() reading ~/.velar/daemon.json with env override
- `velar-daemon/wakeword.py` - WakeWordListener with openwakeword hey_jarvis onnx model, sounddevice 16kHz loop
- `velar-daemon/daemon.py` - VelarDaemon rumps.App with menu bar states, threading orchestration, SIGTERM handler
- `velar-daemon/requirements.txt` - 7 daemon dependencies with pinned/minimum versions
- `velar-daemon/__init__.py` - Empty package marker

## Decisions Made

- **onnxruntime over tflite:** `inference_framework='onnx'` explicitly set — tflite_runtime has no macOS ARM64 wheel; onnxruntime handles .onnx models natively. This was identified as pitfall 1 in 04-RESEARCH.md.
- **2s placeholder in _on_wake:** `time.sleep(2)` smoke-test hook instead of real audio capture — Phase 04-02 wires actual recording + backend POST into this method.
- **application_will_finish_launching_ thread start:** Audio thread never started in `__init__` — macOS NSApplication must be running before background threads touch AppKit objects.
- **~/.velar/ created at install time:** config.py's load_config() checks existence but doesn't create the directory — daemon install script (Phase 04-03) creates it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added explicit onnx inference_framework for ARM64 compatibility**
- **Found during:** Overall verification (after Task 3)
- **Issue:** `Model(wakeword_models=["hey jarvis"])` without `inference_framework='onnx'` defaults to tflite and raises `ValueError: Tried to import tflite runtime...` since tflite_runtime is unavailable on macOS ARM64 (and Windows). The 04-RESEARCH.md explicitly documents this as pitfall 1.
- **Fix:** Added `inference_framework="onnx"` parameter to Model() constructor call in wakeword.py
- **Files modified:** `velar-daemon/wakeword.py`
- **Verification:** `Model(wakeword_models=['hey jarvis'], inference_framework='onnx')` loads successfully; WakeWordListener import passes
- **Committed in:** `8fc3f75`

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical for ARM64 target platform)
**Impact on plan:** Essential fix — without this, daemon would crash immediately on macOS ARM64 (the target platform). No scope creep.

## Issues Encountered

- `rumps` cannot be installed on Windows (requires macOS AppKit) — daemon.py import test cannot be fully verified on Windows dev environment. AST-parsed for syntax validity; full launch test requires target macOS machine. This matches the plan's explicit note: "Full launch test requires macOS with mic access."
- openwakeword models not bundled in package — downloaded hey_jarvis_v0.1.onnx via `openwakeword.utils.download_models()` for local validation.

## User Setup Required

None - no external service configuration required. The `~/.velar/` directory is created during daemon install (Phase 04-03).

## Next Phase Readiness

- `velar-daemon/daemon.py` has `_on_wake()` placeholder ready for Phase 04-02 audio capture + backend POST wiring
- All icon state constants defined (ICON_IDLE, ICON_LISTENING, ICON_PROCESSING, ICON_PAUSED, ICON_ERROR)
- Menu bar Pause Wake Word toggle fully wired to listener.paused
- Config system ready for audio_device_index (sounddevice device selection)
- Blocker: daemon must be tested on macOS with mic permissions to confirm rumps + sounddevice integration works end-to-end

## Self-Check: PASSED

- FOUND: velar-daemon/config.py
- FOUND: velar-daemon/wakeword.py
- FOUND: velar-daemon/daemon.py
- FOUND: velar-daemon/requirements.txt
- FOUND: velar-daemon/__init__.py
- FOUND: .planning/phases/04-mac-daemon/04-01-SUMMARY.md
- FOUND commit: 701f674 (Task 1 - scaffold)
- FOUND commit: a6ba610 (Task 2 - WakeWordListener)
- FOUND commit: 898c5b8 (Task 3 - VelarDaemon)
- FOUND commit: 8fc3f75 (Auto-fix - onnx inference_framework)

---
*Phase: 04-mac-daemon*
*Completed: 2026-03-02*
