---
phase: 01-foundation
plan: 01
subsystem: infra
tags: [fastapi, pydantic-settings, sqlalchemy, asyncpg, docker, supabase, pgvector, python]

# Dependency graph
requires: []
provides:
  - FastAPI service skeleton with lifespan, CORS, and /health endpoint
  - pydantic-settings config with hard-fail on missing env vars
  - SQLAlchemy 2.0 async engine and session factory
  - Docker Compose dev environment with hot reload and healthcheck
  - Supabase migration defining all 4 personal data tables with pgvector and RLS
affects: [02-voice-pipeline, 03-memory-engine, 04-wake-word, 05-proactive-intelligence, 06-cross-device-sync, 07-advice-engine]

# Tech tracking
tech-stack:
  added:
    - fastapi>=0.115
    - uvicorn[standard]>=0.30
    - pydantic-settings>=2.0
    - supabase>=2.0
    - python-jose[cryptography]>=3.3
    - asyncpg>=0.29
    - sqlalchemy>=2.0
    - python:3.12-slim (Docker base)
    - pgvector (Supabase extension)
  patterns:
    - pydantic-settings BaseSettings with env_file — crashes at startup on missing secrets
    - SQLAlchemy async_sessionmaker + get_db async generator as FastAPI dependency
    - asynccontextmanager lifespan (not deprecated on_event)
    - (select auth.uid()) RLS caching syntax in all Supabase policies
    - EAV triple pattern with supersede versioning for memory_facts

key-files:
  created:
    - velar-backend/app/main.py
    - velar-backend/app/config.py
    - velar-backend/app/database.py
    - velar-backend/app/health/router.py
    - velar-backend/app/auth/schemas.py
    - velar-backend/app/users/schemas.py
    - velar-backend/Dockerfile
    - velar-backend/docker-compose.yml
    - velar-backend/.dockerignore
    - velar-backend/.env.example
    - velar-backend/requirements.txt
    - velar-backend/pyproject.toml
    - velar-backend/supabase/migrations/20260301000001_initial_schema.sql
    - velar-backend/supabase/seed.sql
  modified: []

key-decisions:
  - "Supabase runs as cloud project only — no local Supabase container in docker-compose (satisfies SYNC-02: cloud schema)"
  - "pydantic-settings intentionally crashes at startup if any of the 7 required env vars are missing"
  - "asyncpg lifespan DB check uses DSN string conversion (postgresql+asyncpg -> postgresql) for direct connectivity check"
  - "RLS policies use (select auth.uid()) caching syntax to avoid per-row function calls"
  - "memory_facts uses EAV triple pattern with valid_from/valid_until/superseded_by for full audit trail"

patterns-established:
  - "Config pattern: from app.config import settings — all modules import the singleton"
  - "DB dependency: FastAPI Depends(get_db) yields AsyncSession per request"
  - "Router pattern: each domain (health/auth/users) has router.py exporting APIRouter instance"
  - "Stub routers: auth and users modules have router.py with empty APIRouter ready for future routes"

requirements-completed: [SYNC-02]

# Metrics
duration: 3min
completed: 2026-03-01
---

# Phase 1 Plan 01: Foundation Summary

**FastAPI skeleton with pydantic-settings hard-fail config, SQLAlchemy async engine, Docker Compose hot-reload environment, and Supabase migration defining user_profiles/memory_facts/user_events/user_contacts tables with pgvector and RLS**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-01T20:32:30Z
- **Completed:** 2026-03-01T20:35:59Z
- **Tasks:** 3
- **Files modified:** 17

## Accomplishments
- FastAPI app with asynccontextmanager lifespan, CORSMiddleware, and /health endpoint returning `{"status": "ok", "version": "1.0.0"}`
- pydantic-settings Settings class with all 7 required env vars — service crashes at startup if any are absent
- SQLAlchemy 2.0 async engine + async_session_factory with get_db dependency injection pattern
- Docker image builds successfully (python:3.12-slim, libpq/asyncpg deps), docker-compose with hot reload volume and /health healthcheck
- Supabase migration with pgvector extension, all 4 personal data tables (user_profiles, memory_facts, user_events, user_contacts), RLS enabled on each with (select auth.uid()) caching syntax

## Task Commits

Each task was committed atomically:

