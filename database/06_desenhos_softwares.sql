-- =============================================================================
-- IntelliINPI - 06_desenhos_softwares.sql
--
-- Cria as tabelas e os índices dos módulos:
--   * Desenhos Industriais
--   * Programas de Computador (Softwares)
--
-- Equivale à migration Alembic `f1a2b3c4d5e7_add_desenhos_software.py`.
--
-- COMO USAR (PostgreSQL)
--   psql -U postgres -d intelliinpi_app -f database/06_desenhos_softwares.sql
--
-- PRÉ-REQUISITOS
--   * O banco precisa já ter as tabelas `tenants` e `users` no schema public.
--   * `tenants.id` e `users.id` precisam ter PRIMARY KEY ou UNIQUE INDEX.
--     Sem isso, as FKs de `desenhos_monitoramento` e `softwares_monitoramento`
--     falham com SQLSTATE 42830:
--     "there is no unique constraint matching given keys for referenced table".
--
-- IMPORTANTE
--   Este script é idempotente para TABELAS/ÍNDICES já criados, mas NÃO altera
--   tabelas existentes que estejam com estrutura diferente.
--
--   Se o projeto usa Alembic, depois de rodar este script marque a migration
--   como aplicada para o `alembic upgrade head` não tentar recriar as tabelas:
--
--       cd backend
--       alembic stamp f1a2b3c4d5e7
--
--   A migration seguinte (a9b8c7d6e5f4 - marcas_rpi_imagens) continua normal.
--
--   Alternativa recomendada quando o Alembic está disponível:
--       alembic upgrade head
--   (não rode este script nesse caso).
-- =============================================================================

BEGIN;

SET search_path TO public;

-- =============================================================================
-- 1. DESENHOS INDUSTRIAIS
-- =============================================================================

-- DI_DADOS_BIBLIOGRAFICOS.csv
CREATE TABLE IF NOT EXISTS desenhos (
    codigo_interno      varchar(64) NOT NULL,
    numero_inpi         varchar(32),
    data_deposito       date,
    data_concessao      date,
    data_publicacao     date,
    data_vigencia       date,
    titulo              text,
    codigo_situacao     varchar(16),
    descricao_situacao  text,
    id                  uuid NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT desenhos_pkey PRIMARY KEY (id),
    CONSTRAINT uq_desenhos_codigo_interno UNIQUE (codigo_interno)
);

-- DI_CONTEUDO.csv
CREATE TABLE IF NOT EXISTS desenhos_conteudo (
    codigo_interno  varchar(64) NOT NULL,
    numero_inpi     varchar(32),
    titulo          text,
    campo_aplicacao text,
    descricao       text,
    id              uuid NOT NULL,
    CONSTRAINT desenhos_conteudo_pkey PRIMARY KEY (id)
);

-- DI_DEPOSITANTES.csv
CREATE TABLE IF NOT EXISTS desenhos_depositantes (
    codigo_interno  varchar(64) NOT NULL,
    numero_inpi     varchar(32),
    ordem           varchar(16),
    nome            text,
    cpf_cnpj        varchar(32),
    tipo_pessoa     varchar(32),
    pais            varchar(64),
    estado          varchar(64),
    id              uuid NOT NULL,
    CONSTRAINT desenhos_depositantes_pkey PRIMARY KEY (id)
);

-- DI_AUTORES.csv
CREATE TABLE IF NOT EXISTS desenhos_autores (
    codigo_interno  varchar(64) NOT NULL,
    numero_inpi     varchar(32),
    ordem           varchar(16),
    autor           text,
    pais            varchar(64),
    estado          varchar(64),
    id              uuid NOT NULL,
    CONSTRAINT desenhos_autores_pkey PRIMARY KEY (id)
);

-- DI_PROCURADORES.csv
CREATE TABLE IF NOT EXISTS desenhos_procuradores (
    codigo_interno  varchar(64) NOT NULL,
    numero_inpi     varchar(32),
    procurador      text,
    cpf_cnpj        varchar(32),
    tipo_pessoa     varchar(32),
    id              uuid NOT NULL,
    CONSTRAINT desenhos_procuradores_pkey PRIMARY KEY (id)
);

