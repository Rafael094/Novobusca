-- =============================================================================
-- IntelliINPI - 04_auditoria_indexes.sql
--
-- AUDITORIA (SOMENTE LEITURA) de todos os índices de todas as tabelas.
-- Não altera nada: pode rodar a qualquer momento, inclusive em produção.
--
-- Como rodar na VM (container do Postgres):
--   docker exec -it inpi-postgres psql -U postgres -d intelliinpi_app -f - < database/04_auditoria_indexes.sql
-- ou, dentro do psql:
--   \i /tmp/04_auditoria_indexes.sql
--
-- O que responder:
--   PARTE 1  ambiente e tamanho do banco
--   PARTE 2  tabelas: linhas estimadas, dados, índices, total
--   PARTE 3  TODOS os índices existentes (tabela, nome, tamanho, definição)
--   PARTE 4  índices INVÁLIDOS (sobra de CREATE INDEX CONCURRENTLY interrompido)
--   PARTE 5  índices REDUNDANTES (mesma definição, nomes diferentes)
--   PARTE 6  chaves estrangeiras SEM índice de apoio
--   PARTE 7  extensões instaladas (pg_trgm / unaccent são obrigatórias)
-- =============================================================================

\echo '==================== PARTE 1: ambiente ===================='
SELECT current_database()                                        AS banco,
       current_setting('server_version')                         AS versao_postgres,
       pg_size_pretty(pg_database_size(current_database()))      AS tamanho_banco,
       current_setting('maintenance_work_mem')                   AS maintenance_work_mem,
       current_setting('max_parallel_maintenance_workers')       AS parallel_maintenance_workers;

\echo '==================== PARTE 2: tabelas ===================='
SELECT c.relname                                        AS tabela,
       c.reltuples::bigint                              AS linhas_estimadas,
       pg_size_pretty(pg_relation_size(c.oid))          AS dados,
       pg_size_pretty(pg_indexes_size(c.oid))           AS indices,
       pg_size_pretty(pg_total_relation_size(c.oid))    AS total,
       (SELECT count(*) FROM pg_index i WHERE i.indrelid = c.oid) AS qtd_indices
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY pg_total_relation_size(c.oid) DESC;

\echo '==================== PARTE 3: todos os indices ===================='
SELECT c.relname                                            AS tabela,
       ic.relname                                           AS indice,
       i.indisprimary                                       AS pk,
       i.indisunique                                        AS unico,
       i.indisvalid                                         AS valido,
       pg_size_pretty(pg_relation_size(ic.oid))             AS tamanho,
       regexp_replace(pg_get_indexdef(ic.oid),
                      '^CREATE (UNIQUE )?INDEX [^ ]+ ON ', '') AS definicao
FROM pg_index i
JOIN pg_class c  ON c.oid  = i.indrelid
JOIN pg_class ic ON ic.oid = i.indexrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname, ic.relname;

\echo '==================== PARTE 4: indices invalidos ===================='
-- Se aparecer algo aqui, remova com:  DROP INDEX CONCURRENTLY <indice>;
SELECT c.relname AS tabela, ic.relname AS indice, i.indisvalid, i.indisready
FROM pg_index i
JOIN pg_class c  ON c.oid  = i.indrelid
JOIN pg_class ic ON ic.oid = i.indexrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND (NOT i.indisvalid OR NOT i.indisready)
ORDER BY 1, 2;

\echo '==================== PARTE 5: indices redundantes ===================='
-- Mesma tabela + mesma definição (ignorando o nome) => um dos dois é dispensável.
WITH d AS (
    SELECT c.relname AS tabela,
           ic.relname AS indice,
           replace(regexp_replace(regexp_replace(pg_get_indexdef(ic.oid),
                   '^CREATE (UNIQUE )?INDEX [^ ]+ ON ', ''),
                   '\s+', ' ', 'g'), 'public.', '') AS definicao,
           pg_relation_size(ic.oid) AS bytes
    FROM pg_index i
    JOIN pg_class c  ON c.oid  = i.indrelid
    JOIN pg_class ic ON ic.oid = i.indexrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r' AND i.indisvalid
)
SELECT tabela,
       definicao,
       count(*)                                 AS qtd,
       string_agg(indice, ', ' ORDER BY indice)  AS indices,
       pg_size_pretty(sum(bytes))               AS tamanho_desnecessario
FROM d
GROUP BY tabela, definicao
HAVING count(*) > 1
ORDER BY sum(bytes) DESC;

\echo '==================== PARTE 6: FKs sem indice de apoio ===================='
SELECT conrelid::regclass::text AS tabela,
       conname                  AS chave_estrangeira,
       pg_get_constraintdef(oid) AS definicao
FROM pg_constraint
WHERE contype = 'f'
  AND connamespace = 'public'::regnamespace
  AND NOT EXISTS (
        SELECT 1 FROM pg_index i
        WHERE i.indrelid = conrelid AND i.indkey[0] = conkey[1]
      )
ORDER BY 1, 2;

\echo '==================== PARTE 7: extensoes ===================='
SELECT extname, extversion FROM pg_extension ORDER BY extname;