1. **Task 1: FastAPI project scaffold with config, database layer, and health endpoint** - `f72c6c9` (feat)
2. **Task 2: Docker Compose dev environment with healthcheck and hot reload** - `78ccbef` (feat)
3. **Task 3: Supabase schema migration — all personal data tables with RLS** - `1a20b9a` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `velar-backend/app/main.py` - FastAPI app with lifespan, CORS, router mounts
- `velar-backend/app/config.py` - pydantic-settings Settings singleton (7 required vars)
- `velar-backend/app/database.py` - SQLAlchemy async engine, session factory, get_db dependency
- `velar-backend/app/health/router.py` - GET /health returning status/version
- `velar-backend/app/auth/router.py` - Empty stub APIRouter for future auth routes
- `velar-backend/app/auth/schemas.py` - LoginRequest, TokenResponse Pydantic models
- `velar-backend/app/users/router.py` - Empty stub APIRouter for future user routes
- `velar-backend/app/users/schemas.py` - UserProfile Pydantic model
- `velar-backend/Dockerfile` - python:3.12-slim, libpq-dev/gcc/curl for asyncpg
- `velar-backend/docker-compose.yml` - Single api service, env_file, hot-reload, healthcheck
- `velar-backend/.dockerignore` - Excludes .env, __pycache__, tests/, .git
- `velar-backend/.env.example` - All 7 env var placeholders (no real values)
- `velar-backend/requirements.txt` - Full stack dependencies
- `velar-backend/pyproject.toml` - Project metadata + pytest asyncio_mode=auto config
- `velar-backend/supabase/migrations/20260301000001_initial_schema.sql` - Full schema with pgvector + 4 tables + RLS
- `velar-backend/supabase/seed.sql` - Empty placeholder
- `velar-backend/app/__init__.py`, `velar-backend/app/health/__init__.py`, etc. - Empty package init files

## Decisions Made
- Used cloud-only Supabase (no local container in docker-compose) — satisfies SYNC-02 requirement for cloud schema
- pydantic-settings intentionally has no defaults for the 5 secret vars — startup failure is the desired behavior
- asyncpg direct connectivity check in lifespan converts `postgresql+asyncpg://` DSN to `postgresql://` for the asyncpg.connect() call
- RLS policies use `(select auth.uid())` caching syntax instead of bare `auth.uid()` to avoid per-row function invocation overhead
- memory_facts uses EAV triple pattern with `valid_from`/`valid_until`/`superseded_by` columns to support time-versioned facts

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added stub router.py files for auth and users**
- **Found during:** Task 1 (main.py mount of auth_router and users_router)
- **Issue:** Plan listed only schemas.py for auth and users modules, but main.py imports router.py from each — missing router files would cause ImportError at startup
- **Fix:** Created app/auth/router.py and app/users/router.py with empty APIRouters
- **Files modified:** velar-backend/app/auth/router.py, velar-backend/app/users/router.py
- **Verification:** main.py imports cleanly; router objects exist
- **Committed in:** f72c6c9 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical — import correctness)
**Impact on plan:** Necessary for the app to start. No scope creep.

## Issues Encountered
None — Docker build succeeded on first attempt. All file checks passed.

## User Setup Required
**External services require manual configuration before `docker-compose up` will succeed.**

To run the service:
1. Copy `.env.example` to `.env` in `velar-backend/`
2. Fill in real values from your Supabase project dashboard:
   - `SUPABASE_URL` — Project URL (Settings > API)
   - `SUPABASE_ANON_KEY` — Anon/public key (Settings > API)
   - `SUPABASE_SERVICE_ROLE_KEY` — Service role key (Settings > API, keep secret)
   - `SUPABASE_JWT_SECRET` — JWT secret (Settings > Auth)
   - `DATABASE_URL` — Direct connection URL (Settings > Database > Connection string, use asyncpg format: `postgresql+asyncpg://postgres:[password]@db.[project-ref].supabase.co:5432/postgres`)
3. Apply migration to Supabase cloud:
   ```bash
   cd velar-backend
   supabase link --project-ref YOUR_PROJECT_REF
   supabase db push
   ```
4. Start the service:
   ```bash
   docker-compose up
   ```
5. Verify: `curl http://localhost:8000/health` should return `{"status":"ok","version":"1.0.0"}`

## Next Phase Readiness
- FastAPI skeleton is complete and runnable — Phase 2 can add voice pipeline routes to app/auth and new voice/ module
- Config pattern established: all new modules import `from app.config import settings`
- DB dependency established: `Depends(get_db)` in route handlers for async sessions
- Supabase schema is ready to push; pgvector enabled for Phase 3 memory embedding storage

---
*Phase: 01-foundation*
*Completed: 2026-03-01*
