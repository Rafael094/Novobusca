-- =============================================================================
-- IntelliINPI - 05_gerar_indexes_faltantes.sql
--
-- ATENÇÃO (desde a revisão de índices): para o deploy este script foi
-- substituído por `python -m app.db_indexes`, que roda a cada subida da API
-- (ver docker-compose.prod.yml) e faz exatamente esta comparação por DEFINIÇÃO,
-- criando só o que falta. A fonte canônica do manifesto é
-- `backend/app/db_indexes.py`; `python -m app.db_indexes --emit-sql` gera o SQL
-- equivalente. Este arquivo continua útil para inspecionar/gerar o DDL à mão.
--
-- SOMENTE LEITURA no banco. Lê o catálogo do PostgreSQL e IMPRIME o DDL
-- (CREATE INDEX ...) de todo índice que deveria existir e não existe.
--
-- A comparação é feita por DEFINIÇÃO (tabela + colunas/expressão + opclass) e
-- NÃO por nome. Assim:
--   * nunca cria um índice duplicado só porque o existente tem outro nome;
--   * reconhece índices já criados como equivalentes e apenas os reporta.
--
-- COMO USAR (na VM)
--   # 1) gera o script do que falta (o output é um .sql executável)
--   docker cp database/05_gerar_indexes_faltantes.sql inpi-postgres:/tmp/
--   docker exec inpi-postgres psql -U postgres -d intelliinpi_app -At \
--       -f /tmp/05_gerar_indexes_faltantes.sql > /tmp/faltantes.sql
--
--   # 2) revise o que foi gerado
--   less /tmp/faltantes.sql
--
--   # 3) rode em segundo plano (não depende do SSH/console aberto)
--   docker cp /tmp/faltantes.sql inpi-postgres:/tmp/faltantes.sql
--   docker exec -d inpi-postgres sh -c \
--     'psql -U postgres -d intelliinpi_app -f /tmp/faltantes.sql > /tmp/faltantes.log 2>&1'
--   docker exec -it inpi-postgres tail -f /tmp/faltantes.log
--
-- OBS.: o script gerado já vem com os SETs de sessão e com os ANALYZE no lugar
--       certo, e coloca os índices GIN trigram (pesados) por último.
-- =============================================================================

