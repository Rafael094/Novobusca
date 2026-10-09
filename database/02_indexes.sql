-- =============================================================================
-- IntelliINPI - 02_indexes.sql
-- Additional search indexes for the large INPI datasets.
-- Run AFTER the data has been loaded (bulk COPY is faster without them) and
-- after 01_extensions.sql. Idempotent (IF NOT EXISTS).
-- =============================================================================

-- --- Marcas -----------------------------------------------------------------
-- Trigram indexes enable fast ILIKE / similarity() searches on the big text
-- columns without a sequential scan over millions of rows.
CREATE INDEX IF NOT EXISTS ix_marcas_elemento_nominativo_trgm
    ON marcas USING gin (elemento_nominativo gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_marcas_elemento_nominativo_fold
    ON marcas (public.fold(elemento_nominativo));

CREATE INDEX IF NOT EXISTS ix_marcas_numero_inpi_trgm
    ON marcas USING gin (numero_inpi gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_marcas_depositantes_nome_trgm
    ON marcas_depositantes USING gin (nome gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_marcas_depositantes_codigo_interno
    ON marcas_depositantes (codigo_interno);

-- --- Patentes ---------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_patentes_conteudo_titulo_trgm
    ON patentes_conteudo USING gin (titulo gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_patentes_conteudo_resumo_trgm
    ON patentes_conteudo USING gin (resumo gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_patentes_conteudo_codigo_interno
    ON patentes_conteudo (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_depositantes_depositante_trgm
    ON patentes_depositantes USING gin (depositante gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_patentes_depositantes_codigo_interno
    ON patentes_depositantes (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_inventores_autor_trgm
    ON patentes_inventores USING gin (autor gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_patentes_inventores_codigo_interno
    ON patentes_inventores (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_numero_inpi_trgm
    ON patentes USING gin (numero_inpi gin_trgm_ops);

-- --- Foreign-key helper indexes (join performance) --------------------------
CREATE INDEX IF NOT EXISTS ix_marcas_codigo_interno
    ON marcas (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_codigo_interno
    ON patentes (codigo_interno);
