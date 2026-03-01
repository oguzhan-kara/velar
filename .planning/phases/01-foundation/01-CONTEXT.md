# Phase 1: Foundation - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Secure backend with personal data storage and authentication. FastAPI service with Supabase integration, JWT auth middleware, row-level security, Docker dev environment. This is the base layer that every subsequent phase depends on — voice, memory, proactive engine, and all client apps talk to this backend.

</domain>

<decisions>
## Implementation Decisions

### Personal Data Model
- Supabase (PostgreSQL) with pgvector extension for semantic memory retrieval
- Schema must accommodate the full "life graph": health, food preferences, social contacts, places, habits, mood, goals
- Entity-attribute-value triples pattern for flexible fact storage (research recommendation)
- Separate tables for: user profile, memory facts, user events (meals, visits, conversations), user contacts (relationship graph)
- pgvector embeddings column on facts table for semantic search
- Fact versioning via supersede pattern (new fact references old, old marked superseded — never delete)

### Authentication
- Supabase Auth with email/password as primary method
- Apple Sign-In support for iOS/Watch devices (add in Phase 6 when iPhone app ships)
- JWT tokens for API authentication — middleware validates on every request
- Single user focus initially, but schema supports multi-user via RLS from day one

### Deployment
- Docker Compose for local development (FastAPI + Supabase local via CLI)
- Cloud Supabase project from day one for cross-device sync (requirement SYNC-02)
- Environment variables for all secrets — .env file for local, cloud env for production
- No cloud deployment of FastAPI yet — runs locally on Mac in Phase 1, cloud hosting deferred

### API Design
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

</decisions>

<specifics>
## Specific Ideas

- User wants cloud-backed data from day one (Firebase/Supabase decision landed on Supabase per research — pgvector advantage)
- Architecture must support multi-user later even though it's personal-first
- Research flagged: Firebase Security Rules misconfiguration is the #1 breach risk — RLS must be tested with non-owner accounts

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-01*
