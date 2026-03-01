---
phase: 01-foundation
plan: 02
subsystem: auth
tags: [fastapi, supabase, jwt, python-jose, hs256, dependency-injection, rls, pytest, pytest-asyncio, httpx]

# Dependency graph
requires:
  - phase: 01-foundation-01
    provides: FastAPI skeleton, config.py settings singleton, auth/users schema stubs, Supabase migration with memory_facts RLS
provides:
  - get_current_user FastAPI dependency decoding Supabase HS256 JWT (app/dependencies.py)
  - POST /api/v1/auth/login endpoint calling Supabase Auth via asyncio.to_thread (app/auth/router.py + service.py)
  - GET /api/v1/users/me protected endpoint using Depends(get_current_user) (app/users/router.py)
  - get_user_profile service using user-scoped Supabase client with RLS applied (app/users/service.py)
  - Pytest test suite verifying 401 on no/invalid token, login success/failure, and RLS isolation (tests/)
affects: [02-voice-pipeline, 03-memory-engine, 04-wake-word, 05-proactive-intelligence, 06-cross-device-sync, 07-advice-engine]

# Tech tracking
tech-stack:
  added:
    - python-jose[cryptography]>=3.3 (already in requirements; now actively used for JWT decode)
    - pydantic[email]>=2.0 (added — required for EmailStr in auth/schemas.py)
    - pytest>=8.0 (test runner)
    - pytest-asyncio>=0.23 (asyncio test support, asyncio_mode=auto)
    - httpx>=0.27 (async test client via ASGITransport)
  patterns:
    - JWT validation via FastAPI Depends() — NOT middleware (returns structured JSON errors)
    - asyncio.to_thread() wraps all supabase-py sync client calls (auth and DB)
    - User-scoped Supabase client: create_client(anon_key) + set_session(user_jwt) ensures RLS applies
    - Service role key NEVER used in user-facing request handlers
    - pytest.mark.skipif(not os.getenv(...)) for live cloud tests — graceful skip without env vars

key-files:
  created:
    - velar-backend/app/dependencies.py
    - velar-backend/app/auth/service.py
    - velar-backend/app/users/service.py
    - velar-backend/tests/__init__.py
    - velar-backend/tests/conftest.py
    - velar-backend/tests/test_auth.py
    - velar-backend/tests/test_rls.py
  modified:
    - velar-backend/app/auth/router.py
    - velar-backend/app/users/router.py
    - velar-backend/requirements.txt
    - velar-backend/.env.example

key-decisions:
  - "JWT algorithm is HS256 — aligns with Supabase default for new projects; plan notes ES256/JWKS as upgrade path if project is configured with asymmetric keys"
  - "JWT validation uses python-jose with audience=authenticated — matches Supabase JWT audience claim"
  - "supabase-py sync client wrapped in asyncio.to_thread — async supabase-py client stability uncertain per research"
  - "User-scoped Supabase client (anon_key + set_session) used in users/service.py so RLS policies evaluate auth.uid() correctly"
  - "RLS test requires two pre-existing test accounts — deferred to environment setup, skips gracefully when absent"

patterns-established:
  - "Auth pattern: all protected routes use Depends(get_current_user) — never FastAPI middleware for auth"
  - "Supabase calls pattern: asyncio.to_thread(_sync_fn) wraps any supabase-py sync call"
  - "Test skip pattern: @pytest.mark.skipif(not os.getenv('VAR'), reason=...) for cloud-dependent tests"
  - "User-scoped DB access: create_client(anon_key).auth.set_session(user_jwt) — RLS applies automatically"

requirements-completed: [SYNC-02]

# Metrics
duration: 4min
completed: 2026-03-01
---

# Phase 1 Plan 02: Auth Foundation Summary

**Supabase JWT auth via FastAPI dependency injection (HS256, python-jose), login endpoint wrapping supabase-py in asyncio.to_thread, /users/me protected route with RLS-enforced user-scoped client, and pytest suite verifying 401s and gracefully skipping live cloud tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-01T20:39:07Z
- **Completed:** 2026-03-01T20:43:00Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- `get_current_user` FastAPI dependency decoding Supabase HS256 JWTs using python-jose, returning structured 401 JSON errors on failure
- POST /api/v1/auth/login using supabase-py wrapped in asyncio.to_thread, returns TokenResponse with access_token
- GET /api/v1/users/me protected endpoint that passes user JWT to a user-scoped Supabase client so RLS applies when fetching user_profiles
- Pytest suite: 4 passing tests (health no-auth, 401 no token, 401 invalid token, 401 wrong credentials) + 3 gracefully skipped live cloud tests
- RLS isolation test (test_rls.py) ready for execution when TEST_USER_EMAIL/TEST_USER2_EMAIL are configured — verifies User2 cannot read User1's memory_facts

## Task Commits

Each task was committed atomically:

