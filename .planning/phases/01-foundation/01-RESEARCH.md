# Phase 1: Foundation - Research

**Researched:** 2026-03-01
**Domain:** FastAPI backend, Supabase PostgreSQL + pgvector, Docker, JWT authentication, RLS
**Confidence:** HIGH (core stack verified via official docs; schema patterns MEDIUM)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Personal Data Model**
- Supabase (PostgreSQL) with pgvector extension for semantic memory retrieval
- Schema must accommodate the full "life graph": health, food preferences, social contacts, places, habits, mood, goals
- Entity-attribute-value triples pattern for flexible fact storage
- Separate tables for: user profile, memory facts, user events (meals, visits, conversations), user contacts (relationship graph)
- pgvector embeddings column on facts table for semantic search
- Fact versioning via supersede pattern (new fact references old, old marked superseded — never delete)

**Authentication**
- Supabase Auth with email/password as primary method
- Apple Sign-In support for iOS/Watch devices deferred to Phase 6
- JWT tokens for API authentication — middleware validates on every request
- Single user focus initially, but schema supports multi-user via RLS from day one

**Deployment**
- Docker Compose for local development (FastAPI + Supabase local via CLI)
- Cloud Supabase project from day one for cross-device sync (requirement SYNC-02)
- Environment variables for all secrets — .env file for local, cloud env for production
- No cloud deployment of FastAPI yet — runs locally on Mac in Phase 1

