-- =============================================================================
-- IntelliINPI - 01_extensions.sql
-- Extensions used for fast, accent-insensitive search on the INPI datasets.
-- Safe to run multiple times (idempotent).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- trigram similarity / GIN indexes
CREATE EXTENSION IF NOT EXISTS unaccent;  -- accent-insensitive matching
CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- gen_random_uuid() fallback (PG < 13)

-- Immutable, accent-folded lowercase helper used by functional indexes below.
-- (unaccent() is STABLE, so it cannot be used directly in an index; we wrap it.)
CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
AS $$
    SELECT public.unaccent('public.unaccent', $1)
$$;

CREATE OR REPLACE FUNCTION public.fold(text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
AS $$
    SELECT lower(public.immutable_unaccent($1))
$$;
