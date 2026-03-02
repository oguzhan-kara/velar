# Deferred Items — Phase 03

## Out-of-Scope Discoveries During Plan 03-01 Execution

### 1. Missing `anthropic` package in current venv

**Discovered during:** T4 full test suite run
**Issue:** `ModuleNotFoundError: No module named 'anthropic'` when importing `app.voice.conversation` and `app.voice.streaming`. This causes 4 tests in `test_auth.py` (which use the `client` fixture that imports `app.main`) to error at setup.
**Root cause:** `anthropic==0.84.0` is in requirements.txt but not installed in the current venv session.
**Action needed:** Run `pip install -r requirements.txt` to install all Phase 2 deps.
**Scope:** Pre-existing, not caused by Phase 3 changes.

### 2. Missing `soundfile` package in current venv

**Discovered during:** T4 full test suite run
**Issue:** `ModuleNotFoundError: No module named 'soundfile'` when importing `test_voice_e2e.py` and `test_voice_stt.py`.
**Root cause:** `soundfile>=0.12` is in requirements.txt but not installed in the current venv session.
**Action needed:** Run `pip install -r requirements.txt`.
**Scope:** Pre-existing, not caused by Phase 3 changes.
