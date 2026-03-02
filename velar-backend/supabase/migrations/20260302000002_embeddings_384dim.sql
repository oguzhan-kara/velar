-- Run this migration if switching to local embeddings (EMBEDDING_PROVIDER=local)
-- ============================================================
-- VELAR Phase 5: Switch memory_facts embedding column to 384 dims
-- ============================================================
-- The Phase 1 + Phase 3 migrations created memory_facts with a vector(1536)
-- embedding column (OpenAI text-embedding-3-small dimensions) and an HNSW index.
--
-- This migration downsizes the embedding column to vector(384) to match the
-- sentence-transformers model paraphrase-multilingual-MiniLM-L12-v2 used when
-- EMBEDDING_PROVIDER=local (the new default free-tier path).
--
-- Steps:
--   1. Drop the existing HNSW index (it references the old dimension)
--   2. Alter the column type to vector(384)
--   3. Clear stale 1536-dim embeddings so they are re-embedded at 384 dims
--   4. Recreate the HNSW index for the new dimension
--
-- IMPORTANT: After running this migration, all existing embeddings become NULL
-- and will be re-populated on next memory access. Facts remain queryable by
-- category/key filter; semantic search resumes as embeddings are re-created.
--
-- To revert to OpenAI/1536 dims: set EMBEDDING_PROVIDER=openai and run a
-- companion migration that reverses this one (alter back to vector(1536), etc.).
--
-- APPLY: Run via Supabase dashboard SQL editor or `supabase db push`.
-- ============================================================

-- Step 1: Drop the existing HNSW index on memory_facts(embedding)
DROP INDEX IF EXISTS public.memory_facts_embedding_hnsw;

-- Step 2: Alter memory_facts.embedding column to vector(384)
ALTER TABLE public.memory_facts
    ALTER COLUMN embedding TYPE extensions.vector(384)
    USING NULL::extensions.vector(384);

-- Step 3: Clear existing embedding data (stale 1536-dim vectors are incompatible)
UPDATE public.memory_facts
SET embedding = NULL
WHERE embedding IS NOT NULL;

-- Step 4: Recreate HNSW index with vector_cosine_ops for the new 384-dim column
-- Same index parameters as Phase 3 (m=16, ef_construction=64)
CREATE INDEX IF NOT EXISTS memory_facts_embedding_hnsw
ON public.memory_facts
USING hnsw (embedding extensions.vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
