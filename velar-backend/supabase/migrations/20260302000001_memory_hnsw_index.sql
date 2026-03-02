-- ============================================================
-- VELAR Phase 3: HNSW index for memory_facts semantic search
-- ============================================================
-- The Phase 1 migration created memory_facts with a vector(1536)
-- embedding column but no vector index — only a B-tree index on
-- (user_id, category, key) for point lookups. Without a vector
-- index, every semantic retrieval is a full sequential scan.
--
-- HNSW is preferred over IVFFlat for Phase 3 (empty table at start):
-- IVFFlat requires data before creation; HNSW creates immediately
-- and self-updates as rows are inserted.
--
-- m=16, ef_construction=64: recommended defaults for datasets up to
-- ~100K rows per pgvector documentation.
--
-- NOTE: The embedding column is typed extensions.vector(1536) because
-- the pgvector extension was created in the 'extensions' schema in Phase 1.
-- The index operator class must reference extensions.vector_cosine_ops.
--
-- APPLY: Run this migration via the Supabase dashboard SQL editor or
-- `supabase db push` before running any tests that touch the embedding
-- column. Verify in Supabase dashboard: Table Editor > memory_facts >
-- Indexes should show memory_facts_embedding_hnsw, or run:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'memory_facts';
-- ============================================================

CREATE INDEX IF NOT EXISTS memory_facts_embedding_hnsw
ON public.memory_facts
USING hnsw (embedding extensions.vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Fix active_memory_facts view RLS: the view was created without
-- SECURITY INVOKER, which means view queries could bypass RLS on
-- the base table. Re-create with security_invoker = true so the
-- view respects the calling user's RLS policies.
-- Note: Python code in Phase 3 always queries memory_facts directly
-- with ORM filters (never the view) as an additional safeguard.
CREATE OR REPLACE VIEW public.active_memory_facts
WITH (security_invoker = true) AS
  SELECT * FROM public.memory_facts
  WHERE valid_until IS NULL AND superseded_by IS NULL;