WITH esperado(ordem, nome, tabela, definicao) AS (
    VALUES
    -- ===================== FASE 1: MARCAS (busca) ==========================
    (10,'ix_marcas_elemento_nominativo_fold','marcas',   'public.marcas USING btree (public.fold(elemento_nominativo))'),
    (10,'ix_marcas_codigo_interno',           'marcas',   'public.marcas USING btree (codigo_interno)'),
    (10,'ix_marcas_numero_inpi',              'marcas',   'public.marcas USING btree (numero_inpi)'),
    (10,'ix_marcas_codigo_situacao',          'marcas',   'public.marcas USING btree (codigo_situacao)'),
    (10,'ix_marcas_data_deposito',            'marcas',   'public.marcas USING btree (data_deposito DESC NULLS LAST)'),
    (10,'ix_marcas_data_vigencia',            'marcas',   'public.marcas USING btree (data_vigencia)'),

    -- ===================== FASE 2: MARCAS - relacoes =======================
    (20,'ix_marcas_dep_codigo_interno',       'marcas_depositantes',              'public.marcas_depositantes USING btree (codigo_interno)'),
    (20,'ix_marcas_dep_nome',                 'marcas_depositantes',              'public.marcas_depositantes USING btree (nome)'),
    (20,'ix_marcas_cn_codigo_interno',        'marcas_classificacoes_nacionais',  'public.marcas_classificacoes_nacionais USING btree (codigo_interno)'),
    (20,'ix_marcas_nice_codigo_interno',      'marcas_classificacoes_nice',       'public.marcas_classificacoes_nice USING btree (codigo_interno)'),
    (20,'ix_marcas_viena_codigo_interno',     'marcas_classificacoes_viena',      'public.marcas_classificacoes_viena USING btree (codigo_interno)'),
    (20,'ix_marcas_desp_codigo_interno',      'marcas_despachos',                 'public.marcas_despachos USING btree (codigo_interno)'),
    (20,'ix_marcas_desp_codigo_despacho',     'marcas_despachos',                 'public.marcas_despachos USING btree (codigo_despacho)'),
    (20,'ix_marcas_logos_codigo_interno',     'marcas_logos',                     'public.marcas_logos USING btree (codigo_interno)'),
    (20,'ix_marcas_logos_status',             'marcas_logos',                     'public.marcas_logos USING btree (status)'),

    -- ===================== FASE 3: PATENTES ================================
    (30,'ix_patentes_codigo_interno',         'patentes', 'public.patentes USING btree (codigo_interno)'),
    (30,'ix_patentes_numero_inpi',            'patentes', 'public.patentes USING btree (numero_inpi)'),
    (30,'ix_patentes_data_deposito',          'patentes', 'public.patentes USING btree (data_deposito)'),
    (35,'ix_patentes_conteudo_codigo_interno','patentes_conteudo',      'public.patentes_conteudo USING btree (codigo_interno)'),
    (35,'ix_patentes_conteudo_numero_inpi',   'patentes_conteudo',      'public.patentes_conteudo USING btree (numero_inpi)'),
    (35,'ix_patentes_dep_codigo_interno',     'patentes_depositantes',  'public.patentes_depositantes USING btree (codigo_interno)'),
    (35,'ix_patentes_dep_depositante',        'patentes_depositantes',  'public.patentes_depositantes USING btree (depositante)'),
    (35,'ix_patentes_inv_codigo_interno',     'patentes_inventores',    'public.patentes_inventores USING btree (codigo_interno)'),
    (35,'ix_patentes_inv_autor',              'patentes_inventores',    'public.patentes_inventores USING btree (autor)'),
    (35,'ix_patentes_proc_codigo_interno',    'patentes_procuradores',  'public.patentes_procuradores USING btree (codigo_interno)'),
    (35,'ix_patentes_proc_procurador',        'patentes_procuradores',  'public.patentes_procuradores USING btree (procurador)'),
    (35,'ix_patentes_prio_codigo_interno',    'patentes_prioridades',   'public.patentes_prioridades USING btree (codigo_interno)'),
    (35,'ix_patentes_ipc_codigo_interno',     'patentes_classificacao_ipc','public.patentes_classificacao_ipc USING btree (codigo_interno)'),
    (35,'ix_patentes_ipc_simbolo',            'patentes_classificacao_ipc','public.patentes_classificacao_ipc USING btree (simbolo)'),
    (35,'ix_patentes_desp_codigo_interno',    'patentes_despachos',     'public.patentes_despachos USING btree (codigo_interno)'),
    (35,'ix_patentes_desp_codigo_despacho',   'patentes_despachos',     'public.patentes_despachos USING btree (codigo_despacho)'),
    (35,'ix_patentes_renum_codigo_interno',   'patentes_renumeracoes',  'public.patentes_renumeracoes USING btree (codigo_interno)'),
    (35,'ix_patentes_vinc_origem',            'patentes_vinculos',      'public.patentes_vinculos USING btree (codigo_interno_origem)'),
    (35,'ix_patentes_vinc_derivado',          'patentes_vinculos',      'public.patentes_vinculos USING btree (codigo_interno_derivado)'),

    -- ===================== FASE 4: MONITORAMENTO ===========================
    (40,'ix_marcas_monitoramento_tenant',     'marcas_monitoramento',   'public.marcas_monitoramento USING btree (tenant_id)'),
    (40,'ix_marcas_monitoramento_codigo',     'marcas_monitoramento',   'public.marcas_monitoramento USING btree (codigo_interno)'),
    (40,'ix_patentes_monitoramento_tenant',   'patentes_monitoramento', 'public.patentes_monitoramento USING btree (tenant_id)'),
    (40,'ix_patentes_monitoramento_codigo',   'patentes_monitoramento', 'public.patentes_monitoramento USING btree (codigo_interno)'),

    -- ===================== FASE 5: TABELAS DO APLICATIVO ===================
    -- Normalmente já existem (criadas por `alembic upgrade head`). Estão aqui
    -- para a auditoria ser completa: se existirem, nada é gerado.
    (45,'ix_audit_logs_tenant_created','audit_logs','public.audit_logs USING btree (tenant_id, created_at)'),
    (45,'ix_audit_logs_action','audit_logs','public.audit_logs USING btree (action)'),
    (45,'ix_refresh_tokens_user','refresh_tokens','public.refresh_tokens USING btree (user_id)'),
    (45,'ix_resources_module','resources','public.resources USING btree (module_id)'),
    (45,'ix_role_policies_role','role_policies','public.role_policies USING btree (role_id)'),
    (45,'ix_role_policies_user','role_policies','public.role_policies USING btree (user_id)'),
    (45,'ix_user_policies_user','user_policies','public.user_policies USING btree (user_id)'),
    (45,'ix_groups_tenant','groups','public.groups USING btree (tenant_id)'),
    (45,'ix_group_policies_group','group_policies','public.group_policies USING btree (group_id)'),
    (45,'ix_user_groups_user','user_groups','public.user_groups USING btree (user_id)'),
    (45,'ix_user_groups_group','user_groups','public.user_groups USING btree (group_id)'),
    (45,'ix_menu_items_menu','menu_items','public.menu_items USING btree (menu_id)'),
    (45,'ix_user_tenants_user','user_tenants','public.user_tenants USING btree (user_id)'),
    (45,'ix_user_company_unity_user','user_company_unity','public.user_company_unity USING btree (user_id)'),
    (45,'ix_departments_tenant','departments','public.departments USING btree (tenant_id)'),
    (45,'ix_people_tenant','people','public.people USING btree (tenant_id)'),
    (45,'ix_people_name','people','public.people USING btree (name)'),
    (45,'ix_companies_tenant','companies','public.companies USING btree (tenant_id)'),
    (45,'ix_companies_company_name','companies','public.companies USING btree (company_name)'),
    (45,'ix_unities_tenant','unities','public.unities USING btree (tenant_id)'),
    (45,'ix_unities_company','unities','public.unities USING btree (company_id)'),
    (45,'ix_customers_tenant','customers','public.customers USING btree (tenant_id)'),
    (45,'ix_customers_company','customers','public.customers USING btree (company_id)'),
    (45,'ix_crm_opportunities_tenant','crm_opportunities','public.crm_opportunities USING btree (tenant_id)'),
    (45,'ix_crm_opportunities_stage','crm_opportunities','public.crm_opportunities USING btree (tenant_id, stage)'),
    (45,'ix_crm_opportunities_customer','crm_opportunities','public.crm_opportunities USING btree (customer_id)'),
    (45,'ix_crm_opportunities_owner','crm_opportunities','public.crm_opportunities USING btree (owner_id)'),
    (45,'ix_crm_proposals_tenant','crm_proposals','public.crm_proposals USING btree (tenant_id)'),
    (45,'ix_crm_proposals_status','crm_proposals','public.crm_proposals USING btree (tenant_id, status)'),
    (45,'ix_crm_proposals_opportunity','crm_proposals','public.crm_proposals USING btree (opportunity_id)'),
    (45,'ix_crm_proposals_customer','crm_proposals','public.crm_proposals USING btree (customer_id)'),
    (45,'ix_crm_activities_tenant','crm_activities','public.crm_activities USING btree (tenant_id)'),
    (45,'ix_crm_activities_subject','crm_activities','public.crm_activities USING btree (tenant_id, subject_type, subject_id)'),
    (45,'ix_crm_activities_due','crm_activities','public.crm_activities USING btree (tenant_id, due_at)'),
    (45,'ix_crm_activities_owner','crm_activities','public.crm_activities USING btree (owner_id)'),
    (45,'ix_inpi_dataset_category','inpi_dataset','public.inpi_dataset USING btree (category)'),
    (45,'ix_inpi_dataset_status','inpi_dataset','public.inpi_dataset USING btree (status)'),
    (45,'ix_inpi_import_dataset','inpi_import','public.inpi_import USING btree (dataset_id)'),
    (45,'ix_inpi_import_error_import','inpi_import_error','public.inpi_import_error USING btree (import_id)'),
    (45,'ix_inpi_rpi_status','inpi_rpi','public.inpi_rpi USING btree (status)'),
    (45,'ix_disclosures_tenant','invention_disclosures','public.invention_disclosures USING btree (tenant_id)'),
    (45,'ix_disclosures_unity','invention_disclosures','public.invention_disclosures USING btree (unity_id)'),
    (45,'ix_disclosures_status','invention_disclosures','public.invention_disclosures USING btree (status)'),
    (45,'ix_disclosures_tenant_created','invention_disclosures','public.invention_disclosures USING btree (tenant_id, created_at)'),
    (45,'ix_disclosure_inventors_disclosure','disclosure_inventors','public.disclosure_inventors USING btree (disclosure_id)'),
    (45,'ix_disclosure_inventors_tenant','disclosure_inventors','public.disclosure_inventors USING btree (tenant_id)'),
    (45,'ix_invention_documents_tenant','invention_documents','public.invention_documents USING btree (tenant_id)'),
    (45,'ix_invention_documents_disclosure','invention_documents','public.invention_documents USING btree (disclosure_id)'),
    (45,'ix_invention_documents_asset','invention_documents','public.invention_documents USING btree (asset_id)'),
    (45,'ix_document_acls_document','document_acls','public.document_acls USING btree (document_id)'),
    (45,'ix_document_acls_tenant','document_acls','public.document_acls USING btree (tenant_id)'),
    (45,'ix_workflow_states_tenant','workflow_states','public.workflow_states USING btree (tenant_id)'),
    (45,'ix_workflow_transitions_tenant','workflow_transitions','public.workflow_transitions USING btree (tenant_id)'),
    (45,'ix_workflow_instances_tenant','workflow_instances','public.workflow_instances USING btree (tenant_id)'),
    (45,'ix_workflow_history_instance','workflow_history','public.workflow_history USING btree (instance_id, created_at)'),
    (45,'ix_workflow_history_tenant','workflow_history','public.workflow_history USING btree (tenant_id)'),
    (45,'ix_workflow_history_disclosure','workflow_history','public.workflow_history USING btree (disclosure_id)'),
    (45,'ix_evaluations_tenant','evaluations','public.evaluations USING btree (tenant_id)'),
    (45,'ix_evaluations_disclosure','evaluations','public.evaluations USING btree (disclosure_id)'),
    (45,'ix_evaluations_kind','evaluations','public.evaluations USING btree (kind)'),
    (45,'ix_ip_assets_tenant','ip_assets','public.ip_assets USING btree (tenant_id)'),
    (45,'ix_ip_assets_unity','ip_assets','public.ip_assets USING btree (unity_id)'),
    (45,'ix_ip_assets_type','ip_assets','public.ip_assets USING btree (asset_type)'),
    (45,'ix_ip_assets_status','ip_assets','public.ip_assets USING btree (status)'),
    (45,'ix_ip_asset_public_links_asset','ip_asset_public_links','public.ip_asset_public_links USING btree (asset_id)'),
    (45,'ix_ip_asset_public_links_tenant','ip_asset_public_links','public.ip_asset_public_links USING btree (tenant_id)'),
    (45,'ix_ip_asset_public_links_ref','ip_asset_public_links','public.ip_asset_public_links USING btree (source, external_ref)'),
    (45,'ix_trl_history_tenant','trl_history','public.trl_history USING btree (tenant_id)'),
    (45,'ix_trl_history_disclosure','trl_history','public.trl_history USING btree (disclosure_id)'),
    (45,'ix_trl_history_asset','trl_history','public.trl_history USING btree (asset_id)'),
    (45,'ix_committees_tenant','committees','public.committees USING btree (tenant_id)'),
    (45,'ix_committee_members_committee','committee_members','public.committee_members USING btree (committee_id)'),
    (45,'ix_committee_members_user','committee_members','public.committee_members USING btree (user_id)'),
    (45,'ix_committee_meetings_committee','committee_meetings','public.committee_meetings USING btree (committee_id)'),
    (45,'ix_committee_meetings_tenant','committee_meetings','public.committee_meetings USING btree (tenant_id)'),
    (45,'ix_committee_meetings_date','committee_meetings','public.committee_meetings USING btree (scheduled_at)'),
    (45,'ix_committee_agenda_items_meeting','committee_agenda_items','public.committee_agenda_items USING btree (meeting_id)'),
    (45,'ix_committee_agenda_items_disclosure','committee_agenda_items','public.committee_agenda_items USING btree (disclosure_id)'),
    (45,'ix_committee_agenda_items_asset','committee_agenda_items','public.committee_agenda_items USING btree (asset_id)'),
    (45,'ix_committee_votes_item','committee_votes','public.committee_votes USING btree (item_id)'),
    (45,'ix_committee_votes_tenant','committee_votes','public.committee_votes USING btree (tenant_id)'),
    (45,'ix_committee_decisions_tenant','committee_decisions','public.committee_decisions USING btree (tenant_id)'),
    (45,'ix_technology_offers_tenant','technology_offers','public.technology_offers USING btree (tenant_id)'),
    (45,'ix_technology_offers_status','technology_offers','public.technology_offers USING btree (status)'),
    (45,'ix_interest_tenant','expressions_of_interest','public.expressions_of_interest USING btree (tenant_id)'),
    (45,'ix_interest_offer','expressions_of_interest','public.expressions_of_interest USING btree (offer_id)'),
    (45,'ix_interest_status','expressions_of_interest','public.expressions_of_interest USING btree (status)'),
    (45,'ix_interest_interactions_interest','interest_interactions','public.interest_interactions USING btree (interest_id, created_at)'),
    (45,'ix_interest_interactions_tenant','interest_interactions','public.interest_interactions USING btree (tenant_id)'),
    (45,'ix_negotiations_tenant','negotiations','public.negotiations USING btree (tenant_id)'),
    (45,'ix_negotiations_interest','negotiations','public.negotiations USING btree (interest_id)'),
    (45,'ix_negotiations_stage','negotiations','public.negotiations USING btree (stage)'),
    (45,'ix_negotiation_history_neg','negotiation_history','public.negotiation_history USING btree (negotiation_id, created_at)'),
    (45,'ix_negotiation_history_tenant','negotiation_history','public.negotiation_history USING btree (tenant_id)'),
    (45,'ix_licenses_tenant','licenses','public.licenses USING btree (tenant_id)'),
    (45,'ix_licenses_asset','licenses','public.licenses USING btree (asset_id)'),
    (45,'ix_contracts_tenant','contracts','public.contracts USING btree (tenant_id)'),
    (45,'ix_contracts_license','contracts','public.contracts USING btree (license_id)'),
    (45,'ix_contracts_status','contracts','public.contracts USING btree (status)'),
    (45,'ix_contract_parties_contract','contract_parties','public.contract_parties USING btree (contract_id)'),
    (45,'ix_contract_obligations_contract','contract_obligations','public.contract_obligations USING btree (contract_id)'),
    (45,'ix_contract_obligations_due','contract_obligations','public.contract_obligations USING btree (due_date)'),
    (45,'ix_royalties_contract','royalties','public.royalties USING btree (contract_id)'),
    (45,'ix_royalties_period','royalties','public.royalties USING btree (period)'),
    (45,'ix_projects_tenant','projects','public.projects USING btree (tenant_id)'),
    (45,'ix_projects_status','projects','public.projects USING btree (status)'),
    (45,'ix_projects_unity','projects','public.projects USING btree (unity_id)'),
    (45,'ix_project_members_project','project_members','public.project_members USING btree (project_id)'),
    (45,'ix_project_funders_project','project_funders','public.project_funders USING btree (project_id)'),
    (45,'ix_project_milestones_project','project_milestones','public.project_milestones USING btree (project_id)'),
    (45,'ix_project_milestones_due','project_milestones','public.project_milestones USING btree (due_date)'),
    (45,'ix_project_asset_links_project','project_asset_links','public.project_asset_links USING btree (project_id)'),
    (45,'ix_project_asset_links_asset','project_asset_links','public.project_asset_links USING btree (asset_id)'),
    (45,'ix_startups_tenant','startups','public.startups USING btree (tenant_id)'),
    (45,'ix_startups_status','startups','public.startups USING btree (status)'),
    (45,'ix_startup_members_startup','startup_members','public.startup_members USING btree (startup_id)'),
    (45,'ix_incubation_programs_tenant','incubation_programs','public.incubation_programs USING btree (tenant_id)'),
    (45,'ix_incubation_participations_program','incubation_participations','public.incubation_participations USING btree (program_id)'),
    (45,'ix_incubation_participations_startup','incubation_participations','public.incubation_participations USING btree (startup_id)'),
    (45,'ix_incubation_stages_participation','incubation_stages','public.incubation_stages USING btree (participation_id)'),
    (45,'ix_nit_notifications_user','nit_notifications','public.nit_notifications USING btree (user_id)'),
    (45,'ix_nit_notifications_tenant','nit_notifications','public.nit_notifications USING btree (tenant_id)'),
    (45,'ix_nit_notifications_unread','nit_notifications','public.nit_notifications USING btree (user_id, read_at)'),
    (45,'ix_nit_notif_pref_user','nit_notification_preferences','public.nit_notification_preferences USING btree (user_id)'),
    (45,'ix_nit_email_status','nit_email_messages','public.nit_email_messages USING btree (status)'),
    (45,'ix_nit_email_tenant','nit_email_messages','public.nit_email_messages USING btree (tenant_id)'),
    (45,'ix_nit_portal_access_tenant','nit_portal_access','public.nit_portal_access USING btree (tenant_id)'),
    (45,'ix_nit_portal_access_status','nit_portal_access','public.nit_portal_access USING btree (status)'),
    (45,'ix_nit_portal_requests_access','nit_portal_requests','public.nit_portal_requests USING btree (access_id)'),
    (45,'ix_nit_portal_requests_tenant','nit_portal_requests','public.nit_portal_requests USING btree (tenant_id)'),
    (45,'ix_nit_portal_requests_status','nit_portal_requests','public.nit_portal_requests USING btree (status)'),
    (45,'ix_nit_portal_notes_request','nit_portal_request_notes','public.nit_portal_request_notes USING btree (request_id)'),
    (45,'ix_nit_saved_reports_tenant','nit_saved_reports','public.nit_saved_reports USING btree (tenant_id)'),
    (45,'ix_nit_report_runs_report','nit_report_runs','public.nit_report_runs USING btree (report_id)'),
    (45,'ix_nit_report_runs_tenant','nit_report_runs','public.nit_report_runs USING btree (tenant_id)'),
    (45,'ix_nit_integration_tenant','nit_integration_endpoints','public.nit_integration_endpoints USING btree (tenant_id)'),
    (45,'ix_nit_integration_kind','nit_integration_endpoints','public.nit_integration_endpoints USING btree (kind)'),
    (45,'ix_nit_integration_deliveries_endpoint','nit_integration_deliveries','public.nit_integration_deliveries USING btree (endpoint_id)'),
    (45,'ix_nit_integration_deliveries_status','nit_integration_deliveries','public.nit_integration_deliveries USING btree (status)'),

    -- ===================== FASE 6: GIN TRIGRAM (PESADO) ====================
    -- Só afeta "Contém" (ILIKE '%x%'), "Começa com" e a busca global.
    -- Comente este bloco se o disco estiver apertado (veja `df -h` na VM).
    (60,'ix_marcas_elemento_nominativo_trgm','marcas','public.marcas USING gin (elemento_nominativo gin_trgm_ops)'),
    (60,'ix_marcas_fold_trgm','marcas','public.marcas USING gin (public.fold(elemento_nominativo) gin_trgm_ops)'),
    (60,'ix_marcas_numero_inpi_trgm','marcas','public.marcas USING gin (numero_inpi gin_trgm_ops)'),
    (60,'ix_patentes_conteudo_titulo_trgm','patentes_conteudo','public.patentes_conteudo USING gin (titulo gin_trgm_ops)'),
    (60,'ix_patentes_conteudo_resumo_trgm','patentes_conteudo','public.patentes_conteudo USING gin (resumo gin_trgm_ops)'),
    (60,'ix_patentes_numero_inpi_trgm','patentes','public.patentes USING gin (numero_inpi gin_trgm_ops)'),
    (60,'ix_patentes_numero_pct_trgm','patentes','public.patentes USING gin (numero_pct gin_trgm_ops)')
),
analisar(tabela) AS (
    VALUES ('marcas'), ('marcas_depositantes'), ('marcas_classificacoes_nacionais'),
           ('marcas_classificacoes_nice'), ('marcas_classificacoes_viena'),
           ('marcas_despachos'), ('marcas_logos'),
           ('patentes'), ('patentes_conteudo'), ('patentes_depositantes'),
           ('patentes_inventores'), ('patentes_procuradores'), ('patentes_prioridades'),
           ('patentes_classificacao_ipc'), ('patentes_despachos'),
           ('patentes_renumeracoes'), ('patentes_vinculos')
),
norm AS (
    SELECT ordem, nome, tabela, definicao,
           replace(regexp_replace(definicao, '[[:space:]]+', ' ', 'g'),
                   'public.', '') AS chave
    FROM esperado
),
existente AS (
    SELECT tabela, chave, min(indice) AS indice
    FROM (
        SELECT tc.relname AS tabela,
               ic.relname AS indice,
               replace(regexp_replace(regexp_replace(pg_get_indexdef(i.indexrelid),
                       '^CREATE (UNIQUE )?INDEX [^ ]+ ON ', ''),
                       '[[:space:]]+', ' ', 'g'), 'public.', '') AS chave
        FROM pg_index i
        JOIN pg_class tc ON tc.oid = i.indrelid
        JOIN pg_class ic ON ic.oid = i.indexrelid
        JOIN pg_namespace n ON n.oid = tc.relnamespace
        WHERE n.nspname = 'public' AND tc.relkind = 'r' AND i.indisvalid
    ) z
    GROUP BY tabela, chave
),
nome_uso AS (
    SELECT ic.relname AS nome,
           regexp_replace(pg_get_indexdef(ic.oid),
                          '^CREATE (UNIQUE )?INDEX [^ ]+ ON ', '') AS definicao_atual,
           i.indisvalid
    FROM pg_index i
    JOIN pg_class ic ON ic.oid = i.indexrelid
    JOIN pg_namespace n ON n.oid = ic.relnamespace
    WHERE n.nspname = 'public'
)
SELECT linha::text FROM (
    SELECT 0 AS ordem, 0 AS sub, '-- ======================================================' AS linha
    UNION ALL SELECT 0, 1, '-- IntelliINPI - indices faltantes (gerado automaticamente)'
    UNION ALL SELECT 0, 2, '-- Revise antes de rodar. So cria o que realmente falta.'
    UNION ALL SELECT 0, 3, '-- ======================================================'
    UNION ALL SELECT 0, 4, 'SET statement_timeout = 0;'
    UNION ALL SELECT 0, 5, 'SET lock_timeout = 0;'
    UNION ALL SELECT 0, 6, 'SET maintenance_work_mem = ''256MB'';'
    UNION ALL SELECT 0, 7, 'SET max_parallel_maintenance_workers = 2;'
    UNION ALL SELECT 0, 8, ''
    UNION ALL SELECT 9, 0, '-- FASE: btree de busca (marcas/patentes/relacoes/relacionamentos)'
    UNION ALL
    SELECT e.ordem, 1,
           CASE
             WHEN to_regclass('public.' || e.tabela) IS NULL
               THEN '-- [TABELA AUSENTE] ' || e.tabela || ' -> ' || e.nome || ' ignorado'
             WHEN x.indice IS NOT NULL
               THEN '-- [OK] ' || e.nome || ' (equivalente existente: ' || x.indice || ')'
             WHEN u.nome IS NOT NULL
               THEN '-- [CONFLITO] ' || e.nome || ' ja existe com definicao diferente/invalida ('
                    || u.definicao_atual || '); remova manualmente e rode novamente'
             ELSE 'CREATE INDEX IF NOT EXISTS ' || quote_ident(e.nome)
                  || ' ON ' || e.definicao || ';'
           END
    FROM norm e
    LEFT JOIN existente x ON x.tabela = e.tabela AND x.chave = e.chave
    LEFT JOIN nome_uso  u ON u.nome = e.nome
    UNION ALL SELECT 50, 0, ''
    UNION ALL SELECT 50, 1, '-- FASE: ANALYZE (o planner so passa a usar os indices novos depois disso)'
    UNION ALL
    SELECT 50, 2,
           CASE WHEN to_regclass('public.' || a.tabela) IS NULL
                THEN '-- [TABELA AUSENTE] ANALYZE ' || a.tabela
                ELSE 'ANALYZE ' || quote_ident(a.tabela) || ';' END
    FROM analisar a
    UNION ALL SELECT 59, 0, ''
    UNION ALL SELECT 59, 1, '-- FASE PESADA: GIN trigram (remove este bloco se o disco estiver apertado)'
    UNION ALL SELECT 80, 0, ''
    UNION ALL SELECT 80, 1, '-- FASE: ANALYZE final'
    UNION ALL
    SELECT 80, 2,
           CASE WHEN to_regclass('public.' || a.tabela) IS NULL
                THEN '-- [TABELA AUSENTE] ANALYZE ' || a.tabela
                ELSE 'ANALYZE ' || quote_ident(a.tabela) || ';' END
    FROM analisar a
    UNION ALL SELECT 999, 0, ''
    UNION ALL SELECT 999, 1, '-- ===== FIM ====='
) t
ORDER BY ordem, sub, linha;
