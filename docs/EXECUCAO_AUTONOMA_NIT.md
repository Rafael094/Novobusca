# Execução Autônoma NIT — Controle de Estado

**Início:** 2026-10-09 · **Natureza:** execução autorizada de F1–F5 (implementação real).
**Escopo:** evoluir IntelliINPI para plataforma SaaS de gestão de NIT preservando 100% do
sistema atual (marcas, patentes, CRM, análise por IA, ingestão INPI, auth, RBAC, monitoramento).

> Documento de **retomada**: permite reiniciar a execução após interrupção sem repetir alterações.
> Nenhum segredo, token ou dado pessoal é registrado aqui.

---

## 1. Estado atual

| Fase | Status | Observação |
|---|---|---|
| **F0** | ✅ CONCLUÍDA (parcial operacional) | R-04/R-08/R-10/500-safe/409 implementados; backup real bloqueado por S1 |
| **F1** | ✅ CONCLUÍDA | 11 tabelas, 24 endpoints, 9 telas; 134 testes; tsc+build OK |
| **F2** | ✅ CONCLUÍDA | +7 tabelas, +14 endpoints, comitês/TRL/portfólio; 147 testes; tsc+build OK |
| **F3** | ✅ CONCLUÍDA | +10 tabelas, contratos/royalties/TT; 158 testes; tsc+build OK |
| **F4** | ✅ CONCLUÍDA | +10 tabelas, projetos P&D/startups/incubação/indicadores/FORMICT; 168 testes; tsc+build OK |
| **F5** | ✅ CONCLUÍDA | +10 tabelas, notificações/portais externos/BI/integrações/TS-types; 181 testes; tsc+build OK |

**Baseline verificado:** suíte PHPytest = **109 passed** (94 originais + 15 F0). Frontend
`tsc --noEmit` = 0, `next build` = 0. Branch: `main`. Sem commit/push/deploy.

---

## 2. Decisões adotadas para avanço (provisórias, reversíveis)

Ver detalhamento e justificativa em `DECISOES_EXECUCAO_AUTONOMA_NIT.md`. Resumo:

| ID | Decisão provisória adotada | Reversível? |
|---|---|---|
| D1 | 4 níveis de sigilo: `PUBLIC`, `INTERNAL`, `RESTRICTED`, `CONFIDENTIAL` | Sim (enum configurável) |
| D2 | Storage abstrato com adaptador **local privado** (`services/storage.py`); S3/MinIO plugável | Sim (interface) |
| D5 | Auditoria de todo download de documento não-público | Sim |
| E1 | Workflow `PROPOSAL→TRIAGE→EVALUATION→DECISION→CLOSED` configurável por tenant | Sim (seed) |
| E4 | Alçada por permissão/role na transição (nunca implícita) | Sim |
| I1/I3 | `IPAsset` interno com `IPAssetPublicLink` **opcional** (sem FK dura) | Sim |
| P1/P2/P4 | Tenant = instituição; `Unity` = campus/departamento; portfólio do tenant com escopo por unidade | Sim |
| S1 | Não decidido → nada dependente de infra é declarado operacional | — |
| S4 | Não decidido → documentação preparada, sem declarar conformidade LGPD | — |

---

## 3. Tarefas F1 (checklist)

### 3.1 Backend
- [ ] `app/constants.py`: módulo `NIT`, permissões `NIT_*`, recursos `nit:*`, roles NIT
- [ ] `app/models/nit.py`: `InventionDisclosure`, `DisclosureInventor`, `InventionDocument`,
      `DocumentAcl`, `WorkflowState`, `WorkflowTransition`, `WorkflowInstance`, `Evaluation`,
      `IPAsset`, `IPAssetPublicLink`
- [ ] `app/schemas/nit.py`
- [ ] `app/services/protocol.py` (protocolo único concorrente-seguro)
- [ ] `app/services/storage.py` (abstração + adaptador local privado, MIME/magic bytes)
- [ ] `app/services/workflow.py` (máquina de estados + alçadas)
- [ ] `app/routers/nit/*` (disclosures, documents, workflow, assets)
- [ ] Migration aditiva + downgrade funcional
- [ ] `app/seed_nit.py` (estados/transições padrão por tenant)

### 3.2 Testes
- [ ] Isolamento tenant + unidade
- [ ] ACL de documento (positivo/negativo)
- [ ] Protocolo concorrente
- [ ] Transições válidas/inválidas + alçadas
- [ ] Vínculo público
- [ ] MIME/tamanho

### 3.3 Frontend
- [ ] `src/lib/api.ts` + `types.ts` (tipos NIT)
- [ ] `src/app/nit/*` (comunicações, dossiê, documentos, ativos, dashboard)
- [ ] Agrupamento no `AppShell.tsx`

### 3.4 Gate F1
- [ ] Suíte completa verde · `tsc` + `build` · regressão módulos públicos

---

## 4. Histórico de marcos

| # | Marco | Data | Evidência |
|---|---|---|---|
| 1 | Baseline verificado (109 passed) | 2026-10-09 | `pytest -q` |
| 2 | Registro de execução criado | 2026-10-09 | este arquivo |