-- DI_CLASSIFICACOES.csv (Locarno)
CREATE TABLE IF NOT EXISTS desenhos_classificacoes (
    codigo_interno          varchar(64) NOT NULL,
    numero_inpi             varchar(32),
    ordem                   varchar(16),
    classificacao_locarno   varchar(32),
    descricao_locarno       text,
    id                      uuid NOT NULL,
    CONSTRAINT desenhos_classificacoes_pkey PRIMARY KEY (id)
);

-- DI_PRIORIDADES.csv
CREATE TABLE IF NOT EXISTS desenhos_prioridades (
    codigo_interno      varchar(64) NOT NULL,
    numero_inpi         varchar(32),
    pais_prioridade     varchar(64),
    numero_prioridade   varchar(64),
    data_prioridade     date,
    id                  uuid NOT NULL,
    CONSTRAINT desenhos_prioridades_pkey PRIMARY KEY (id)
);

-- DI_DESPACHOS.csv
CREATE TABLE IF NOT EXISTS desenhos_despachos (
    codigo_interno      varchar(64) NOT NULL,
    numero_inpi         varchar(32),
    numero_rpi          varchar(32),
    data_rpi            date,
    codigo_despacho     varchar(32),
    descricao_despacho  text,
    complemento_despacho text,
    id                  uuid NOT NULL,
    CONSTRAINT desenhos_despachos_pkey PRIMARY KEY (id)
);

-- DI_VINCULOS.csv
CREATE TABLE IF NOT EXISTS desenhos_vinculos (
    codigo_interno_derivado  varchar(64),
    numero_inpi_derivado     varchar(32),
    codigo_interno_origem    varchar(64),
    numero_inpi_origem       varchar(32),
    data_vinculo             date,
    tipo_vinculo             varchar(64),
    id                       uuid NOT NULL,
    CONSTRAINT desenhos_vinculos_pkey PRIMARY KEY (id)
);

-- DI_FIGURAS_* (somente metadados; o binário fica em disco/objeto storage)
CREATE TABLE IF NOT EXISTS desenhos_figuras (
    codigo_interno  varchar(64) NOT NULL,
    ordem           integer NOT NULL DEFAULT 1,
    arquivo         text,
    mime            varchar(64),
    bytes           bigint,
    sha256          varchar(64),
    status          varchar(16) NOT NULL DEFAULT 'PENDING',
    tentativas      integer NOT NULL DEFAULT 0,
    erro            text,
    baixado_em      timestamptz,
    id              uuid NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT desenhos_figuras_pkey PRIMARY KEY (id),
    CONSTRAINT uq_desenhos_figuras_codigo_interno UNIQUE (codigo_interno)
);

