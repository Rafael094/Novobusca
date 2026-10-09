-- =============================================================================
-- IntelliINPI - 03_fts_search.sql
-- Full-text search indexes (Portuguese configuration) for titles/marks.
-- Run after 01_extensions.sql and after the data has been loaded. Idempotent.
-- =============================================================================

-- --- Marcas: full-text on the nominative element (the brand name) -----------
-- We store the tsvector in a generated column and index it with GIN. Queries use
-- to_tsquery('portuguese', ...) or plainto_tsquery('portuguese', ...).
ALTER TABLE marcas
    ADD COLUMN IF NOT EXISTS elemento_nominativo_tsv tsvector
    GENERATED ALWAYS AS (
        to_tsvector('portuguese', coalesce(elemento_nominativo, ''))
    ) STORED;

CREATE INDEX IF NOT EXISTS ix_marcas_elemento_nominativo_fts
    ON marcas USING gin (elemento_nominativo_tsv);

-- --- Patentes: full-text on title + abstract --------------------------------
ALTER TABLE patentes_conteudo
    ADD COLUMN IF NOT EXISTS conteudo_tsv tsvector
    GENERATED ALWAYS AS (
        to_tsvector(
            'portuguese',
            coalesce(titulo, '') || ' ' || coalesce(resumo, '')
        )
    ) STORED;

CREATE INDEX IF NOT EXISTS ix_patentes_conteudo_fts
    ON patentes_conteudo USING gin (conteudo_tsv);

-- --- Optional: refresh planner statistics after bulk load -------------------
ANALYZE marcas;
ANALYZE marcas_depositantes;
ANALYZE marcas_classificacoes_nacionais;
ANALYZE marcas_classificacoes_nice;
ANALYZE marcas_classificacoes_viena;
ANALYZE marcas_despachos;
ANALYZE patentes;
ANALYZE patentes_conteudo;
ANALYZE patentes_depositantes;
ANALYZE patentes_inventores;
ANALYZE patentes_classificacao_ipc;
ANALYZE patentes_despachos;
ANALYZE patentes_prioridades;
ANALYZE patentes_renumeracoes;
ANALYZE patentes_procuradores;
ANALYZE patentes_vinculos;
