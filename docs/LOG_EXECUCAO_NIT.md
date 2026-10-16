# Log de Execução — NIT

**Formato:** registro conciso de atividades, comandos, resultados e problemas.
Sem segredos, tokens ou dados pessoais.

---

## 2026-10-09

### Inspeção inicial
- `git status` → branch `main`; modificados de F0 (.env.example, config.py, main.py, users.py, conftest.py);
  novos: `app/logging_config.py`, `scripts/`, `test_foundation_hardening.py`, `docs/`.
- App tree confirmado: `models/{auth,company,inpi,marcas,patentes,rbac}.py`,
  `routers/{...}`, `services/deepseek.py`. Sem `models/nit.py` (esperado).
- Alembic head: `e5f6a7b8c9d0_restructure_core_rbac.py` (6 migrações).
- Frontend: 16 rotas em `src/app/*`, componentes em `src/components/*`, libs em `src/lib/*`.
- `package.json` scripts: `dev`, `build`, `start`, `lint` (`next lint`). **Sem ESLint config** → lint indisponível.

### Baseline de testes
- Comando: `.venv\Scripts\python.exe -m pytest --no-header -p no:cacheprovider -q`
- Resultado: **109 passed** (confirmado; contagem real do estado atual).

### Documentos de controle criados
- `docs/EXECUCAO_AUTONOMA_NIT.md` (estado + checklist)
- `docs/DECISOES_EXECUCAO_AUTONOMA_NIT.md` (premissas provisórias)
- `docs/LOG_EXECUCAO_NIT.md` (este arquivo)

### Próximo passo
- Iniciar F1: catálogo NIT em `constants.py` → modelos → schemas → serviços → routers → migração → testes → frontend.

### F1 — Backend concluído
- **Catálogo RBAC**: módulo `NIT`, 18 permissões `NIT_*`, 5 recursos `nit:*`, 3 roles
  (`NIT_RESEARCHER`, `NIT_ANALYST`, `NIT_MANAGER`) + concessões para `TENANT_ADMIN`.
- **Modelos** (`app/models/nit.py`, 11 tabelas): `InventionDisclosure`, `DisclosureInventor`,
  `InventionDocument`, `DocumentAcl`, `WorkflowState`, `WorkflowTransition`, `WorkflowInstance`,
  `WorkflowHistory` (append-only), `Evaluation`, `IPAsset`, `IPAssetPublicLink` (sem FK dura).
- **Serviços**: `services/protocol.py` (NIT-AAAA-NNNN único por tenant), `services/storage.py`
  (abstração + local privado + S3 inerte + magic bytes + limite), `services/workflow.py`
  (máquina de estados + alçada por permissão/role + concorrência otimista).
- **Routers** (`app/routers/nit/*`, 24 endpoints): disclosures (CRUD+dossiê+workflow+pareceres),
  documents (upload/download/ACL), workflow (estados/transições), assets (+vínculo público),
  dashboard (indicadores reais).
- **Migração**: `f6a7b8c9d0e1_add_nit_domain.py` (head; aditiva; downgrade funcional testado).
- **Seed**: `app/seed_nit.py` (workflow padrão por tenant).
- **Testes**: `test_nit_f1.py` (17), `test_nit_storage.py` (7), `test_nit_migration.py` (1).
- **Correções**: import faltante `ACL_WRITE`; ordem de DROP no downgrade; endpoints DELETE
  retornam corpo JSON 200 (convenção do projeto) em vez de 204.

### Suíte completa pós-F1 backend
- Comando: `pytest --junit-xml` → **134 passed, 0 failed, 0 erros, 0 skipped**.
- (109 baseline + 25 novos F1).

### F1 — Frontend concluído
- `src/lib/types.ts`: tipos NIT + `PaginatedNit<T>`.
- `src/lib/hooks.ts`: hooks NIT (dashboard, disclosures, workflow, evaluations, documents, assets).
- `src/components/AppShell.tsx`: grupo de navegação NIT (dropdown genérico substituiu o
  hardcode de `/admin`), ícone `flask`.
- Páginas: `src/app/nit/page.tsx` (painel), `nit/comunicacoes/page.tsx` + `NewDisclosureModal`,
  `nit/comunicacoes/[id]/page.tsx` (dossiê com abas) + `WorkflowPanel`, `EvaluationsPanel`,
  `DocumentsPanel`, `nit/ativos/page.tsx` + `NewAssetModal`, `nit/ativos/[id]/page.tsx`,
  `nit/documentos/page.tsx`.
