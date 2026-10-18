"""Reconciliação idempotente dos índices do PostgreSQL (roda em todo deploy).

Contexto
--------
As tabelas do INPI (``marcas`` com ~6,6 milhões de linhas, ``patentes`` e as
tabelas de relacionamento) são carregadas em massa pelo pipeline de ingestão,
*fora* do Alembic. Nenhuma migration criava os índices de busca dessas tabelas:
um banco recriado — ou um restore — voltava a fazer ``Seq Scan`` e a busca por
nome levava ~76 s (``Parallel Seq Scan on marcas``).

Este módulo é o elo que faltava. Ele mantém o manifesto dos índices que
**devem** existir e, a cada execução, cria apenas o que estiver faltando. É
chamado no deploy, antes do ``app.seed`` (ver ``docker-compose.prod.yml``):

    alembic upgrade head && python -m app.db_indexes && python -m app.seed && uvicorn ...

Propriedades
------------
* **Idempotente**: rodar de novo não cria nada e não altera nada.
* **Comparação por definição**: um índice é considerado existente quando
  *qualquer* índice da tabela (mesmo com nome herdado/diferente) tem a mesma
  definição — evita duplicar índices equivalentes.
* **Nunca destrutivo**: não remove nem substitui índices. Um índice com o nome
  esperado mas definição diferente é apenas reportado como conflito.
* **Transações independentes**: cada ``CREATE INDEX`` é confirmado sozinho
  (``AUTOCOMMIT``). Se algo falhar, o que já foi criado permanece.
* **Uma execução por vez**: um *advisory lock* do PostgreSQL impede que dois
  containers/deploys reconciliem em paralelo (era a causa dos erros
  ``duplicate key value violates unique constraint "pg_class_relname_nsp_index"``).
* **Não trava o deploy**: ``lock_timeout`` curto faz um índice que não conseguiu
  o lock ser adiado para o próximo deploy, em vez de pendurar a subida da API.

Além dos índices de busca, o mesmo passo garante os **índices únicos** que o
código da ingestão exige para `INSERT ... ON CONFLICT` — ver
`REQUIRED_UNIQUE_INDEXES`. Sem eles a ingestão quebra na primeira gravação com
`InvalidColumnReference: there is no unique or exclusion constraint matching the
ON CONFLICT specification` (foi o que aconteceu em produção com `inpi_rpi`).

Uso
---
    python -m app.db_indexes                # reconcilia (usado no deploy)
    python -m app.db_indexes --dry-run      # só mostra o que seria criado
    python -m app.db_indexes --emit-sql     # imprime o DDL equivalente (psql)
    python -m app.db_indexes --timeout 600  # limite em segundos por índice

Variáveis de ambiente (todas opcionais)
---------------------------------------
    INDEX_SKIP=1                     desliga a reconciliação no deploy
    INDEX_BUILD_TIMEOUT_SECONDS=0    limite por índice (0 = sem limite)
    INDEX_MAINTENANCE_WORK_MEM=256MB memória de manutenção de cada build

Os arquivos ``database/02_indexes.sql`` e ``database/05_gerar_indexes_faltantes.sql``
continuam válidos para uso manual via ``psql``; este manifesto é a fonte usada
pelo deploy (``--emit-sql`` gera o equivalente em SQL).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import time
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db import engine
from app.logging_config import setup_logging

log = logging.getLogger("app.db_indexes")

# Chave do advisory lock (0x494E5049 == "INPI"): garante uma única execução.
_ADVISORY_LOCK_KEY = 0x494E5049

# Tempo máximo esperando por um lock alheio antes de desistir do índice.
_LOCK_TIMEOUT = "15s"

# Extensões/funções das quais os índices de expressão e trigram dependem.
# Não são criadas por nenhuma migration: fazem parte de database/01_extensions.sql.
_EXTENSIONS: tuple[str, ...] = ("pg_trgm", "unaccent", "uuid-ossp")

_IMMUTABLE_UNACCENT_SQL = """
CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
AS $$ SELECT public.unaccent('public.unaccent', $1) $$
"""

_FOLD_SQL = """
CREATE OR REPLACE FUNCTION public.fold(text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
AS $$ SELECT lower(public.immutable_unaccent($1)) $$
"""

# Remove o prefixo "CREATE [UNIQUE] INDEX <nome> ON " de um pg_get_indexdef.
_INDEXDEF_PREFIX = re.compile(r"^CREATE (UNIQUE )?INDEX \S+ ON ", re.IGNORECASE)

_TABLES_SQL = text(
    """
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r'
    """
)

_INDEXES_SQL = text(
    """
    SELECT tc.relname                        AS table_name,
           ic.relname                        AS index_name,
           pg_get_indexdef(i.indexrelid)     AS definition,
           (i.indisvalid AND i.indisready)   AS usable
    FROM pg_index i
    JOIN pg_class tc ON tc.oid = i.indrelid
    JOIN pg_class ic ON ic.oid = i.indexrelid
    JOIN pg_namespace n ON n.oid = tc.relnamespace
    WHERE n.nspname = 'public' AND tc.relkind = 'r'
    """
)

# Só os índices que podem servir de árbitro para `ON CONFLICT`: únicos e
# imediatos (`indimmediate = false` é o caso de uma constraint DEFERRABLE, que o
# PostgreSQL recusa como árbitro).
_UNIQUE_KEYS_SQL = text(
    """
    SELECT tc.relname                     AS table_name,
           ic.relname                     AS index_name,
           pg_get_indexdef(i.indexrelid)  AS definition
    FROM pg_index i
    JOIN pg_class tc ON tc.oid = i.indrelid
    JOIN pg_class ic ON ic.oid = i.indexrelid
    JOIN pg_namespace n ON n.oid = tc.relnamespace
    WHERE n.nspname = 'public' AND tc.relkind = 'r'
      AND i.indisvalid AND i.indisready AND i.indisunique AND i.indimmediate
    """
)


@dataclass(frozen=True)
class IndexSpec:
    """Um índice que deve existir no banco.

    ``by_name`` define como reconhecer um índice equivalente já existente:

    * ``False`` (tabelas do INPI, schema carregado em massa): compara tabela +
      colunas/expressão + opclass, **ignorando o nome**. Um índice equivalente
      com nome herdado não gera duplicata. Se o *nome* esperado existir com
      outra definição, isso é reportado como conflito.
    * ``True`` (tabelas do aplicativo, schema gerido pelo Alembic): basta o nome
      existir — o Alembic é a autoridade sobre a definição, então nunca criamos
      uma segunda cópia por causa de uma definição divergente.

    ``heavy`` marca os GIN trigram: construídos por último por serem os mais
    lentos em tabela cheia.
    """

    name: str
    table: str
    definition: str
    by_name: bool = False
    heavy: bool = False


def _idx(
    name: str,
    table: str,
    definition: str,
    *,
    by_name: bool = False,
    heavy: bool = False,
) -> IndexSpec:
    return IndexSpec(
        name=name, table=table, definition=definition, by_name=by_name, heavy=heavy
    )


# ---------------------------------------------------------------------------
# Manifesto — índices das tabelas de dados do INPI (comparados por definição)
# ---------------------------------------------------------------------------

INPI_INDEXES: tuple[IndexSpec, ...] = (
    # --- Fase 1: marcas (busca principal) ---------------------------------
    _idx(
        "ix_marcas_elemento_nominativo_fold",
        "marcas",
        "public.marcas USING btree (public.fold(elemento_nominativo))",
    ),
    _idx("ix_marcas_codigo_interno", "marcas", "public.marcas USING btree (codigo_interno)"),
    _idx("ix_marcas_numero_inpi", "marcas", "public.marcas USING btree (numero_inpi)"),
    _idx("ix_marcas_codigo_situacao", "marcas", "public.marcas USING btree (codigo_situacao)"),
    _idx(
        "ix_marcas_data_deposito",
        "marcas",
        "public.marcas USING btree (data_deposito DESC NULLS LAST)",
    ),
    _idx("ix_marcas_data_vigencia", "marcas", "public.marcas USING btree (data_vigencia)"),
    # --- Fase 2: marcas — tabelas de relacionamento -----------------------
    _idx(
        "ix_marcas_dep_codigo_interno",
        "marcas_depositantes",
        "public.marcas_depositantes USING btree (codigo_interno)",
    ),
    _idx("ix_marcas_dep_nome", "marcas_depositantes", "public.marcas_depositantes USING btree (nome)"),
    _idx(
        "ix_marcas_cn_codigo_interno",
        "marcas_classificacoes_nacionais",
        "public.marcas_classificacoes_nacionais USING btree (codigo_interno)",
    ),
    _idx(
        "ix_marcas_nice_codigo_interno",
        "marcas_classificacoes_nice",
        "public.marcas_classificacoes_nice USING btree (codigo_interno)",
    ),
    _idx(
        "ix_marcas_viena_codigo_interno",
        "marcas_classificacoes_viena",
        "public.marcas_classificacoes_viena USING btree (codigo_interno)",
    ),
    _idx(
        "ix_marcas_desp_codigo_interno",
        "marcas_despachos",
        "public.marcas_despachos USING btree (codigo_interno)",
    ),
    _idx(
        "ix_marcas_desp_codigo_despacho",
        "marcas_despachos",
        "public.marcas_despachos USING btree (codigo_despacho)",
    ),
    _idx(
        "ix_marcas_logos_codigo_interno",
        "marcas_logos",
        "public.marcas_logos USING btree (codigo_interno)",
    ),
    _idx("ix_marcas_logos_status", "marcas_logos", "public.marcas_logos USING btree (status)"),
    # --- Fase 3: patentes --------------------------------------------------
    _idx("ix_patentes_codigo_interno", "patentes", "public.patentes USING btree (codigo_interno)"),
    _idx("ix_patentes_numero_inpi", "patentes", "public.patentes USING btree (numero_inpi)"),
    _idx("ix_patentes_data_deposito", "patentes", "public.patentes USING btree (data_deposito)"),
    _idx(
        "ix_patentes_conteudo_codigo_interno",
        "patentes_conteudo",
        "public.patentes_conteudo USING btree (codigo_interno)",
    ),
    _idx(
        "ix_patentes_conteudo_numero_inpi",
        "patentes_conteudo",
        "public.patentes_conteudo USING btree (numero_inpi)",
    ),
    _idx(
        "ix_patentes_dep_codigo_interno",
        "patentes_depositantes",
        "public.patentes_depositantes USING btree (codigo_interno)",
    ),
    _idx(
        "ix_patentes_dep_depositante",
        "patentes_depositantes",
        "public.patentes_depositantes USING btree (depositante)",
    ),
    _idx(
        "ix_patentes_inv_codigo_interno",
        "patentes_inventores",
        "public.patentes_inventores USING btree (codigo_interno)",
    ),
    _idx("ix_patentes_inv_autor", "patentes_inventores", "public.patentes_inventores USING btree (autor)"),
    _idx(
        "ix_patentes_proc_codigo_interno",
        "patentes_procuradores",
        "public.patentes_procuradores USING btree (codigo_interno)",
    ),
    _idx(
        "ix_patentes_proc_procurador",
        "patentes_procuradores",
        "public.patentes_procuradores USING btree (procurador)",
    ),
    _idx(
        "ix_patentes_prio_codigo_interno",
        "patentes_prioridades",
        "public.patentes_prioridades USING btree (codigo_interno)",
    ),
    _idx(
        "ix_patentes_ipc_codigo_interno",
        "patentes_classificacao_ipc",
        "public.patentes_classificacao_ipc USING btree (codigo_interno)",
    ),
    _idx(
        "ix_patentes_ipc_simbolo",
        "patentes_classificacao_ipc",
        "public.patentes_classificacao_ipc USING btree (simbolo)",
    ),
    _idx(
        "ix_patentes_desp_codigo_interno",
        "patentes_despachos",
        "public.patentes_despachos USING btree (codigo_interno)",
    ),
    _idx(
        "ix_patentes_desp_codigo_despacho",
        "patentes_despachos",
        "public.patentes_despachos USING btree (codigo_despacho)",
    ),
    _idx(
        "ix_patentes_renum_codigo_interno",
        "patentes_renumeracoes",
        "public.patentes_renumeracoes USING btree (codigo_interno)",
    ),
    _idx(
        "ix_patentes_vinc_origem",
        "patentes_vinculos",
        "public.patentes_vinculos USING btree (codigo_interno_origem)",
    ),
    _idx(
        "ix_patentes_vinc_derivado",
        "patentes_vinculos",
        "public.patentes_vinculos USING btree (codigo_interno_derivado)",
    ),
    # --- Fase 4: monitoramento ---------------------------------------------
    _idx(
        "ix_marcas_monitoramento_tenant",
        "marcas_monitoramento",
        "public.marcas_monitoramento USING btree (tenant_id)",
    ),
    _idx(
        "ix_marcas_monitoramento_codigo",
        "marcas_monitoramento",
        "public.marcas_monitoramento USING btree (codigo_interno)",
    ),
    _idx(
        "ix_patentes_monitoramento_tenant",
        "patentes_monitoramento",
        "public.patentes_monitoramento USING btree (tenant_id)",
    ),
    _idx(
        "ix_patentes_monitoramento_codigo",
        "patentes_monitoramento",
        "public.patentes_monitoramento USING btree (codigo_interno)",
    ),
    # --- Fase 5: GIN trigram (pesados) -------------------------------------
    # Sem eles, "Contém" (ILIKE '%x%'), "Começa com" e a busca global varrem a
    # tabela inteira. A construção é longa em tabela cheia, por isso vêm por
    # último (ver `sorted(..., key=heavy)` em `ensure_indexes`).
    _idx(
        "ix_marcas_elemento_nominativo_trgm",
        "marcas",
        "public.marcas USING gin (elemento_nominativo gin_trgm_ops)",
        heavy=True,
    ),
    _idx(
        "ix_marcas_fold_trgm",
        "marcas",
        "public.marcas USING gin (public.fold(elemento_nominativo) gin_trgm_ops)",
        heavy=True,
    ),
    _idx(
        "ix_marcas_numero_inpi_trgm",
        "marcas",
        "public.marcas USING gin (numero_inpi gin_trgm_ops)",
        heavy=True,
    ),
    _idx(
        "ix_patentes_conteudo_titulo_trgm",
        "patentes_conteudo",
        "public.patentes_conteudo USING gin (titulo gin_trgm_ops)",
        heavy=True,
    ),
    _idx(
        "ix_patentes_conteudo_resumo_trgm",
        "patentes_conteudo",
        "public.patentes_conteudo USING gin (resumo gin_trgm_ops)",
        heavy=True,
    ),
    _idx(
        "ix_patentes_numero_inpi_trgm",
        "patentes",
        "public.patentes USING gin (numero_inpi gin_trgm_ops)",
        heavy=True,
    ),
    _idx(
        "ix_patentes_numero_pct_trgm",
        "patentes",
        "public.patentes USING gin (numero_pct gin_trgm_ops)",
        heavy=True,
    ),
)

# Tabelas grandes cujas estatísticas o planner precisa depois de um índice novo.
INPI_ANALYZE_TABLES: tuple[str, ...] = (
    "marcas",
    "marcas_depositantes",
    "marcas_classificacoes_nacionais",
    "marcas_classificacoes_nice",
    "marcas_classificacoes_viena",
    "marcas_despachos",
    "marcas_logos",
    "patentes",
    "patentes_conteudo",
    "patentes_depositantes",
    "patentes_inventores",
    "patentes_procuradores",
    "patentes_prioridades",
    "patentes_classificacao_ipc",
    "patentes_despachos",
    "patentes_renumeracoes",
    "patentes_vinculos",
)

# ---------------------------------------------------------------------------
# Manifesto — índices das tabelas do aplicativo (comparados por nome)
# ---------------------------------------------------------------------------
# Normalmente já existem: são criados por `alembic upgrade head`. Estão aqui
# como rede de segurança (um índice apagado à mão é recriado no próximo
# deploy). Comparados por NOME: o Alembic continua sendo a autoridade sobre a
# definição, então nunca criamos uma cópia divergente.

APP_INDEXES: tuple[IndexSpec, ...] = (
    # RBAC / núcleo
    _idx("ix_audit_logs_tenant_created", "audit_logs", "public.audit_logs USING btree (tenant_id, created_at)", by_name=True),
    _idx("ix_audit_logs_action", "audit_logs", "public.audit_logs USING btree (action)", by_name=True),
    _idx("ix_refresh_tokens_user", "refresh_tokens", "public.refresh_tokens USING btree (user_id)", by_name=True),
    _idx("ix_resources_module", "resources", "public.resources USING btree (module_id)", by_name=True),
    _idx("ix_role_policies_role", "role_policies", "public.role_policies USING btree (role_id)", by_name=True),
    _idx("ix_role_policies_user", "role_policies", "public.role_policies USING btree (user_id)", by_name=True),
    _idx("ix_user_policies_user", "user_policies", "public.user_policies USING btree (user_id)", by_name=True),
    _idx("ix_groups_tenant", "groups", "public.groups USING btree (tenant_id)", by_name=True),
    _idx("ix_group_policies_group", "group_policies", "public.group_policies USING btree (group_id)", by_name=True),
    _idx("ix_user_groups_user", "user_groups", "public.user_groups USING btree (user_id)", by_name=True),
    _idx("ix_user_groups_group", "user_groups", "public.user_groups USING btree (group_id)", by_name=True),
    _idx("ix_menu_items_menu", "menu_items", "public.menu_items USING btree (menu_id)", by_name=True),
    _idx("ix_user_tenants_user", "user_tenants", "public.user_tenants USING btree (user_id)", by_name=True),
    _idx("ix_user_company_unity_user", "user_company_unity", "public.user_company_unity USING btree (user_id)", by_name=True),
    _idx("ix_departments_tenant", "departments", "public.departments USING btree (tenant_id)", by_name=True),
    _idx("ix_people_tenant", "people", "public.people USING btree (tenant_id)", by_name=True),
    _idx("ix_people_name", "people", "public.people USING btree (name)", by_name=True),
    _idx("ix_companies_tenant", "companies", "public.companies USING btree (tenant_id)", by_name=True),
    _idx("ix_companies_company_name", "companies", "public.companies USING btree (company_name)", by_name=True),
    _idx("ix_unities_tenant", "unities", "public.unities USING btree (tenant_id)", by_name=True),
    _idx("ix_unities_company", "unities", "public.unities USING btree (company_id)", by_name=True),
    _idx("ix_customers_tenant", "customers", "public.customers USING btree (tenant_id)", by_name=True),
    _idx("ix_customers_company", "customers", "public.customers USING btree (company_id)", by_name=True),
    # CRM
    _idx("ix_crm_opportunities_tenant", "crm_opportunities", "public.crm_opportunities USING btree (tenant_id)", by_name=True),
    _idx("ix_crm_opportunities_stage", "crm_opportunities", "public.crm_opportunities USING btree (tenant_id, stage)", by_name=True),
    _idx("ix_crm_opportunities_customer", "crm_opportunities", "public.crm_opportunities USING btree (customer_id)", by_name=True),
    _idx("ix_crm_opportunities_owner", "crm_opportunities", "public.crm_opportunities USING btree (owner_id)", by_name=True),
    _idx("ix_crm_proposals_tenant", "crm_proposals", "public.crm_proposals USING btree (tenant_id)", by_name=True),
    _idx("ix_crm_proposals_status", "crm_proposals", "public.crm_proposals USING btree (tenant_id, status)", by_name=True),
    _idx("ix_crm_proposals_opportunity", "crm_proposals", "public.crm_proposals USING btree (opportunity_id)", by_name=True),
    _idx("ix_crm_proposals_customer", "crm_proposals", "public.crm_proposals USING btree (customer_id)", by_name=True),
    _idx("ix_crm_activities_tenant", "crm_activities", "public.crm_activities USING btree (tenant_id)", by_name=True),
    _idx("ix_crm_activities_subject", "crm_activities", "public.crm_activities USING btree (tenant_id, subject_type, subject_id)", by_name=True),
    _idx("ix_crm_activities_due", "crm_activities", "public.crm_activities USING btree (tenant_id, due_at)", by_name=True),
    _idx("ix_crm_activities_owner", "crm_activities", "public.crm_activities USING btree (owner_id)", by_name=True),
    # Ingestão INPI
    _idx("ix_inpi_dataset_category", "inpi_dataset", "public.inpi_dataset USING btree (category)", by_name=True),
    _idx("ix_inpi_dataset_status", "inpi_dataset", "public.inpi_dataset USING btree (status)", by_name=True),
    _idx("ix_inpi_import_dataset", "inpi_import", "public.inpi_import USING btree (dataset_id)", by_name=True),
    _idx("ix_inpi_import_error_import", "inpi_import_error", "public.inpi_import_error USING btree (import_id)", by_name=True),
    _idx("ix_inpi_rpi_status", "inpi_rpi", "public.inpi_rpi USING btree (status)", by_name=True),
    # Marcas — petições (documentos GRU) buscadas do pePI pelo worker de detalhe
    _idx("ix_marcas_peticoes_codigo_interno", "marcas_peticoes", "public.marcas_peticoes USING btree (codigo_interno)", by_name=True),
    _idx("ix_marcas_pepi_sync_status", "marcas_pepi_sync", "public.marcas_pepi_sync USING btree (status)", by_name=True),
    # NIT — portfólio / workflow
    _idx("ix_disclosures_tenant", "invention_disclosures", "public.invention_disclosures USING btree (tenant_id)", by_name=True),
    _idx("ix_disclosures_unity", "invention_disclosures", "public.invention_disclosures USING btree (unity_id)", by_name=True),
    _idx("ix_disclosures_status", "invention_disclosures", "public.invention_disclosures USING btree (status)", by_name=True),
    _idx("ix_disclosures_tenant_created", "invention_disclosures", "public.invention_disclosures USING btree (tenant_id, created_at)", by_name=True),
    _idx("ix_disclosure_inventors_disclosure", "disclosure_inventors", "public.disclosure_inventors USING btree (disclosure_id)", by_name=True),
    _idx("ix_disclosure_inventors_tenant", "disclosure_inventors", "public.disclosure_inventors USING btree (tenant_id)", by_name=True),
    _idx("ix_invention_documents_tenant", "invention_documents", "public.invention_documents USING btree (tenant_id)", by_name=True),
    _idx("ix_invention_documents_disclosure", "invention_documents", "public.invention_documents USING btree (disclosure_id)", by_name=True),
    _idx("ix_invention_documents_asset", "invention_documents", "public.invention_documents USING btree (asset_id)", by_name=True),
    _idx("ix_document_acls_document", "document_acls", "public.document_acls USING btree (document_id)", by_name=True),
    _idx("ix_document_acls_tenant", "document_acls", "public.document_acls USING btree (tenant_id)", by_name=True),
    _idx("ix_workflow_states_tenant", "workflow_states", "public.workflow_states USING btree (tenant_id)", by_name=True),
    _idx("ix_workflow_transitions_tenant", "workflow_transitions", "public.workflow_transitions USING btree (tenant_id)", by_name=True),
    _idx("ix_workflow_instances_tenant", "workflow_instances", "public.workflow_instances USING btree (tenant_id)", by_name=True),
    _idx("ix_workflow_history_instance", "workflow_history", "public.workflow_history USING btree (instance_id, created_at)", by_name=True),
    _idx("ix_workflow_history_tenant", "workflow_history", "public.workflow_history USING btree (tenant_id)", by_name=True),
    _idx("ix_workflow_history_disclosure", "workflow_history", "public.workflow_history USING btree (disclosure_id)", by_name=True),
    _idx("ix_evaluations_tenant", "evaluations", "public.evaluations USING btree (tenant_id)", by_name=True),
    _idx("ix_evaluations_disclosure", "evaluations", "public.evaluations USING btree (disclosure_id)", by_name=True),
    _idx("ix_evaluations_kind", "evaluations", "public.evaluations USING btree (kind)", by_name=True),
    _idx("ix_ip_assets_tenant", "ip_assets", "public.ip_assets USING btree (tenant_id)", by_name=True),
    _idx("ix_ip_assets_unity", "ip_assets", "public.ip_assets USING btree (unity_id)", by_name=True),
    _idx("ix_ip_assets_type", "ip_assets", "public.ip_assets USING btree (asset_type)", by_name=True),
    _idx("ix_ip_assets_status", "ip_assets", "public.ip_assets USING btree (status)", by_name=True),
    _idx("ix_ip_asset_public_links_asset", "ip_asset_public_links", "public.ip_asset_public_links USING btree (asset_id)", by_name=True),
    _idx("ix_ip_asset_public_links_tenant", "ip_asset_public_links", "public.ip_asset_public_links USING btree (tenant_id)", by_name=True),
    _idx("ix_ip_asset_public_links_ref", "ip_asset_public_links", "public.ip_asset_public_links USING btree (source, external_ref)", by_name=True),
    _idx("ix_trl_history_tenant", "trl_history", "public.trl_history USING btree (tenant_id)", by_name=True),
    _idx("ix_trl_history_disclosure", "trl_history", "public.trl_history USING btree (disclosure_id)", by_name=True),
    _idx("ix_trl_history_asset", "trl_history", "public.trl_history USING btree (asset_id)", by_name=True),
    # NIT — comitês
    _idx("ix_committees_tenant", "committees", "public.committees USING btree (tenant_id)", by_name=True),
    _idx("ix_committee_members_committee", "committee_members", "public.committee_members USING btree (committee_id)", by_name=True),
    _idx("ix_committee_members_user", "committee_members", "public.committee_members USING btree (user_id)", by_name=True),
    _idx("ix_committee_meetings_committee", "committee_meetings", "public.committee_meetings USING btree (committee_id)", by_name=True),
    _idx("ix_committee_meetings_tenant", "committee_meetings", "public.committee_meetings USING btree (tenant_id)", by_name=True),
    _idx("ix_committee_meetings_date", "committee_meetings", "public.committee_meetings USING btree (scheduled_at)", by_name=True),
    _idx("ix_committee_agenda_items_meeting", "committee_agenda_items", "public.committee_agenda_items USING btree (meeting_id)", by_name=True),
    _idx("ix_committee_agenda_items_disclosure", "committee_agenda_items", "public.committee_agenda_items USING btree (disclosure_id)", by_name=True),
    _idx("ix_committee_agenda_items_asset", "committee_agenda_items", "public.committee_agenda_items USING btree (asset_id)", by_name=True),
    _idx("ix_committee_votes_item", "committee_votes", "public.committee_votes USING btree (item_id)", by_name=True),
    _idx("ix_committee_votes_tenant", "committee_votes", "public.committee_votes USING btree (tenant_id)", by_name=True),
    _idx("ix_committee_decisions_tenant", "committee_decisions", "public.committee_decisions USING btree (tenant_id)", by_name=True),
    # NIT — transferência de tecnologia
    _idx("ix_technology_offers_tenant", "technology_offers", "public.technology_offers USING btree (tenant_id)", by_name=True),
    _idx("ix_technology_offers_status", "technology_offers", "public.technology_offers USING btree (status)", by_name=True),
    _idx("ix_interest_tenant", "expressions_of_interest", "public.expressions_of_interest USING btree (tenant_id)", by_name=True),
    _idx("ix_interest_offer", "expressions_of_interest", "public.expressions_of_interest USING btree (offer_id)", by_name=True),
    _idx("ix_interest_status", "expressions_of_interest", "public.expressions_of_interest USING btree (status)", by_name=True),
    _idx("ix_interest_interactions_interest", "interest_interactions", "public.interest_interactions USING btree (interest_id, created_at)", by_name=True),
    _idx("ix_interest_interactions_tenant", "interest_interactions", "public.interest_interactions USING btree (tenant_id)", by_name=True),
    _idx("ix_negotiations_tenant", "negotiations", "public.negotiations USING btree (tenant_id)", by_name=True),
    _idx("ix_negotiations_interest", "negotiations", "public.negotiations USING btree (interest_id)", by_name=True),
    _idx("ix_negotiations_stage", "negotiations", "public.negotiations USING btree (stage)", by_name=True),
    _idx("ix_negotiation_history_neg", "negotiation_history", "public.negotiation_history USING btree (negotiation_id, created_at)", by_name=True),
    _idx("ix_negotiation_history_tenant", "negotiation_history", "public.negotiation_history USING btree (tenant_id)", by_name=True),
    # NIT — contratos e licenças
    _idx("ix_licenses_tenant", "licenses", "public.licenses USING btree (tenant_id)", by_name=True),
    _idx("ix_licenses_asset", "licenses", "public.licenses USING btree (asset_id)", by_name=True),
    _idx("ix_contracts_tenant", "contracts", "public.contracts USING btree (tenant_id)", by_name=True),
    _idx("ix_contracts_license", "contracts", "public.contracts USING btree (license_id)", by_name=True),
    _idx("ix_contracts_status", "contracts", "public.contracts USING btree (status)", by_name=True),
    _idx("ix_contract_parties_contract", "contract_parties", "public.contract_parties USING btree (contract_id)", by_name=True),
    _idx("ix_contract_obligations_contract", "contract_obligations", "public.contract_obligations USING btree (contract_id)", by_name=True),
    _idx("ix_contract_obligations_due", "contract_obligations", "public.contract_obligations USING btree (due_date)", by_name=True),
    _idx("ix_royalties_contract", "royalties", "public.royalties USING btree (contract_id)", by_name=True),
    _idx("ix_royalties_period", "royalties", "public.royalties USING btree (period)", by_name=True),
    # NIT — projetos
    _idx("ix_projects_tenant", "projects", "public.projects USING btree (tenant_id)", by_name=True),
    _idx("ix_projects_status", "projects", "public.projects USING btree (status)", by_name=True),
    _idx("ix_projects_unity", "projects", "public.projects USING btree (unity_id)", by_name=True),
    _idx("ix_project_members_project", "project_members", "public.project_members USING btree (project_id)", by_name=True),
    _idx("ix_project_funders_project", "project_funders", "public.project_funders USING btree (project_id)", by_name=True),
    _idx("ix_project_milestones_project", "project_milestones", "public.project_milestones USING btree (project_id)", by_name=True),
    _idx("ix_project_milestones_due", "project_milestones", "public.project_milestones USING btree (due_date)", by_name=True),
    _idx("ix_project_asset_links_project", "project_asset_links", "public.project_asset_links USING btree (project_id)", by_name=True),
    _idx("ix_project_asset_links_asset", "project_asset_links", "public.project_asset_links USING btree (asset_id)", by_name=True),
    # NIT — startups e incubação
    _idx("ix_startups_tenant", "startups", "public.startups USING btree (tenant_id)", by_name=True),
    _idx("ix_startups_status", "startups", "public.startups USING btree (status)", by_name=True),
    _idx("ix_startup_members_startup", "startup_members", "public.startup_members USING btree (startup_id)", by_name=True),
    _idx("ix_incubation_programs_tenant", "incubation_programs", "public.incubation_programs USING btree (tenant_id)", by_name=True),
    _idx("ix_incubation_participations_program", "incubation_participations", "public.incubation_participations USING btree (program_id)", by_name=True),
    _idx("ix_incubation_participations_startup", "incubation_participations", "public.incubation_participations USING btree (startup_id)", by_name=True),
    _idx("ix_incubation_stages_participation", "incubation_stages", "public.incubation_stages USING btree (participation_id)", by_name=True),
    # NIT — notificações
    _idx("ix_nit_notifications_user", "nit_notifications", "public.nit_notifications USING btree (user_id)", by_name=True),
    _idx("ix_nit_notifications_tenant", "nit_notifications", "public.nit_notifications USING btree (tenant_id)", by_name=True),
    _idx("ix_nit_notifications_unread", "nit_notifications", "public.nit_notifications USING btree (user_id, read_at)", by_name=True),
    _idx("ix_nit_notif_pref_user", "nit_notification_preferences", "public.nit_notification_preferences USING btree (user_id)", by_name=True),
    _idx("ix_nit_email_status", "nit_email_messages", "public.nit_email_messages USING btree (status)", by_name=True),
    _idx("ix_nit_email_tenant", "nit_email_messages", "public.nit_email_messages USING btree (tenant_id)", by_name=True),
    # NIT — portal e relatórios
    _idx("ix_nit_portal_access_tenant", "nit_portal_access", "public.nit_portal_access USING btree (tenant_id)", by_name=True),
    _idx("ix_nit_portal_access_status", "nit_portal_access", "public.nit_portal_access USING btree (status)", by_name=True),
    _idx("ix_nit_portal_requests_access", "nit_portal_requests", "public.nit_portal_requests USING btree (access_id)", by_name=True),
    _idx("ix_nit_portal_requests_tenant", "nit_portal_requests", "public.nit_portal_requests USING btree (tenant_id)", by_name=True),
    _idx("ix_nit_portal_requests_status", "nit_portal_requests", "public.nit_portal_requests USING btree (status)", by_name=True),
    _idx("ix_nit_portal_notes_request", "nit_portal_request_notes", "public.nit_portal_request_notes USING btree (request_id)", by_name=True),
    _idx("ix_nit_saved_reports_tenant", "nit_saved_reports", "public.nit_saved_reports USING btree (tenant_id)", by_name=True),
    _idx("ix_nit_report_runs_report", "nit_report_runs", "public.nit_report_runs USING btree (report_id)", by_name=True),
    _idx("ix_nit_report_runs_tenant", "nit_report_runs", "public.nit_report_runs USING btree (tenant_id)", by_name=True),
    # NIT — integrações
    _idx("ix_nit_integration_tenant", "nit_integration_endpoints", "public.nit_integration_endpoints USING btree (tenant_id)", by_name=True),
    _idx("ix_nit_integration_kind", "nit_integration_endpoints", "public.nit_integration_endpoints USING btree (kind)", by_name=True),
    _idx("ix_nit_integration_deliveries_endpoint", "nit_integration_deliveries", "public.nit_integration_deliveries USING btree (endpoint_id)", by_name=True),
    _idx("ix_nit_integration_deliveries_status", "nit_integration_deliveries", "public.nit_integration_deliveries USING btree (status)", by_name=True),
)

ALL_INDEXES: tuple[IndexSpec, ...] = INPI_INDEXES + APP_INDEXES


# ---------------------------------------------------------------------------
# Índices ÚNICOS exigidos pelo código (`INSERT ... ON CONFLICT`)
# ---------------------------------------------------------------------------
#
# As tabelas do aplicativo são geridas pelo Alembic, que já declara estas
# constraints desde as respectivas migrations. Mas um banco que veio de um dump
# antigo pode estar sem elas — e aí a ingestão falha na primeira gravação, mesmo
# com o schema "funcionando" para leitura:
#
#     psycopg.errors.InvalidColumnReference: there is no unique or exclusion
#     constraint matching the ON CONFLICT specification
#
# (aconteceu em produção: `inpi_rpi.number` existia no Alembic mas não no banco).
# O passo abaixo conserta isso sozinho, em todo deploy, do mesmo jeito que faz
# com os índices de busca. Criamos um índice ÚNICO (não uma constraint): serve
# igual como árbitro do `ON CONFLICT` e é idempotente via `IF NOT EXISTS`.
#
# Formato: (nome, tabela, colunas).
REQUIRED_UNIQUE_INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # Schema inicial (612d99e9df03) — as que faltavam em produção.
    ("uq_inpi_dataset_name", "inpi_dataset", ("name",)),
    ("uq_inpi_checkpoint", "inpi_import_checkpoint", ("dataset_id", "target_table")),
    ("uq_inpi_rpi_number", "inpi_rpi", ("number",)),
    # Migrations seguintes (self-heal também, para o caso de um restore antigo).
    ("uq_marcas_logos_codigo_interno", "marcas_logos", ("codigo_interno",)),
    (
        "uq_marcas_peticoes_codigo_protocolo",
        "marcas_peticoes",
        ("codigo_interno", "protocolo"),
    ),
    ("uq_marcas_pepi_sync_codigo_interno", "marcas_pepi_sync", ("codigo_interno",)),
)


def _unique_specs() -> tuple[IndexSpec, ...]:
    """`REQUIRED_UNIQUE_INDEXES` como `IndexSpec` (comparados por definição)."""
    return tuple(
        IndexSpec(
            name=name,
            table=table,
            definition=f"public.{table} USING btree ({', '.join(columns)})",
        )
        for name, table, columns in REQUIRED_UNIQUE_INDEXES
    )


@dataclass
class Summary:
    """Resultado de uma reconciliação (também usado pelos testes)."""

    created: list[str] = field(default_factory=list)
    existing: int = 0
    conflicts: list[str] = field(default_factory=list)
    missing_tables: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    seconds: float = 0.0
    # True quando outra execução já estava reconciliando (advisory lock).
    skipped: bool = False


# ---------------------------------------------------------------------------
# Normalização e comparação
# ---------------------------------------------------------------------------


def normalise(definition: str) -> str:
    """Chave de comparação de um índice (independente do nome e do schema).

    ``CREATE [UNIQUE] INDEX <nome> ON public.marcas USING btree (x)`` vira
    ``marcas USING btree (x)`` — exatamente como
    ``database/05_gerar_indexes_faltantes.sql`` compara.
    """
    value = _INDEXDEF_PREFIX.sub("", definition.strip())
    value = re.sub(r"\s+", " ", value).strip()
    return value.replace("public.", "")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _check_manifest() -> None:
    """Falha cedo (e claro) se o manifesto tiver nomes repetidos."""
    seen: set[str] = set()
    duplicated: set[str] = set()
    for spec in ALL_INDEXES:
        if spec.name in seen:
            duplicated.add(spec.name)
        seen.add(spec.name)
    if duplicated:
        raise RuntimeError(
            "manifesto de índices com nomes duplicados: " + ", ".join(sorted(duplicated))
        )


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning("valor inválido em %s (%r); usando %s", name, raw, default)
        return default


def _apply_session_settings(
    conn: Connection, timeout_seconds: int, maintenance_work_mem: str
) -> None:
    """Configura a sessão só para os builds (não afeta a API).

    ``lock_timeout`` curto: um índice que não conseguir o lock é adiado para o
    próximo deploy em vez de segurar a subida da API.
    """
    for statement in (
        f"SET lock_timeout = '{_LOCK_TIMEOUT}'",
        f"SET statement_timeout = {max(0, int(timeout_seconds)) * 1000}",
        f"SET maintenance_work_mem = '{maintenance_work_mem}'",
        "SET max_parallel_maintenance_workers = 2",
    ):
        conn.execute(text(statement))


def _ensure_foundation(conn: Connection) -> None:
    """Garante extensões e as funções de *fold* usadas nos índices de expressão.

    Nenhuma migration cria isso (vive em ``database/01_extensions.sql``): sem
    elas um banco novo não tem ``pg_trgm`` nem ``public.fold``, e a busca
    quebraria. As funções só são criadas se faltarem — nunca sobrescrevemos as
    que já existem em produção.
    """
    for extension in _EXTENSIONS:
        try:
            conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{extension}"'))
        except Exception as exc:  # noqa: BLE001 - permissão/indisponibilidade
            log.warning(
                "não foi possível garantir a extensão %s: %s", extension, exc
            )

    for signature, statement in (
        ("public.immutable_unaccent(text)", _IMMUTABLE_UNACCENT_SQL),
        ("public.fold(text)", _FOLD_SQL),
    ):
        exists = conn.execute(
            text("SELECT to_regprocedure(:sig)"), {"sig": signature}
        ).scalar()
        if exists is None:
            try:
                conn.execute(text(statement))
                log.info("função %s criada", signature)
            except Exception as exc:  # noqa: BLE001
                log.error("não foi possível criar a função %s: %s", signature, exc)


def _reconcile(conn: Connection, summary: Summary, *, dry_run: bool) -> None:
    tables = {row[0] for row in conn.execute(_TABLES_SQL)}

    by_definition: dict[tuple[str, str], str] = {}
    by_name: dict[str, tuple[str, bool]] = {}
    for table, index_name, definition, usable in conn.execute(_INDEXES_SQL):
        by_name.setdefault(index_name, (definition, bool(usable)))
        if usable:
            by_definition.setdefault((table, normalise(definition)), index_name)

    touched: set[str] = set()

    # Pesados (GIN trigram) por último; a ordenação é estável, então a ordem do
    # manifesto é preservada dentro de cada grupo.
    for spec in sorted(ALL_INDEXES, key=lambda item: item.heavy):
        if spec.table not in tables:
            summary.missing_tables.append(spec.name)
            log.warning(
                "tabela ausente; índice ignorado",
                extra={"context": {"index": spec.name, "table": spec.table}},
            )
            continue

        if (spec.table, normalise(spec.definition)) in by_definition:
            summary.existing += 1
            continue

        if spec.name in by_name:
            if spec.by_name:
                # Tabela do aplicativo: o Alembic manda na definição.
                summary.existing += 1
            else:
                summary.conflicts.append(spec.name)
                log.warning(
                    "já existe um índice com este nome e definição diferente; "
                    "nada foi criado (remova-o à mão se quiser o índice novo) — %s",
                    by_name[spec.name][0],
                    extra={"context": {"index": spec.name, "table": spec.table}},
                )
            continue

        statement = (
            f"CREATE INDEX IF NOT EXISTS {_quote_ident(spec.name)} ON {spec.definition}"
        )
        if dry_run:
            print(statement + ";")
            summary.created.append(spec.name)
            continue

        if spec.heavy:
            log.warning(
                "construindo índice pesado (GIN trigram); pode demorar em tabela cheia",
                extra={"context": {"index": spec.name, "table": spec.table}},
            )

        started = time.monotonic()
        try:
            conn.execute(text(statement))
        except Exception as exc:  # noqa: BLE001 - um índice não pode derrubar o deploy
            summary.errors.append(spec.name)
            message = str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)
            hint = ""
            if "statement timeout" in message:
                hint = (
                    " — excedeu INDEX_BUILD_TIMEOUT_SECONDS; rode"
                    " `python -m app.db_indexes --timeout 0` para construí-lo sem limite"
                )
            elif "lock timeout" in message or "canceling statement due to lock" in message:
                hint = f" — não obteve o lock em {_LOCK_TIMEOUT}; tentará de novo no próximo deploy"
            log.error(
                "falha ao criar índice: %s%s",
                message,
                hint,
                extra={"context": {"index": spec.name, "table": spec.table}},
            )
            continue

        elapsed = time.monotonic() - started
        summary.created.append(spec.name)
        touched.add(spec.table)
        log.info(
            "índice criado em %.1fs",
            elapsed,
            extra={
                "context": {
                    "index": spec.name,
                    "table": spec.table,
                    "seconds": round(elapsed, 1),
                    "heavy": spec.heavy,
                }
            },
        )

    if dry_run:
        return

    # Sem estatísticas novas o planner continua escolhendo Seq Scan.
    for table in INPI_ANALYZE_TABLES:
        if table not in touched:
            continue
        try:
            conn.execute(text(f"ANALYZE {_quote_ident(table)}"))
            log.info("ANALYZE executado", extra={"context": {"table": table}})
        except Exception as exc:  # noqa: BLE001
            log.error("falha no ANALYZE de %s: %s", table, exc)


def _reconcile_unique(
    conn: Connection, summary: Summary, *, dry_run: bool
) -> None:
    """Garante os índices únicos exigidos por ``INSERT ... ON CONFLICT``.

    É o mesmo raciocínio dos índices de busca, aplicado às *constraints*: o
    schema do banco pode ter divergido do Alembic (restore/dump antigo) e o
    código passa a falhar em toda gravação. Aqui só criamos o que falta; nunca
    removemos nada.
    """
    tables = {row[0] for row in conn.execute(_TABLES_SQL)}

    # Definido por colunas/expressão: um índice único equivalente com outro nome
    # já serve de árbitro, então não criamos uma segunda cópia.
    unique_keys: set[tuple[str, str]] = set()
    for table, _index_name, definition in conn.execute(_UNIQUE_KEYS_SQL):
        unique_keys.add((table, normalise(definition)))

    # Todos os índices (mesmo os que não servem): para detectar o nome já ocupado.
    taken_names: dict[str, str] = {}
    for _table, index_name, definition, _usable in conn.execute(_INDEXES_SQL):
        taken_names.setdefault(index_name, definition)

    for spec in _unique_specs():
        if spec.table not in tables:
            summary.missing_tables.append(spec.name)
            log.warning(
                "tabela ausente; índice único ignorado",
                extra={"context": {"index": spec.name, "table": spec.table}},
            )
            continue

        if (spec.table, normalise(spec.definition)) in unique_keys:
            summary.existing += 1
            continue

        if spec.name in taken_names:
            # Existe com este nome, mas não é único+imediato: não dá para usar em
            # ON CONFLICT e recriar com o mesmo nome é impossível sem removê-lo.
            summary.conflicts.append(spec.name)
            log.warning(
                "já existe um índice com este nome que NÃO serve de árbitro para "
                "ON CONFLICT (precisa ser único e imediato); nada foi criado — %s",
                taken_names[spec.name],
                extra={"context": {"index": spec.name, "table": spec.table}},
            )
            continue

        statement = (
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            f"{_quote_ident(spec.name)} ON {spec.definition}"
        )
        if dry_run:
            print(statement + ";")
            summary.created.append(spec.name)
            continue

        try:
            conn.execute(text(statement))
        except Exception as exc:  # noqa: BLE001 - não pode derrubar o deploy
            summary.errors.append(spec.name)
            message = str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)
            hint = ""
            if "duplicate key" in message or "could not create unique index" in message:
                hint = (
                    " — há valores duplicados na(s) coluna(s); remova as duplicatas"
                    " e rode de novo"
                )
            log.error(
                "falha ao criar índice único: %s%s",
                message,
                hint,
                extra={"context": {"index": spec.name, "table": spec.table}},
            )
            continue

        summary.created.append(spec.name)
        log.info(
            "índice único criado (faltava no banco)",
            extra={"context": {"index": spec.name, "table": spec.table}},
        )


def ensure_indexes(
    *,
    dry_run: bool = False,
    timeout_seconds: int = 0,
    maintenance_work_mem: str = "256MB",
) -> Summary:
    """Cria os índices que faltam. Devolve o resumo da execução."""
    _check_manifest()
    summary = Summary()
    started = time.monotonic()

    # AUTOCOMMIT: cada CREATE INDEX confirma sozinho (o progresso nunca se perde).
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        locked = conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": _ADVISORY_LOCK_KEY}
        ).scalar()
        if not locked:
            log.warning(
                "outra execução da reconciliação de índices já está em andamento; "
                "nada a fazer"
            )
            summary.skipped = True
            return summary

        try:
            _apply_session_settings(conn, timeout_seconds, maintenance_work_mem)
            _ensure_foundation(conn)
            _reconcile(conn, summary, dry_run=dry_run)
            try:
                _reconcile_unique(conn, summary, dry_run=dry_run)
            except Exception as exc:  # noqa: BLE001 - o deploy não pode parar
                log.error("reconciliação dos índices únicos falhou: %s", exc)
        finally:
            conn.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": _ADVISORY_LOCK_KEY}
            )
    finally:
        conn.close()

    summary.seconds = round(time.monotonic() - started, 1)
    return summary


def _emit_sql(timeout_seconds: int = 0, maintenance_work_mem: str = "256MB") -> str:
    """DDL equivalente, para rodar à mão via ``psql`` (sem o app no meio)."""
    lines = [
        "-- Gerado por `python -m app.db_indexes --emit-sql`",
        "-- Equivalente ao passo de deploy; seguro rodar mais de uma vez.",
        "",
        f"SET lock_timeout = '{_LOCK_TIMEOUT}';",
        f"SET statement_timeout = {max(0, int(timeout_seconds)) * 1000};",
        f"SET maintenance_work_mem = '{maintenance_work_mem}';",
        "SET max_parallel_maintenance_workers = 2;",
        "",
    ]
    for spec in sorted(ALL_INDEXES, key=lambda item: item.heavy):
        lines.append(
            f"CREATE INDEX IF NOT EXISTS {_quote_ident(spec.name)} ON {spec.definition};"
        )
    lines.append("")
    lines.append("-- Índices únicos exigidos por ON CONFLICT (self-heal).")
    for spec in _unique_specs():
        lines.append(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {_quote_ident(spec.name)}"
            f" ON {spec.definition};"
        )
    lines.append("")
    lines.extend(f"ANALYZE {_quote_ident(table)};" for table in INPI_ANALYZE_TABLES)
    lines.append("")
    return "\n".join(lines)


def _log_summary(summary: Summary) -> None:
    log.info(
        "reconciliação de índices concluída em %.1fs: %d criado(s), %d já "
        "existia(m), %d conflito(s), %d tabela(s) ausente(s), %d erro(s)",
        summary.seconds,
        len(summary.created),
        summary.existing,
        len(summary.conflicts),
        len(summary.missing_tables),
        len(summary.errors),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.db_indexes",
        description="Cria no banco os índices que faltam (idempotente).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="imprime o DDL do que seria criado, sem alterar o banco",
    )
    parser.add_argument(
        "--emit-sql",
        action="store_true",
        help="imprime o DDL equivalente (para usar com psql) e sai",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="limite em segundos por índice (0 = sem limite)",
    )
    args = parser.parse_args(argv)

    setup_logging(os.getenv("LOG_LEVEL", "INFO"))

    if _env_flag("INDEX_SKIP"):
        log.warning(
            "INDEX_SKIP definido: reconciliação de índices ignorada neste deploy"
        )
        return 0

    timeout_seconds = (
        args.timeout
        if args.timeout is not None
        else _env_int("INDEX_BUILD_TIMEOUT_SECONDS", 0)
    )
    maintenance_work_mem = (
        os.getenv("INDEX_MAINTENANCE_WORK_MEM", "256MB").strip() or "256MB"
    )

    if args.emit_sql:
        print(_emit_sql(timeout_seconds, maintenance_work_mem))
        return 0

    log.info(
        "reconciliando índices (%d no manifesto, %d índices únicos exigidos, "
        "timeout por índice: %s)",
        len(ALL_INDEXES),
        len(REQUIRED_UNIQUE_INDEXES),
        timeout_seconds if timeout_seconds > 0 else "sem limite",
    )
    try:
        summary = ensure_indexes(
            dry_run=args.dry_run,
            timeout_seconds=timeout_seconds,
            maintenance_work_mem=maintenance_work_mem,
        )
    except Exception as exc:  # noqa: BLE001 - o deploy não pode parar por causa disso
        log.error("reconciliação de índices falhou: %s", exc, exc_info=True)
        return 1

    if not summary.skipped:
        _log_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
