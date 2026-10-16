# Relatório Final — Execução Autônoma NIT (F1–F5)

**Data:** 2026-10-10
**Natureza:** Consolidação da execução autorizada das fases F1–F5 do plano de evolução do
IntelliINPI para plataforma SaaS de gestão de NIT.
**Escopo:** implementação real e aditiva, preservando 100% do sistema existente
(marcas, patentes, CRM, análise por IA, ingestão INPI, auth, RBAC, monitoramento).

> Este relatório consolida o que foi implementado, testado e validado. Nenhum commit,
> push ou deploy foi realizado em nenhum momento. A execução está **pausada para
> validação consolidada do usuário**.

---

## 1. Status geral

| Fase | Status | Backend | Frontend | Testes |
|---|---|---|---|---|
| **F0** Fundação | ✅ Concluída (parcial operacional) | R-04/R-08/R-10/500-safe/409 | — | incl. |
| **F1** MVP comunicação de invenção | ✅ Concluída | 11 tabelas, 24-25 endpoints | 9 telas | incl. |
| **F2** Comitês/TRL/Portfólio | ✅ Concluída | +7 tabelas, +14 endpoints | comitês, portfólio | incl. |
| **F3** TT/Contratos | ✅ Concluída | +10 tabelas, +16 endpoints | catálogo, negociações, contratos | 11 |
| **F4** P&D/Startups/Indicadores | ✅ Concluída | +10 tabelas, +17 endpoints | projetos, startups, incubação, indicadores | 10 |
| **F5** Portais/BI/Notificações/Integrações | ✅ Concluída | +10 tabelas, +21 endpoints | notificações, BI, portais, integrações | 13 |

**Backup operacional real (F0):** bloqueado por decisão de infraestrutura **S1** (sem ambiente
isolado/`pg_dump`); runbook e scripts entregues, execução real **não declarada operacional**.

---

## 2. Métricas verificadas (2026-10-10)

| Métrica | Valor |
|---|---|
| Tabelas ORM totais (`Base.metadata`) | **100** |
| Entidades NIT (F1–F5) | **48** |
| Rotas NIT distintas (`/api/nit/...`) | **85** |
| Permissões totais | **110** (sendo **58** `NIT_*`) |
| Recursos RBAC totais | **41** (sendo **16** `nit:*`) |
| Papéis (roles) totais | **13** |
| Migrações Alembic | **11** (head único: `d0e1f2a3b4c5`) |
| Suíte backend | **181 passed, 0 failed, 0 erros, 0 skipped** |
| Gate frontend | `tsc --noEmit` exit **0** · `next build` exit **0** (**37 rotas**) |

---

## 3. Entregas por fase

### F1 — Comunicação de invenção, documentos e ativos
- **Tabelas (11):** `InventionDisclosure`, `DisclosureInventor`, `InventionDocument`,
  `DocumentAcl`, `WorkflowState`, `WorkflowTransition`, `WorkflowInstance`, `WorkflowHistory`
  (append-only), `Evaluation`, `IPAsset`, `IPAssetPublicLink`.
- **Serviços:** `protocol.py` (protocolo único por tenant, concorrente-seguro),
  `storage.py` (abstração + local privado + S3 inerte + magic bytes + limite),
  `workflow.py` (máquina de estados + alçada por permissão/role + concorrência otimista).
- **Endpoints:** disclosures (CRUD+dossiê+workflow+pareceres), documents (upload/download/ACL),
  workflow, assets (+vínculo público), dashboard.

### F2 — Comitês, TRL e portfólio
- **Tabelas (7):** `TechnologyReadinessLevel` (append-only, nunca automático), `Committee`,
  `CommitteeMember`, `CommitteeMeeting`, `CommitteeAgendaItem`, `CommitteeVote`,
  `CommitteeDecision` (append-only).
- **Serviço:** `committee.py` (quórum com votos válidos, maioria simples, conflito de interesse
  → `IMPEDED` não conta para quórum, `DECISION_DEFERRED` sempre permitido).

### F3 — Transferência de tecnologia e contratos
- **Tabelas (10):** `TechnologyOffer`, `ExpressionOfInterest`, `InterestInteraction`,
  `Negotiation`, `NegotiationHistory`, `License`, `Contract`, `ContractParty`,
  `ContractObligation`, `Royalty`. Monetário em `Numeric(18,2)`.
- **Serviço:** `negotiation.py` (pipeline com arestas declaradas; etapa inválida → 422).
- **Regra garantida:** o pipeline de negociação **nunca** altera a situação jurídica de um contrato.

### F4 — P&D, startups, incubação e indicadores
- **Tabelas (10):** `Project`, `ProjectMember`, `ProjectFunder`, `ProjectMilestone`,
  `ProjectAssetLink`, `Startup`, `StartupMember`, `IncubationProgram`,
  `IncubationParticipation`, `IncubationStage`.
- **Regras garantidas:** vincular startup↔ativo **não** infere propriedade (sem campo de
  propriedade; coberto por teste); participação em incubação marca `Startup.status=INCUBATED`
  apenas como indicador de conveniência; indicadores derivam **exclusivamente** de consultas
  reais; FORMICT é **relatório interno de apoio** (disclaimer "NÃO é o formulário oficial").