- **Gate F1 frontend**: `npx tsc --noEmit` exit **0**; `npm run build` exit **0** (20 rotas).
- `npm run lint` continua indisponível (sem config ESLint — pré-existente; ver risco registrado).

### Gate F1
- Backend 134/134; isolamento tenant+unidade, ACL, protocolo, workflow, migração round-trip.
- Frontend tsc + build OK.
- Módulos públicos existentes (marcas/patentes/CRM/IA) preservados (suíte baseline verde).

### F2 — Backend concluído
- **Catálogo**: +9 permissões `NIT_*` (TRL, comitês, portfólio), +2 recursos
  (`nit:committee`, `nit:portfolio`), role `NIT_COMMITTEE_MEMBER`; `NIT_MANAGER` ampliado.
- **Modelos** (`app/models/nit_f2.py`, 7 tabelas): `TechnologyReadinessLevel` (append-only,
  nunca automático), `Committee`, `CommitteeMember`, `CommitteeMeeting`, `CommitteeAgendaItem`,
  `CommitteeVote` (único por membro/item), `CommitteeDecision` (append-only).
- **Serviço** `services/committee.py`: quórum (votos válidos), maioria simples, conflito de
  interesse → voto `IMPEDED` não conta para quórum, `DECISION_DEFERRED` sempre permitido.
- **Routers**: `routers/nit/committees.py` (comitês, membros, reuniões, pautas, votos, decisão),
  `routers/nit/portfolio.py` (TRL, portfólio, alertas, export CSV). +14 endpoints.
- **Migração** `a7b8c9d0e1f2_add_nit_f2.py` (aditiva; downgrade funcional testado).
- **Testes** `test_nit_f2.py` (13): autorização, conflito de interesse, quórum/votação,
  duplicidade, integridade, alertas reais, isolamento.

### F2 — Frontend concluído
- Tipos + hooks F2; páginas `nit/comites` (+ `[id]` com `MeetingCard`, `AgendaItemRow`,
  `AddMemberModal`, `NewMeetingModal`), `nit/portfolio`, `TrlPanel` no detalhe do ativo.
- `npx tsc --noEmit` exit 0; `npm run build` exit 0.

### Suíte completa pós-F2
- `pytest --junit-xml` → **147 passed, 0 failed, 0 erros, 0 skipped** (134 + 13 F2).

### F3 — Backend concluído
- **Catálogo**: +15 permissões `NIT_*` (TT/contratos), +2 recursos (`nit:tt`, `nit:contract`),
  role `NIT_TT_OPERATOR`.
- **Modelos** (`app/models/nit_f3.py`, 10 tabelas): `TechnologyOffer`, `ExpressionOfInterest`,
  `InterestInteraction`, `Negotiation`, `NegotiationHistory`, `License`, `Contract`,
  `ContractParty`, `ContractObligation`, `Royalty`. Valores monetários em `Numeric(18,2)`.
- **Serviço** `services/negotiation.py`: pipeline explícito (arestas declaradas; etapa inválida → 422).
- **Routers**: `routers/nit/tt.py` (catálogo, ofertas, interesses, interações, negociações),
  `routers/nit/contracts.py` (licenças, contratos, partes, obrigações, royalties, resumo, alertas).
- **Migração** `b8c9d0e1f2a3_add_nit_f3.py` (aditiva; downgrade funcional testado).
- **Testes** `test_nit_f3.py` (11): catálogo público só PUBLISHED, interesse só em oferta publicada,
  isolamento, pipeline válido/inválido, pipeline NÃO altera status de contrato, partes,
  aritmética Decimal, alertas reais, permissões.
- **Regra garantida**: o pipeline de negociação **nunca** altera a situação jurídica de um contrato.

### F3 — Frontend concluído
- Tipos + hooks F3; páginas `nit/catalogo` (+ `[id]` com `RegisterInterestModal`),
  `nit/negociacoes`, `nit/contratos` (+ `[id]` com `ObligationsCard`, `RoyaltiesCard`,
  `RoyaltySummaryCard`, `NewContractModal`), `ContractsTable`.
- `npx tsc --noEmit` exit 0; `npm run build` exit 0.

### Suíte completa pós-F3
- `pytest --junit-xml` → **158 passed, 0 failed, 0 erros, 0 skipped** (147 + 11 F3).

### F4 — Backend concluído
- **Catálogo**: +9 permissões `NIT_*` (projetos, startups, incubação, indicadores, FORMICT),
  +3 recursos (`nit:project`, `nit:startup`, `nit:indicator`); `NIT_MANAGER` + `TENANT_ADMIN` ampliados.
