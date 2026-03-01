-- ============================================================
-- VELAR Phase 1: Initial Schema
-- ============================================================

-- 1. Enable required extensions (must come first)
create extension if not exists vector with schema extensions;

-- 2. user_profiles — 1:1 with auth.users
create table public.user_profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  display_name  text,
  locale        text not null default 'tr',  -- 'tr' or 'en'
  timezone      text not null default 'Europe/Istanbul',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

alter table public.user_profiles enable row level security;

create policy "Users can view own profile"
on public.user_profiles for select
to authenticated
using ( (select auth.uid()) = id );

create policy "Users can insert own profile"
on public.user_profiles for insert
to authenticated
with check ( (select auth.uid()) = id );

create policy "Users can update own profile"
on public.user_profiles for update
to authenticated
using ( (select auth.uid()) = id )
with check ( (select auth.uid()) = id );

-- 3. memory_facts — EAV triples with supersede versioning
create table public.memory_facts (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  category      text not null,         -- 'health', 'preference', 'social', 'place', 'habit', 'goal'
  key           text not null,         -- e.g. 'blood_type', 'diet_restriction', 'mother_name'
  value         text not null,
  source        text not null default 'conversation',  -- 'conversation', 'explicit', 'derived'
  confidence    float not null default 1.0 check (confidence >= 0.0 and confidence <= 1.0),
  embedding     extensions.vector(1536),  -- OpenAI text-embedding-ada-002 dimensions
  valid_from    timestamptz not null default now(),
  valid_until   timestamptz,           -- null = currently active
  superseded_by uuid references public.memory_facts(id),
  created_at    timestamptz not null default now()
);

create index on public.memory_facts (user_id, category, key) where valid_until is null;

alter table public.memory_facts enable row level security;

create policy "Users manage own facts"
on public.memory_facts for all
to authenticated
using ( (select auth.uid()) = user_id )
with check ( (select auth.uid()) = user_id );

-- View: only active (non-superseded) facts
create view public.active_memory_facts as
  select * from public.memory_facts
  where valid_until is null and superseded_by is null;

-- 4. user_events — log of meals, visits, conversations, habits
create table public.user_events (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  event_type    text not null,         -- 'meal', 'visit', 'conversation', 'habit', 'mood'
  occurred_at   timestamptz not null default now(),
  payload       jsonb not null default '{}',  -- flexible per event_type
  created_at    timestamptz not null default now()
);

create index on public.user_events (user_id, event_type, occurred_at desc);

alter table public.user_events enable row level security;

create policy "Users manage own events"
on public.user_events for all
to authenticated
using ( (select auth.uid()) = user_id )
with check ( (select auth.uid()) = user_id );

-- 5. user_contacts — relationship graph nodes
create table public.user_contacts (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  name            text not null,
  relationship    text,               -- 'mother', 'friend', 'colleague', etc.
  birthday        date,
  notes           text,
  last_contact_at timestamptz,
  payload         jsonb not null default '{}',  -- extensible metadata
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

alter table public.user_contacts enable row level security;

create policy "Users manage own contacts"
on public.user_contacts for all
to authenticated
using ( (select auth.uid()) = user_id )
with check ( (select auth.uid()) = user_id );