### F5 — Portais externos, BI, notificações e integrações
- **Tabelas (10):** `Notification`, `NotificationPreference`, `EmailMessage` (outbox),
  `ExternalPortalAccess`, `PortalRequest`, `PortalRequestNote`, `SavedReport`, `ReportRun`
  (append-only), `IntegrationEndpoint`, `IntegrationDelivery` (outbox).
- **Serviços:** `indicators.py` (fonte única de indicadores reais, reusado por `/indicators`
  e `/bi`), `notifications.py` (in-app + outbox + broadcast), `ts_types.py` (gerador de tipos
  TS a partir do OpenAPI — R-18).
- **Endpoints:** notificações (listar/ler/preferências/e-mails), portal (concessões, triagem,
  submissão pública por token), BI (métricas reais, relatórios, execução, export), integrações
  (registro, outbox, broadcast), `/dev/ts-types`.
- **Regras garantidas:** (1) concessão de portal **nunca** confere permissões internas;
  (2) notificações e entregas seguem o padrão **outbox** — nada é declarado enviado/entregue sem
  transporte real; (3) e-mail é opt-in por tipo (padrão desligado); (4) token de acesso ao portal
  é revelado uma única vez e nunca listado.

---

## 4. Invariantes transversais preservados

- **Multi-tenancy:** todo dado NIT é escopado por tenant derivado exclusivamente do usuário
  autenticado; IDs adivinhados de outro tenant retornam 403 (proteção IDOR).
- **RBAC granular:** 58 permissões `NIT_*` e 16 recursos `nit:*`; papéis NIT dedicados
  (`NIT_RESEARCHER`, `NIT_ANALYST`, `NIT_MANAGER`, `NIT_COMMITTEE_MEMBER`, `NIT_TT_OPERATOR`)
  e concessões a `TENANT_ADMIN`/`SUPER_ADMIN`.
- **Aditividade:** todas as migrações criam apenas tabelas novas; nenhuma tabela existente foi
  alterada; downgrade funcional testado (round-trip em banco isolado).
- **Sem números inventados:** valores monetários em `Decimal`/`Numeric(18,2)`; indicadores/FORMICT
  e relatórios de BI derivam exclusivamente de consultas reais; financiamentos só gravados quando
  uma fonte real os informa.
- **Auditoria:** ações sensíveis (export FORMICT, export BI, triagem de portal, download de
  documento não-público) registram trilha.

---

## 5. Verificação (comandos e resultados)

```
# Backend (venv do projeto)
.\.venv\Scripts\pytest.exe            → 181 passed
.\.venv\Scripts\alembic.exe heads     → d0e1f2a3b4c5 (head)   [head único]
python -m compileall -q app           → OK

# Frontend
npx tsc --noEmit                      → exit 0
npm run build                         → exit 0 (37 rotas)
```

Testes por fase (arquivos): `test_nit_f1.py`, `test_nit_storage.py`, `test_nit_f2.py`,
`test_nit_f3.py`, `test_nit_f4.py`, `test_nit_f5.py`, `test_nit_migration.py`,
`test_foundation_hardening.py` + baseline original.

---

## 6. Pendências e decisões não resolvidas (bloqueios declarados)

| Item | Situação |
|---|---|
| Backup/restore operacional real (F0) | **Bloqueado por S1** (sem ambiente isolado/`pg_dump`). Runbook em `RUNBOOK_BACKUP_RESTORE.md`; execução real **não** declarada operacional. |
| Observabilidade ativa / rate limiting distribuído | Dependem de S1. |
| Decisões de produto D1/D2/D5, E1/E4, I1/I3, P1/P2/P4, S4 | Avançadas com **premissas conservadoras e reversíveis** (`DECISOES_EXECUCAO_AUTONOMA_NIT.md`); aguardam confirmação do product owner. |
| SSO e envio real de e-mail/SIGA/SEI | F5 entrega o **registro/outbox** (inerte por padrão); transporte real depende de infraestrutura e credenciais. |

---

## 7. Itens para validação do usuário

1. Confirmar as **decisões provisórias** adotadas em `DECISOES_EXECUCAO_AUTONOMA_NIT.md`
   (D1/D2/D5, E1/E4, I1/I3, P1/P2/P4, S1/S4).
2. Definir o **alvo de infraestrutura (S1)** para habilitar backup/restore real, observabilidade
   ativa e transporte de e-mail.
3. Validar as **regras de negócio** centrais: FORMICT como relatório interno (não oficial);
   vínculo startup↔ativo sem inferência de propriedade; pipeline de negociação que não altera
   contrato.
4. Aprovar (ou ajustar) os **rótulos e fluxos** de UX dos novos módulos de NIT.

---

## 8. Declaração de escopo

- **Código:** alterado de forma aditiva em `backend/app/**`, `backend/alembic/versions/**`,
  `backend/tests/**` e `frontend/src/**`.
- **Banco:** migrações **criadas** (11, head único) e validadas em banco isolado; nenhum dado de
  desenvolvimento foi destruído.
- **Configuração/deploy:** inalteradas. **Nenhum** commit, push ou deploy foi realizado.
- **Únicos artefatos de documentação:** este relatório, o log (`LOG_EXECUCAO_NIT.md`) e o controle
  de estado (`EXECUCAO_AUTONOMA_NIT.md`).