- **Modelos** (`app/models/nit_f4.py`, 10 tabelas): `Project`, `ProjectMember`, `ProjectFunder`,
  `ProjectMilestone`, `ProjectAssetLink`, `Startup`, `StartupMember`, `IncubationProgram`,
  `IncubationParticipation`, `IncubationStage`. `Project.code`/`Startup.code` sequenciais por tenant.
  Valores monetários em `Numeric(18,2)`.
- **Routers**: `routers/nit/projects.py` (projetos + membros/financiadores/marcos/vínculos de ativo),
  `routers/nit/startups.py` (startups + membros + programas/participações/fases),
  `routers/nit/indicators.py` (`/indicators` e `/formict` + `/formict/export` CSV). +17 endpoints (65 no total).
- **Migração** `c9d0e1f2a3b4_add_nit_f4.py` (aditiva; downgrade funcional testado).
- **Testes** `test_nit_f4.py` (10): CRUD de projeto + isolamento, membros/financiadores/marcos,
  integridade/duplicidade de vínculo de ativo (409) + rejeição cross-tenant, criação de startup e
  vínculo ≠ propriedade, fluxo de incubação + dedupe (409), isolamento de startup, indicadores com
  consulta real, disclaimer FORMICT + export, gates de permissão.
- **Regra garantida**: vincular startup↔ativo **não** infere propriedade (não há campo de
  propriedade; coberto por teste). Participação em incubação marca `Startup.status=INCUBATED`
  apenas como indicador de conveniência. Indicadores/FORMICT derivam **exclusivamente** de consultas
  reais; o FORMICT é explicitamente relatório **interno de apoio** (disclaimer: "NÃO é o formulário
  oficial"), não submissão oficial.

### Suíte completa pós-F4
- `pytest` → **168 passed, 0 failed, 0 erros, 0 skipped** (158 + 10 F4).

### F4 — Frontend concluído
- `src/lib/types.ts`: tipos F4 (projeto + membros/financiadores/marcos/vínculos, startup + membros,
  programas, participações, fases, indicadores, FORMICT).
- `src/lib/hooks.ts`: hooks F4 (projetos, startups, membros, programas/participações/fases,
  indicadores, FORMICT).
- `src/components/AppShell.tsx`: entradas de navegação (Projetos de P&D, Startups, Incubação,
  Indicadores & FORMICT).
- Páginas: `nit/projetos` (+ `[id]` com `ProjectsTable`, `NewProjectModal` e cards de
  equipe/marcos/financiadores/ativos), `nit/startups` (+ `[id]` com `StartupsTable`,
  `NewStartupModal`, membros/fundadores), `nit/incubacao` (+ `IncubationModals`),
  `nit/indicadores` (métricas reais + FORMICT + export CSV com `IndicatorWidgets`).
- **Gate F4 frontend**: `npx tsc --noEmit` exit **0**; `npm run build` exit **0** (33 rotas).

### Próximo passo
- Iniciar F5 (portais externos pesquisador/empresa, BI, notificações, OpenAPI/tipos TS, integrações),
  após o que será gerado `docs/RELATORIO_FINAL_NIT.md` e a execução será pausada para validação
  consolidada do usuário.

### F5 — Backend concluído
- **Catálogo**: +10 permissões `NIT_*` (notificações, portal, portal requests, BI, integrações),
  +4 recursos (`nit:notification`, `nit:portal`, `nit:bi`, `nit:integration`); `NIT_MANAGER` +
  `TENANT_ADMIN` ampliados.
- **Modelos** (`app/models/nit_f5.py`, 10 tabelas): `Notification`, `NotificationPreference`,
  `EmailMessage` (outbox), `ExternalPortalAccess`, `PortalRequest`, `PortalRequestNote`,
  `SavedReport`, `ReportRun` (append-only), `IntegrationEndpoint`, `IntegrationDelivery` (outbox).
- **Serviço** `services/indicators.py` (extraído do router F4; fonte única de indicadores reais,
  reusado por `/indicators` e `/bi`), `services/notifications.py` (notificação in-app + outbox de
  e-mail + broadcast de integração), `services/ts_types.py` (gerador de tipos TS do OpenAPI, R-18).
- **Routers**: `routers/nit/notifications.py` (listar/ler/preferências/e-mails),
  `routers/nit/portal.py` (concessões + triagem + submissão pública por token),
  `routers/nit/bi.py` (métricas reais + relatórios salvos + execução/export),
  `routers/nit/integrations.py` (registro + outbox + broadcast),
  `routers/nit/devtools.py` (`/dev/ts-types`). +21 endpoints (86 no total).
- **Migração** `d0e1f2a3b4c5_add_nit_f5.py` (aditiva; downgrade funcional testado; head único).
- **Testes** `test_nit_f5.py` (13): isolamento de notificação por usuário, fluxo de leitura,
  opt-in de e-mail enfileira outbox (permanece QUEUED), preferência inválida rejeitada (422),
  ciclo de concessão de portal + submissão pública (token correto/errado/revogado), duplicidade
  (409), isolamento de solicitações, BI com métricas reais + whitelist + escopo de tenant,
  outbox de integração permanece PENDING, broadcast só para endpoints habilitados, geração de
  tipos TS, gates de permissão.
- **Regras garantidas**: (1) concessão de portal **nunca** confere permissões internas — só permite
  submeter/consultar no escopo do próprio titular; (2) notificações e entregas de integração seguem
  o padrão **outbox** — nada é declarado enviado/entregue sem transporte real; (3) e-mail é opt-in
  por tipo de notificação (padrão desligado); (4) indicadores e BI derivam **exclusivamente** de
  consultas reais; (5) token de acesso ao portal é revelado uma única vez (não é listado depois).

### Suíte completa pós-F5
- `pytest` → **181 passed, 0 failed, 0 erros, 0 skipped** (168 + 13 F5).

### F5 — Frontend concluído
- `src/lib/types.ts`: tipos F5 (notificações, preferências, e-mails, concessões, solicitações,
  relatórios salvos, integrações/entregas).
- `src/lib/hooks.ts`: hooks F5 (notificações/leitura/preferências/e-mails, portais/concessões/
  triagem, BI/métricas/relatórios/execução, integrações/entregas).
- `src/components/AppShell.tsx`: entradas de navegação (Notificações, BI & Relatórios,
  Portais externos, Integrações).
- Páginas: `nit/notificacoes` (caixa de entrada + preferências), `nit/bi` (métricas reais +
  relatórios + execução/export), `nit/portais` (+ `PortalWidgets` com triagem e concessão/token),
  `nit/integracoes` (registro + fila outbox).
- **Gate F5 frontend**: `npx tsc --noEmit` exit **0**; `npm run build` exit **0** (37 rotas).

### F1–F5 concluídas — execução pausada para validação
- Relatório final consolidado em `docs/RELATORIO_FINAL_NIT.md`.
- Nenhum commit/push/deploy foi realizado em nenhum momento.

---

## 2026-10-10 (Auditoria Independente)

### Auditoria de segurança e validação técnica
- Executada auditoria independente completa das fases F1–F5.
- **Suíte de testes:** 181 passed (100%).
- **Defeito encontrado e corrigido:** Teste de migração falhava com caminho relativo (`test_nit_migration.py:109`).
- **Correção aplicada:** Path absoluto via `Path(__file__).parent.parent` para resolver `alembic.ini` e `script_location`.
- **Validação:** Teste `test_nit_migration_upgrade_and_downgrade` agora passa em `1 passed in 6.33s`.

### Verificações de segurança realizadas
- **Isolamento multi-tenant:** ✅ Comprovado em todos os 16 routers NIT.
- **Proteção IDOR:** ✅ IDs cross-tenant retornam 404.
- **ACL de documentos:** ✅ `can_access_document` verifica tenant + RBAC + ACL explícita.
- **Auditoria:** ✅ Downloads não-públicos e exports registram trilha.
- **Storage:** ✅ Magic bytes validation, key whitelist regex.
- **Portal público:** ✅ `secrets.compare_digest` (tempo constante).
- **Exports BI/FORMICT:** ✅ `compute_indicators` sempre filtra por `tenant_id`.
- **Autorização RBAC:** ✅ Todos os endpoints sensíveis usam `require_permission`.

### Resultados da auditoria
- **Classificação final:** ✅ APROVADO COM RESSALVAS.
- **Defeitos críticos:** 0
- **Defeitos altos:** 0
- **Defeitos médios:** 1 (corrigido)
- **Defeitos baixos:** 2 (informativos, não bloqueantes)
- **Relatório completo:** `docs/AUDITORIA_FINAL_F1_F5.md`
- **Documento de continuidade:** `docs/CONTINUIDADE_PROXIMA_SESSAO_NIT.md`

### Próxima ação recomendada
- Validação funcional end-to-end (1–2 dias): executar servidor dev e testar ao menos 1 fluxo representativo por fase (F1–F5) no navegador.
- Após validação OK: revisar decisões de produto, criar primeiro commit, abrir PR, deploy em staging.

**Nenhum commit/push/deploy foi realizado durante a auditoria.**