**API Design**
- RESTful JSON API with standard HTTP methods
- Versioned endpoints (/api/v1/...)
- Consistent error response format: {error: string, code: string, details?: object}
- Health check endpoint at /health
- Auth-required on all endpoints except /health and /auth/*

### Claude's Discretion
- Exact Supabase table schemas and column types
- FastAPI project structure and module organization
- Docker Compose configuration details
- RLS policy implementation specifics
- Migration strategy and tooling
- Test structure and framework choice
- Logging and monitoring setup

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SYNC-02 | Memory and personal data accessible from any device | Cloud Supabase project from day one; schema lives in cloud Supabase, not local-only; FastAPI connects via DATABASE_URL env var pointing to cloud instance |
</phase_requirements>

---

## Summary

This phase establishes the backend foundation that every subsequent VELAR phase depends on. The stack is FastAPI (Python) connecting to a cloud-hosted Supabase PostgreSQL project. There are two distinct data access paths that must not be confused: (1) FastAPI validates user JWTs from Supabase Auth, then performs queries **as the authenticated user** so RLS policies apply; (2) Administrative operations (seed data, migrations) use the service role key which bypasses RLS entirely and must be kept server-side only.

The critical insight from research: Supabase now recommends JWKS/ES256 asymmetric JWT signing over the legacy HS256 shared secret for new projects. This affects how the FastAPI middleware decodes tokens. For a fresh project in 2026, configure the Supabase project to use asymmetric keys and validate via the JWKS endpoint rather than the legacy JWT secret.

RLS is the security foundation. The January 2025 incident where 170+ apps built with Lovable exposed databases due to missing/misconfigured RLS confirms that RLS must be (a) enabled on every table, (b) tested with a non-owner account as part of the acceptance criteria, and (c) implemented with the performance-optimized `(select auth.uid())` caching syntax. The schema for this phase is relatively simple — the complex memory schema (EAV triples, pgvector embeddings) is scaffolded here but populated in Phase 3.

**Primary recommendation:** Use supabase-py for auth operations, raw asyncpg (via SQLAlchemy 2.0 async) for data queries — this lets RLS work correctly by passing user JWTs through rather than always using the service role key.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | >=0.115 | Web framework, routing, dependency injection | Standard for Python async APIs; automatic OpenAPI docs; Pydantic-native |
| uvicorn | >=0.30 | ASGI server | FastAPI's recommended server; supports hot reload with --reload |
| pydantic-settings | >=2.0 | Environment variable / .env config management | Official pydantic v2 approach; replaces BaseSettings in pydantic v1 |
| supabase-py | >=2.0 | Supabase client for Auth operations | Official Supabase Python client; handles Auth sign-in, sign-up, session management |
| python-jose[cryptography] | >=3.3 | JWT decode and JWKS validation | Better error messages than PyJWT; supports asymmetric ES256 via JWKS |
| asyncpg | >=0.29 | Async PostgreSQL driver | High-performance; works with SQLAlchemy 2.0 async engine |
| sqlalchemy | >=2.0 | ORM / async query builder | SQLAlchemy 2.0 has first-class async support; familiar abstraction over asyncpg |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | >=1.0 | Load .env file in local dev | pydantic-settings handles this natively; still useful as fallback |
| httpx | >=0.27 | Async HTTP client | Needed for JWKS endpoint fetching; also used in tests |
| pytest | >=8.0 | Test framework | Standard Python testing |
| pytest-asyncio | >=0.23 | Async test support for pytest | Required for testing FastAPI async routes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLAlchemy 2.0 async | Direct asyncpg only | Direct asyncpg has less overhead but no ORM; for this phase's simple queries either works — SQLAlchemy wins for Phase 3+ complexity |
| python-jose | PyJWT | PyJWT is simpler for HS256 but python-jose is better for JWKS/ES256; since Supabase recommends asymmetric keys for new projects, use python-jose |
| supabase-py (auth only) | manual auth API calls | supabase-py handles token refresh, session management; worth the dependency |

**Installation:**
```bash
# Core application
pip install fastapi uvicorn[standard] pydantic-settings supabase python-jose[cryptography] asyncpg sqlalchemy

# Development / test
pip install pytest pytest-asyncio httpx python-dotenv
```

---

## Architecture Patterns

### Recommended Project Structure
```
velar-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app creation, lifespan, router inclusion
│   ├── config.py            # pydantic-settings Settings class
│   ├── dependencies.py      # Shared FastAPI dependencies (get_current_user, get_db)
│   ├── middleware.py        # JWT auth middleware
│   ├── database.py          # SQLAlchemy async engine + session factory
│   │
│   ├── auth/
│   │   ├── router.py        # POST /api/v1/auth/login, /auth/refresh
│   │   ├── schemas.py       # Pydantic request/response models
│   │   └── service.py       # Supabase auth calls
│   │
│   ├── health/
│   │   └── router.py        # GET /health — no auth required
│   │
│   └── users/
│       ├── router.py        # GET /api/v1/users/me
│       ├── schemas.py
│       └── service.py
│
├── supabase/
│   ├── migrations/          # SQL migration files (managed by Supabase CLI)
│   └── seed.sql             # Optional seed data
│
├── tests/
│   ├── conftest.py          # Fixtures: test client, test DB session
│   └── test_auth.py
│
├── Dockerfile
├── docker-compose.yml
├── .env.example             # Template — never commit actual .env
├── pyproject.toml
└── requirements.txt
```

### Pattern 1: JWT Auth via Dependency Injection
**What:** Validate Supabase JWT on every protected route using FastAPI's dependency system, not middleware. Middleware can't return clean JSON errors; dependencies can.
**When to use:** All protected routes (`/api/v1/...`)
**Example:**
```python
# Source: Supabase docs + FastAPI official security docs
# app/dependencies.py

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
from app.config import settings

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    try:
        # Fetch JWKS from Supabase (cache this in production)
        # For HS256 legacy: jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,  # or JWKS public key
            algorithms=["HS256"],           # use ["ES256"] for asymmetric
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": user_id, "email": payload.get("email")}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
```

### Pattern 2: pydantic-settings Configuration
**What:** All secrets and environment-specific config via pydantic-settings BaseSettings. Fails fast at startup if required vars are missing.
**When to use:** Always — no hardcoded config anywhere.
**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
# app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str  # from Supabase dashboard > Settings > Auth

    # Database
    database_url: str  # postgresql+asyncpg://... pointing to cloud Supabase

    # App
    environment: str = "development"
    debug: bool = False

settings = Settings()  # crashes at startup if required vars missing
```

### Pattern 3: Supabase RLS — User-Scoped Query Pattern
**What:** When FastAPI queries Supabase PostgreSQL on behalf of a user, it must either: (a) create a user-scoped Supabase client passing the user's JWT, or (b) use the service role client but pass `user_id` explicitly in WHERE clauses. Option (a) is safer because RLS enforces it automatically.
**When to use:** All data reads/writes that belong to a specific user.
**Example:**
```python
# Source: Supabase discussion #33811 + RLS docs
# app/users/service.py

from supabase import create_client

def get_user_client(user_jwt: str):
    """Create a Supabase client that acts as the authenticated user — RLS applies."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.auth.set_session(access_token=user_jwt, refresh_token="")
    return client

# Use admin client ONLY for administrative operations (never for user data reads)
admin_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
```

### Pattern 4: RLS Policy — Optimal Performance Syntax
**What:** Wrap `auth.uid()` in `(select auth.uid())` to cache the result per query rather than calling per-row.
**Source:** https://supabase.com/docs/guides/database/postgres/row-level-security (verified, official docs show "94.97% improvement" in benchmarks)
```sql
-- CORRECT (cached per query — use this)
create policy "Users see own data"
on public.memory_facts for select
to authenticated
using ( (select auth.uid()) = user_id );

-- WRONG (called per-row — do not use)
using ( auth.uid() = user_id );
```

### Pattern 5: Fact Versioning — Supersede Pattern
**What:** Never delete or update facts. When a fact changes, mark the old row `superseded_by` pointing to the new row's ID, set `valid_until` timestamp, insert new row.
**When to use:** All mutations to `memory_facts` table.
```sql
-- memory_facts schema sketch
create table public.memory_facts (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  category    text not null,           -- 'health', 'preference', 'contact', etc.
  key         text not null,           -- 'blood_type', 'diet', 'name_of_mother'
  value       text not null,
  source      text,                    -- 'conversation', 'explicit', 'derived'
  confidence  float default 1.0,
  embedding   extensions.vector(1536), -- OpenAI ada-002 dimensions
  valid_from  timestamptz default now(),
  valid_until timestamptz,             -- null = currently active
  superseded_by uuid references public.memory_facts(id),
  created_at  timestamptz default now()
);

-- Only active facts in normal queries
create view public.active_memory_facts as
  select * from public.memory_facts
  where valid_until is null and superseded_by is null;
```

### Anti-Patterns to Avoid
- **Using service role key for user data operations:** Bypasses RLS entirely. If a bug in query logic exists, no safety net. User-scoped client is mandatory for user data.
- **Middleware for JWT validation:** Middleware in FastAPI can't return structured JSON errors easily. Use dependency injection instead.
- **Hardcoded secrets in source:** Must crash at startup via pydantic-settings validation, never silently use defaults.
- **Blocking sync operations in async routes:** FastAPI is async — never call synchronous I/O (e.g., requests library) from an async route without running in a thread pool executor.
- **Not enabling RLS on every new table:** PostgreSQL tables are open by default. RLS must be explicitly enabled. Default should be: enable RLS, then add policies.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT decode + validation | Custom HMAC/RSA code | python-jose + Supabase JWKS | Algorithm confusion attacks, timing attacks, key ID handling — crypto is hard |
| DB migration tracking | Ad-hoc SQL files | Supabase CLI migrations (`supabase/migrations/`) | Built-in: timestamped, ordered, linked to cloud push workflow |
| Auth session management | Custom session store | Supabase Auth + supabase-py | Token refresh, session persistence, multi-device handled for free |
| Environment config validation | Manual `os.getenv()` with asserts | pydantic-settings BaseSettings | Type coercion, .env loading, required field validation, startup crash on missing vars |
| Async DB connection pool | Manual asyncpg pool | SQLAlchemy 2.0 async engine | Connection pool, context management, transaction handling |

**Key insight:** Supabase Auth + RLS replaces an entire auth layer that would take weeks to build and secure correctly. The value of this phase is wiring them together correctly, not reimplementing them.

---

## Common Pitfalls

### Pitfall 1: RLS Not Enabled (or Enabled Without Policies)
**What goes wrong:** Tables are created, but `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` is not run, OR RLS is enabled but no policies are created — which means all data is blocked, including from the owner.
**Why it happens:** Easy to miss in schema setup; Supabase dashboard shows a warning but CLI migrations don't enforce it.
**How to avoid:** Every migration that creates a table must include `ALTER TABLE public.tablename ENABLE ROW LEVEL SECURITY;` immediately after. Add policies in the same migration. Never leave them as separate steps.
**Warning signs:** Phase success criteria requires testing with a non-owner account — run this check as part of task acceptance.

### Pitfall 2: Using Legacy HS256 JWT Secret for New Projects
**What goes wrong:** Using the static JWT secret (HS256) from Supabase dashboard instead of JWKS endpoint means a leaked secret compromises all users permanently.
**Why it happens:** Older tutorials use HS256; it's simpler to implement initially.
**How to avoid:** For new Supabase projects in 2026, check if the project supports JWKS (asymmetric ES256). If so, use `python-jose` to fetch and cache the JWKS JSON and validate with `algorithms=["ES256"]`.
**Warning signs:** Supabase docs now explicitly say HS256 is "strongly discouraged." Verify current project JWT signing method in Supabase dashboard > Settings > Auth > JWT Settings.

### Pitfall 3: Service Role Key Exposed or Misused
**What goes wrong:** Service role key ends up in client-accessible code, logs, or is used for all queries instead of only admin operations.
**Why it happens:** Developers reach for the "all-access" key to avoid dealing with RLS during development.
**How to avoid:** Service role key is ONLY for: (1) initial DB setup/migration, (2) administrative background tasks with explicit user_id filtering. Never use it in request handlers that serve user data.
**Warning signs:** Any route handler that uses `admin_client` for data reads is a red flag.

### Pitfall 4: Blocking Sync Code in Async Routes
**What goes wrong:** `supabase-py` v2's synchronous client methods called from async FastAPI routes block the event loop, causing the entire server to stall under load.
**Why it happens:** `supabase-py` has both sync and async APIs; mixing them is easy.
**How to avoid:** Use `await client.auth.sign_in_with_password(...)` (async methods). For the async Supabase client, use `acreate_client()`. Or use `asyncio.to_thread()` for any unavoidably sync calls.
**Warning signs:** API response times spike under concurrent requests even for simple operations.

### Pitfall 5: Missing pgvector Extension Before Migration
**What goes wrong:** Migrations that create tables with `vector` columns fail because `CREATE EXTENSION vector` hasn't run.
**Why it happens:** Extension must be enabled before it can be used in column definitions.
**How to avoid:** First migration file (or Supabase dashboard) enables: `create extension if not exists vector with schema extensions;`. All subsequent migrations can reference `extensions.vector(1536)`.
**Warning signs:** `ERROR: type "vector" does not exist` during migration.

### Pitfall 6: CORS Not Configured
**What goes wrong:** The future iPhone app (Phase 6) and any browser-based clients are blocked by CORS.
**Why it happens:** FastAPI has no CORS by default; easy to forget in Phase 1.
**How to avoid:** Add `CORSMiddleware` in Phase 1 even though no clients exist yet. Restrict origins properly (not `"*"` in production).

---

## Code Examples

Verified patterns from official sources:

### Minimal FastAPI App with Lifespan and Health Check
```python
# Source: FastAPI official docs — https://fastapi.tiangolo.com/tutorial/bigger-applications/
# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.health.router import router as health_router
from app.auth.router import router as auth_router
from app.users.router import router as users_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection, warm JWKS cache
    yield
    # Shutdown: cleanup

app = FastAPI(
    title="VELAR API",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,  # hide docs in prod
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # expand as clients are added
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)                          # /health — no auth
app.include_router(auth_router, prefix="/api/v1/auth")    # /api/v1/auth/*
app.include_router(users_router, prefix="/api/v1/users")  # /api/v1/users/*
```

### Health Check Endpoint
```python
# app/health/router.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok"}
```

### RLS Policies for Core Tables
```sql
-- Source: Supabase RLS docs — https://supabase.com/docs/guides/database/postgres/row-level-security

-- user_profiles
alter table public.user_profiles enable row level security;

create policy "Users can view own profile"
on public.user_profiles for select
to authenticated
using ( (select auth.uid()) = id );

create policy "Users can update own profile"
on public.user_profiles for update
to authenticated
using ( (select auth.uid()) = id )
with check ( (select auth.uid()) = id );

create policy "Users can insert own profile"
on public.user_profiles for insert
to authenticated
with check ( (select auth.uid()) = id );

-- memory_facts
alter table public.memory_facts enable row level security;

create policy "Users manage own facts"
on public.memory_facts for all
to authenticated
using ( (select auth.uid()) = user_id )
with check ( (select auth.uid()) = user_id );
```

### Docker Compose for Local Development
```yaml
# docker-compose.yml
# Source: FastAPI Docker docs + Docker Compose best practices

version: "3.9"
services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app/app  # hot reload
    env_file:
      - .env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

# Note: Supabase runs as a cloud project (SYNC-02 requirement).
# Local Supabase CLI stack is only used for migration development/testing.
# For migration testing: run `supabase start` separately, not via Docker Compose.
```

### Dockerfile (Development)
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system deps for asyncpg
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| HS256 shared secret for JWT | JWKS/ES256 asymmetric keys | Supabase recommended 2025 | Can no longer validate with a single static secret; must fetch JWKS endpoint |
| pydantic v1 BaseSettings | pydantic-settings v2 (separate package) | Pydantic v2 release (2023) | `pydantic-settings` is now a separate install; old imports break |
| SQLAlchemy sync with psycopg2 | SQLAlchemy 2.0 async with asyncpg | SQLAlchemy 2.0 (2023) | Async I/O; dramatically different session API |
| FastAPI startup/shutdown events | `@asynccontextmanager` lifespan | FastAPI 0.93+ | Old `@app.on_event` is deprecated |
| supabase-py v1 (gotrue-py) | supabase-py v2 with unified auth | 2023-2024 | API surface changed; many v1 tutorials are wrong |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: Use `lifespan` context manager instead
- `pydantic.BaseSettings` (from pydantic v1): Use `pydantic_settings.BaseSettings` from separate `pydantic-settings` package
- Supabase HS256 JWT secret validation: Still works but is strongly discouraged for new projects; prefer JWKS

---

## Open Questions

1. **JWKS vs HS256 for this project**
   - What we know: Supabase docs say HS256 is "strongly discouraged" for new projects; JWKS with ES256 is recommended
   - What's unclear: Whether VELAR's Supabase project is already created and which JWT signing method is configured
   - Recommendation: At phase start, check Supabase dashboard > Settings > Auth > JWT Settings. If asymmetric keys are available, use JWKS. If project was pre-created with legacy HS256, document the JWT secret and plan migration.

2. **supabase-py async client stability**
   - What we know: Async client uses `acreate_client()`; only Realtime requires async; Auth methods have async variants
   - What's unclear: Whether the async client is production-stable for Auth operations or if sync client in thread pool is safer
   - Recommendation: Start with sync supabase-py client wrapped in `asyncio.to_thread()` for auth calls; migrate to async client if performance requires it.

3. **pgvector dimension choice**
   - What we know: OpenAI `text-embedding-ada-002` = 1536 dims; OpenAI `text-embedding-3-small` supports variable dims (default 1536, can reduce); local models vary
   - What's unclear: Which embedding model Phase 3 will use for memory retrieval
   - Recommendation: Schema uses `vector(1536)` for Phase 1; dimension can be changed before Phase 3 populates real embeddings, but requires migration.

4. **Supabase CLI local stack integration**
   - What we know: SYNC-02 requires cloud Supabase from day one; local CLI stack is for migration development
   - What's unclear: Whether Docker Compose should spin up the local Supabase stack for tests, or tests should run against cloud dev instance
   - Recommendation: Use the cloud dev project for all testing in Phase 1 (simpler setup, validates SYNC-02); document Supabase CLI workflow for schema iteration.

---

## Sources

### Primary (HIGH confidence)
- Supabase RLS official docs (https://supabase.com/docs/guides/database/postgres/row-level-security) — policy syntax, auth.uid(), performance optimization
- Supabase JWT docs (https://supabase.com/docs/guides/auth/jwts) — HS256 vs ES256/JWKS, current recommendation
- Supabase API keys docs (https://supabase.com/docs/guides/api/api-keys) — anon vs service role behavior
- Supabase pgvector docs (https://supabase.com/docs/guides/database/extensions/pgvector) — setup, schema, dimensions
- Supabase local development docs (https://supabase.com/docs/guides/local-development/overview) — CLI migration workflow, link/push commands
- Pydantic Settings docs (https://docs.pydantic.dev/latest/concepts/pydantic_settings/) — BaseSettings v2 API

### Secondary (MEDIUM confidence)
- FastAPI bigger applications docs (https://fastapi.tiangolo.com/tutorial/bigger-applications/) — router structure, APIRouter pattern
- FastAPI settings guide (https://fastapi.tiangolo.com/advanced/settings/) — pydantic-settings integration
- GitHub: zhanymkanov/fastapi-best-practices — module structure, service layer pattern (community-verified best practices repo)
- DEV.to: Validating Supabase JWT with Python/FastAPI (https://dev.to/zwx00/validating-a-supabase-jwt-locally-with-python-and-fastapi-59jf) — JWT decode code pattern

### Tertiary (LOW confidence — flag for validation)
- supabase-py async client stability: async methods documented but community reports of occasional edge cases in v2 auth — test at implementation time
- pgvector HNSW vs IVFFlat performance at small data sizes: benchmarks exist but findings vary; not relevant until Phase 3 when data volume matters

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core libraries verified via official docs; versions cross-checked
- Architecture: HIGH — module structure from FastAPI official docs + widely-used community patterns
- RLS patterns: HIGH — directly from Supabase official docs including performance guidance
- JWT handling: MEDIUM-HIGH — official docs confirm JWKS recommendation; exact python-jose integration pattern from community (MEDIUM), but algorithm choice from official docs (HIGH)
- Fact versioning schema: MEDIUM — supersede pattern is sound database design; specific column choices are Claude's discretion and will need refinement in planning
- Pitfalls: HIGH — RLS misconfiguration incident verified (January 2025, documented); blocking async verified from FastAPI docs; others from official guidance

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (Supabase is actively developed; JWT guidance in particular may evolve)