-- Monitoramento seletivo por usuário/tenant
CREATE TABLE IF NOT EXISTS desenhos_monitoramento (
    tenant_id       uuid NOT NULL,
    user_id         uuid NOT NULL,
    codigo_interno  varchar(64) NOT NULL,
    active          boolean NOT NULL DEFAULT true,
    notes           text,
    monitored_at    timestamptz NOT NULL DEFAULT now(),
    id              uuid NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz,
    CONSTRAINT desenhos_monitoramento_pkey PRIMARY KEY (id),
    CONSTRAINT uq_desenhos_monitoramento_tenant_codigo
        UNIQUE (tenant_id, codigo_interno),
    CONSTRAINT desenhos_monitoramento_tenant_id_fkey
        FOREIGN KEY (tenant_id) REFERENCES tenants (id) ON DELETE CASCADE,
    CONSTRAINT desenhos_monitoramento_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- =============================================================================
-- 2. PROGRAMAS DE COMPUTADOR (SOFTWARES)
-- =============================================================================

-- PROG_COMP_DADOS_BASICOS.csv
CREATE TABLE IF NOT EXISTS softwares (
    codigo_interno      varchar(64) NOT NULL,
    numero_inpi         varchar(32),
    data_deposito       date,
    data_concessao      date,
    data_publicacao     date,
    data_criacao        date,
    titulo              text,
    codigo_situacao     varchar(16),
    descricao_situacao  text,
    id                  uuid NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT softwares_pkey PRIMARY KEY (id),
    CONSTRAINT uq_softwares_codigo_interno UNIQUE (codigo_interno)
);

-- PROG_COMP_CAMPOS.csv
CREATE TABLE IF NOT EXISTS softwares_campos (
    codigo_interno  varchar(64) NOT NULL,
    numero_inpi     varchar(32),
    campo           text,
    valor           text,
    id              uuid NOT NULL,
    CONSTRAINT softwares_campos_pkey PRIMARY KEY (id)
);

-- PROG_COMP_TITULAR.csv
CREATE TABLE IF NOT EXISTS softwares_titulares (
    codigo_interno  varchar(64) NOT NULL,
    numero_inpi     varchar(32),
    ordem           varchar(16),
    nome            text,
    cpf_cnpj        varchar(32),
    tipo_pessoa     varchar(32),
    pais            varchar(64),
    estado          varchar(64),
    id              uuid NOT NULL,
    CONSTRAINT softwares_titulares_pkey PRIMARY KEY (id)
);

-- PROG_COMP_AUTORES.csv
CREATE TABLE IF NOT EXISTS softwares_autores (
    codigo_interno  varchar(64) NOT NULL,
    numero_inpi     varchar(32),
    ordem           varchar(16),
    autor           text,
    pais            varchar(64),
    estado          varchar(64),
    id              uuid NOT NULL,
    CONSTRAINT softwares_autores_pkey PRIMARY KEY (id)
);

-- PROG_COMP_LINGUAGEM.csv
CREATE TABLE IF NOT EXISTS softwares_linguagens (
    codigo_interno  varchar(64) NOT NULL,
    numero_inpi     varchar(32),
    linguagem       text,
    id              uuid NOT NULL,
    CONSTRAINT softwares_linguagens_pkey PRIMARY KEY (id)
);

-- PROG_COMP_TIPO.csv
CREATE TABLE IF NOT EXISTS softwares_tipos (
    codigo_interno  varchar(64) NOT NULL,
    numero_inpi     varchar(32),
    tipo            text,
    campo_aplicacao text,
    id              uuid NOT NULL,
    CONSTRAINT softwares_tipos_pkey PRIMARY KEY (id)
);

-- PROG_COMP_DESPACHOS.csv
CREATE TABLE IF NOT EXISTS softwares_despachos (
    codigo_interno      varchar(64) NOT NULL,
    numero_inpi         varchar(32),
    numero_rpi          varchar(32),
    data_rpi            date,
    codigo_despacho     varchar(32),
    descricao_despacho  text,
    complemento_despacho text,
    id                  uuid NOT NULL,
    CONSTRAINT softwares_despachos_pkey PRIMARY KEY (id)
);

-- Monitoramento seletivo por usuário/tenant
CREATE TABLE IF NOT EXISTS softwares_monitoramento (
    tenant_id       uuid NOT NULL,
    user_id         uuid NOT NULL,
    codigo_interno  varchar(64) NOT NULL,
    active          boolean NOT NULL DEFAULT true,
    notes           text,
    monitored_at    timestamptz NOT NULL DEFAULT now(),
    id              uuid NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz,
    CONSTRAINT softwares_monitoramento_pkey PRIMARY KEY (id),
    CONSTRAINT uq_softwares_monitoramento_tenant_codigo
        UNIQUE (tenant_id, codigo_interno),
    CONSTRAINT softwares_monitoramento_tenant_id_fkey
        FOREIGN KEY (tenant_id) REFERENCES tenants (id) ON DELETE CASCADE,
    CONSTRAINT softwares_monitoramento_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- =============================================================================
-- 3. ÍNDICES
-- =============================================================================

-- --- Desenhos industriais ----------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_desenhos_numero_inpi
    ON desenhos (numero_inpi);

CREATE INDEX IF NOT EXISTS ix_desenhos_data_deposito
    ON desenhos (data_deposito);

CREATE INDEX IF NOT EXISTS ix_desenhos_codigo_situacao
    ON desenhos (codigo_situacao);

CREATE INDEX IF NOT EXISTS ix_desenhos_conteudo_codigo_interno
    ON desenhos_conteudo (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_desenhos_dep_codigo_interno
    ON desenhos_depositantes (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_desenhos_dep_nome
    ON desenhos_depositantes (nome);

CREATE INDEX IF NOT EXISTS ix_desenhos_aut_codigo_interno
    ON desenhos_autores (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_desenhos_aut_autor
    ON desenhos_autores (autor);

CREATE INDEX IF NOT EXISTS ix_desenhos_proc_codigo_interno
    ON desenhos_procuradores (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_desenhos_class_codigo_interno
    ON desenhos_classificacoes (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_desenhos_class_locarno
    ON desenhos_classificacoes (classificacao_locarno);

CREATE INDEX IF NOT EXISTS ix_desenhos_prio_codigo_interno
    ON desenhos_prioridades (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_desenhos_desp_codigo_interno
    ON desenhos_despachos (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_desenhos_desp_codigo_despacho
    ON desenhos_despachos (codigo_despacho);

CREATE INDEX IF NOT EXISTS ix_desenhos_vinc_derivado
    ON desenhos_vinculos (codigo_interno_derivado);

CREATE INDEX IF NOT EXISTS ix_desenhos_vinc_origem
    ON desenhos_vinculos (codigo_interno_origem);

-- Redundante com a UNIQUE acima; mantido com o mesmo nome da migration.
CREATE INDEX IF NOT EXISTS ix_desenhos_fig_codigo_interno
    ON desenhos_figuras (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_desenhos_fig_status
    ON desenhos_figuras (status);

CREATE INDEX IF NOT EXISTS ix_desenhos_monitoramento_tenant
    ON desenhos_monitoramento (tenant_id);

CREATE INDEX IF NOT EXISTS ix_desenhos_monitoramento_codigo
    ON desenhos_monitoramento (codigo_interno);

-- --- Softwares ---------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_softwares_numero_inpi
    ON softwares (numero_inpi);

CREATE INDEX IF NOT EXISTS ix_softwares_data_deposito
    ON softwares (data_deposito);

CREATE INDEX IF NOT EXISTS ix_softwares_codigo_situacao
    ON softwares (codigo_situacao);

CREATE INDEX IF NOT EXISTS ix_softwares_campos_codigo_interno
    ON softwares_campos (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_softwares_tit_codigo_interno
    ON softwares_titulares (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_softwares_tit_nome
    ON softwares_titulares (nome);

CREATE INDEX IF NOT EXISTS ix_softwares_aut_codigo_interno
    ON softwares_autores (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_softwares_aut_autor
    ON softwares_autores (autor);

CREATE INDEX IF NOT EXISTS ix_softwares_ling_codigo_interno
    ON softwares_linguagens (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_softwares_tipo_codigo_interno
    ON softwares_tipos (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_softwares_desp_codigo_interno
    ON softwares_despachos (codigo_interno);

CREATE INDEX IF NOT EXISTS ix_softwares_desp_codigo_despacho
    ON softwares_despachos (codigo_despacho);

CREATE INDEX IF NOT EXISTS ix_softwares_monitoramento_tenant
    ON softwares_monitoramento (tenant_id);

CREATE INDEX IF NOT EXISTS ix_softwares_monitoramento_codigo
    ON softwares_monitoramento (codigo_interno);

-- =============================================================================
-- 4. OPCIONAL - BUSCA POR TÍTULO COM ILIKE '%...%'
-- =============================================================================
-- As telas pesquisam título com ILIKE. Para bases grandes, descomente o bloco
-- abaixo DEPOIS da carga inicial (a extensão pg_trgm já é criada pelo
-- database/01_extensions.sql):
--
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
--
-- CREATE INDEX IF NOT EXISTS ix_desenhos_titulo_trgm
--     ON desenhos USING gin (titulo gin_trgm_ops);
--
-- CREATE INDEX IF NOT EXISTS ix_softwares_titulo_trgm
--     ON softwares USING gin (titulo gin_trgm_ops);

COMMIT;
