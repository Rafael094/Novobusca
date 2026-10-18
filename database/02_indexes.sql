-- =============================================================================
-- IntelliINPI - 02_indexes.sql
--
-- ATENÇÃO (desde a revisão de índices): este script NÃO é mais necessário no
-- deploy. O `docker-compose.prod.yml` roda `python -m app.db_indexes` antes do
-- seed e cria a cada subida da API tudo o que estiver faltando (mesmo manifesto,
-- idempotente, tolerante a falha). Mantido para execução manual via psql em um
-- banco que o app não alcança — a fonte canônica do manifesto é
-- `backend/app/db_indexes.py` (`python -m app.db_indexes --emit-sql` gera o
-- equivalente em SQL).
--
-- Índices de BUSCA das bases do INPI (marcas/patentes) e das suas tabelas de
-- relacionamento. É isto que faz /api/marcas/search, /api/patentes/search e
-- /api/search deixarem de varrer milhões de linhas (era 76 s por busca exata;
-- com índice: ~1 ms).
--
-- QUANDO RODAR
--   DEPOIS de carregar os CSVs (o COPY em massa é mais rápido sem índices) e
--   DEPOIS de 01_extensions.sql + `alembic upgrade head`.
--   É idempotente (IF NOT EXISTS) e seguro para reexecução.
--
-- PRODUÇÃO (VM Oracle, Postgres no container `inpi-postgres`)
--   docker cp database/02_indexes.sql inpi-postgres:/tmp/02_indexes.sql
--   docker exec -d inpi-postgres sh -c \
--     'psql -U postgres -d intelliinpi_app -f /tmp/02_indexes.sql > /tmp/02_indexes.log 2>&1'
--   docker exec -it inpi-postgres tail -f /tmp/02_indexes.log
--
-- ORDEM DAS FASES (importante: o pesado fica por último)
--   FASE 1  btree de marcas          -> destrava a busca exata (o mais urgente)
--   FASE 2  btree das relações       -> elimina ~5 Seq Scans por página de busca
--   FASE 3  btree de patentes        -> idem para patentes
--   FASE 4  ANALYZE                  -> o planner passa a usar os índices novos
--   FASE 5  GIN trigram (PESADO)     -> só afeta "Contém" / "Começa com" / busca global
--   FASE 6  ANALYZE final
--
-- ⚠️  A FASE 5 é a única que pode consumir vários GB de disco e horas de CPU.
--     Antes de rodar, confira o espaço livre (`df -h` na VM). Se não houver
--     folga (>= 8 GB livres), comente/remova a FASE 5: as fases 1-4 já
--     resolvem a lentidão das buscas por nome (modo "Exata", o padrão da tela).
--
-- Nomes dos índices = exatamente os declarados pelo ORM/alembic
-- (backend/app/models/*.py). Não renomeie: os scripts 04/05 comparam por
-- DEFINIÇÃO (não por nome) justamente para nunca duplicar um índice.
-- =============================================================================

-- --- 0. Dependências (idempotentes) ------------------------------------------
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Helper accent-insensitive imutável usado pelos índices funcionais abaixo
-- (unaccent() é STABLE e não pode ser usado direto em índice).
CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$
    SELECT public.unaccent('public.unaccent', $1)
$$;

CREATE OR REPLACE FUNCTION public.fold(text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$
    SELECT lower(public.immutable_unaccent($1))
$$;

-- --- Sessão: deixa os builds longos usarem memória e não serem interrompidos -
SET statement_timeout = 0;
SET lock_timeout = 0;
SET maintenance_work_mem = '256MB';        -- suba para 1GB se a VM tiver RAM sobrando
SET max_parallel_maintenance_workers = 2;   -- suba para 4 se a VM tiver >= 4 vCPU

\echo '=== FASE 1: marcas (busca) ==='

-- =============================================================================
-- FASE 1 - MARCAS (6,6M linhas)
-- =============================================================================
-- Busca exata: WHERE public.fold(elemento_nominativo) = public.fold($1)
CREATE INDEX IF NOT EXISTS ix_marcas_elemento_nominativo_fold
    ON marcas (public.fold(elemento_nominativo));

-- Listagem por id / join com as tabelas de relacionamento
CREATE INDEX IF NOT EXISTS ix_marcas_codigo_interno
    ON marcas (codigo_interno);

-- Filtros da tela
CREATE INDEX IF NOT EXISTS ix_marcas_numero_inpi
    ON marcas (numero_inpi);

CREATE INDEX IF NOT EXISTS ix_marcas_codigo_situacao
    ON marcas (codigo_situacao);

-- ORDER BY data_deposito DESC NULLS LAST (ordem da listagem de busca)
CREATE INDEX IF NOT EXISTS ix_marcas_data_deposito
    ON marcas (data_deposito DESC NULLS LAST);

-- Dashboard: WHERE data_vigencia >= hoje ORDER BY data_vigencia (sem isto = scan)
CREATE INDEX IF NOT EXISTS ix_marcas_data_vigencia
    ON marcas (data_vigencia);

\echo '=== FASE 2: marcas - relacoes (titulares, classes, despachos) ==='

-- =============================================================================
-- FASE 2 - RELAÇÕES DE MARCAS
-- Cada uma destas elimina um Seq Scan que a busca paga em TODA página
-- (as cargas de titulares / classificações / despachos filtram por
-- codigo_interno IN (...)).
-- =============================================================================
CREATE INDEX IF NOT EXISTS ix_marcas_dep_codigo_interno
    ON marcas_depositantes (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_marcas_dep_nome
    ON marcas_depositantes (nome);

CREATE INDEX IF NOT EXISTS ix_marcas_cn_codigo_interno
    ON marcas_classificacoes_nacionais (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_marcas_nice_codigo_interno
    ON marcas_classificacoes_nice (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_marcas_viena_codigo_interno
    ON marcas_classificacoes_viena (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_marcas_desp_codigo_interno
    ON marcas_despachos (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_marcas_desp_codigo_despacho
    ON marcas_despachos (codigo_despacho);

CREATE INDEX IF NOT EXISTS ix_marcas_logos_codigo_interno
    ON marcas_logos (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_marcas_logos_status
    ON marcas_logos (status);

\echo '=== FASE 3: patentes ==='

-- =============================================================================
-- FASE 3 - PATENTES
-- =============================================================================
CREATE INDEX IF NOT EXISTS ix_patentes_codigo_interno
    ON patentes (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_numero_inpi
    ON patentes (numero_inpi);

CREATE INDEX IF NOT EXISTS ix_patentes_data_deposito
    ON patentes (data_deposito);

-- Relações de patentes (detalhe + join do título na listagem do monitoramento)
CREATE INDEX IF NOT EXISTS ix_patentes_conteudo_codigo_interno
    ON patentes_conteudo (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_conteudo_numero_inpi
    ON patentes_conteudo (numero_inpi);

CREATE INDEX IF NOT EXISTS ix_patentes_dep_codigo_interno
    ON patentes_depositantes (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_dep_depositante
    ON patentes_depositantes (depositante);

CREATE INDEX IF NOT EXISTS ix_patentes_inv_codigo_interno
    ON patentes_inventores (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_inv_autor
    ON patentes_inventores (autor);

CREATE INDEX IF NOT EXISTS ix_patentes_proc_codigo_interno
    ON patentes_procuradores (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_proc_procurador
    ON patentes_procuradores (procurador);

CREATE INDEX IF NOT EXISTS ix_patentes_prio_codigo_interno
    ON patentes_prioridades (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_ipc_codigo_interno
    ON patentes_classificacao_ipc (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_ipc_simbolo
    ON patentes_classificacao_ipc (simbolo);

CREATE INDEX IF NOT EXISTS ix_patentes_desp_codigo_interno
    ON patentes_despachos (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_desp_codigo_despacho
    ON patentes_despachos (codigo_despacho);

CREATE INDEX IF NOT EXISTS ix_patentes_renum_codigo_interno
    ON patentes_renumeracoes (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_patentes_vinc_origem
    ON patentes_vinculos (codigo_interno_origem);

CREATE INDEX IF NOT EXISTS ix_patentes_vinc_derivado
    ON patentes_vinculos (codigo_interno_derivado);

-- =============================================================================
-- FASE 4 - ANALYZE (sem isto o planner pode continuar preferindo Seq Scan)
-- =============================================================================
\echo '=== FASE 4: ANALYZE ==='

ANALYZE marcas;
ANALYZE marcas_depositantes;
ANALYZE marcas_classificacoes_nacionais;
ANALYZE marcas_classificacoes_nice;
ANALYZE marcas_classificacoes_viena;
ANALYZE marcas_despachos;
ANALYZE marcas_logos;
ANALYZE patentes;
ANALYZE patentes_conteudo;
ANALYZE patentes_depositantes;
ANALYZE patentes_inventores;
ANALYZE patentes_procuradores;
ANALYZE patentes_prioridades;
ANALYZE patentes_classificacao_ipc;
ANALYZE patentes_despachos;
ANALYZE patentes_renumeracoes;
ANALYZE patentes_vinculos;

-- =============================================================================
-- FASE 5 - GIN TRIGRAM  (PESADO: horas + vários GB)
-- Só serve para: modo "Contém" (ILIKE '%x%'), modo "Começa com" (prefixo no
-- fold) e a busca global. Se o disco estiver apertado, remova esta fase.
-- =============================================================================
\echo '=== FASE 5: GIN trigram (PESADO) ==='

-- "Contém", busca global e /api/analises: elemento_nominativo ILIKE '%x%'
CREATE INDEX IF NOT EXISTS ix_marcas_elemento_nominativo_trgm
    ON marcas USING gin (elemento_nominativo gin_trgm_ops);

-- Modo "Começa com": public.fold(elemento_nominativo) LIKE fold($1) || '%'
CREATE INDEX IF NOT EXISTS ix_marcas_fold_trgm
    ON marcas USING gin (public.fold(elemento_nominativo) gin_trgm_ops);

-- Busca global: numero_inpi ILIKE '%x%'
CREATE INDEX IF NOT EXISTS ix_marcas_numero_inpi_trgm
    ON marcas USING gin (numero_inpi gin_trgm_ops);

-- Patentes: titulo/resumo ILIKE '%x%'
CREATE INDEX IF NOT EXISTS ix_patentes_conteudo_titulo_trgm
    ON patentes_conteudo USING gin (titulo gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_patentes_conteudo_resumo_trgm
    ON patentes_conteudo USING gin (resumo gin_trgm_ops);

-- Patentes: numero_inpi / numero_pct ILIKE '%x%'
CREATE INDEX IF NOT EXISTS ix_patentes_numero_inpi_trgm
    ON patentes USING gin (numero_inpi gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_patentes_numero_pct_trgm
    ON patentes USING gin (numero_pct gin_trgm_ops);

-- =============================================================================
-- FASE 6 - ANALYZE final
-- =============================================================================
\echo '=== FASE 6: ANALYZE final ==='

ANALYZE marcas;
ANALYZE marcas_depositantes;
ANALYZE marcas_despachos;
ANALYZE patentes_conteudo;
ANALYZE patentes;

\echo '=== FIM de 02_indexes.sql ==='