1. **Task 1: JWT dependency, auth router (login), and users/me protected endpoint** - `e764133` (feat)
2. **Task 2: Pytest test suite for auth flows and RLS isolation verification** - `e21e5a5` (feat)

**Plan metadata:** (docs commit — created with this summary)

## Files Created/Modified
- `velar-backend/app/dependencies.py` - get_current_user dependency, CurrentUser TypedDict, HTTPBearer security
- `velar-backend/app/auth/service.py` - sign_in() calling supabase-py via asyncio.to_thread
- `velar-backend/app/auth/router.py` - POST /api/v1/auth/login endpoint, returns TokenResponse
- `velar-backend/app/users/service.py` - get_user_profile() using user-scoped client (RLS applies)
- `velar-backend/app/users/router.py` - GET /api/v1/users/me with Depends(get_current_user)
- `velar-backend/tests/__init__.py` - Empty package marker
- `velar-backend/tests/conftest.py` - Async ASGI test client fixture (httpx + ASGITransport)
- `velar-backend/tests/test_auth.py` - Auth flow tests (health, 401s, login valid/invalid, /users/me)
- `velar-backend/tests/test_rls.py` - RLS isolation test (User2 cannot read User1 memory_facts)
- `velar-backend/requirements.txt` - Added pydantic[email], pytest, pytest-asyncio, httpx
- `velar-backend/.env.example` - Added TEST_USER_EMAIL/PASSWORD vars for live auth/RLS tests

## Decisions Made
- JWT algorithm set to HS256 — matches Supabase default for new projects. If the Supabase project settings show ES256/JWKS, update `algorithms=["ES256"]` in dependencies.py and replace jwt_secret with the JWKS public key.
- python-jose decode uses `audience="authenticated"` — this matches the Supabase JWT `aud` claim for user tokens.
- supabase-py async client stability is uncertain (per plan research), so all calls use sync client wrapped in asyncio.to_thread.
- User-scoped Supabase client (anon_key + set_session) is the correct approach for user data queries — service_role_key bypasses RLS and must never be used in user-facing handlers.
- RLS test was scoped to integration (requires real cloud accounts) rather than mocking — a mock would not verify actual Supabase RLS policy enforcement.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added missing pydantic[email] dependency**
- **Found during:** Task 1 (import verification)
- **Issue:** app/auth/schemas.py uses EmailStr from pydantic.networks, which requires email-validator package. pydantic[email] was missing from requirements.txt, causing ImportError at import time.
- **Fix:** Added `pydantic[email]>=2.0` to requirements.txt and installed email-validator into the venv.
- **Files modified:** velar-backend/requirements.txt
- **Verification:** Import verification command succeeded after installing: `from app.auth.router import router as ar` resolved cleanly.
- **Committed in:** e764133 (Task 1 commit)

**2. [Rule 3 - Blocking] Created virtual environment and installed all dependencies**
- **Found during:** Task 1 (import verification)
- **Issue:** No .venv existed in the backend directory. Dependencies not installed globally. Required for verification and test execution.
- **Fix:** Created .venv with `py -m venv .venv` and installed requirements.txt. The venv is gitignored and is a developer setup step.
- **Files modified:** None (venv not committed)
- **Verification:** All imports resolved after venv creation.
- **Committed in:** e764133 (Task 1 commit, requirements.txt was also updated)

---

**Total deviations:** 2 auto-fixed (2 blocking issues — missing dependency, missing dev environment)
**Impact on plan:** Both required to execute import verification and tests. No scope creep.

## Issues Encountered
- `pydantic[email]` was missing from requirements.txt even though auth/schemas.py uses EmailStr — caught during Task 1 import verification. Fixed inline per Rule 3.
- No virtual environment existed at execution start — created during Task 1 verification to enable import checking and test execution.

## User Setup Required
**To run live auth and RLS tests, add to `velar-backend/.env`:**
```bash
TEST_USER_EMAIL=your-test-user@example.com
TEST_USER_PASSWORD=yourpassword
TEST_USER2_EMAIL=your-second-test-user@example.com
TEST_USER2_PASSWORD=yourpassword2
```
Both accounts must pre-exist in your Supabase Auth project.

Run tests:
```bash
cd velar-backend
.venv/Scripts/pytest tests/ -v
```

Without env vars: 4 tests pass, 3 skip gracefully. With env vars: all 7 run, including the RLS isolation test.

## Next Phase Readiness
- Auth foundation complete. All Phase 2+ routes should use `Depends(get_current_user)` to get `CurrentUser` dict.
- Pattern established: service_role_key never in user-facing handlers; user-scoped Supabase client enforces RLS.
- RLS isolation test is the Phase 1 security acceptance criterion — verify it passes with real accounts before advancing to Phase 2.
- JWT algorithm note: verify Supabase dashboard > Settings > Auth > JWT Settings shows HS256 before deploying. Update dependencies.py if ES256.

---
*Phase: 01-foundation*
*Completed: 2026-03-01*
