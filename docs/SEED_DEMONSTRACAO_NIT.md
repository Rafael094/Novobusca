# Seed de Demonstração NIT (F1–F5)

**Data:** 2026-10-10
**Módulo:** `backend/app/seed_demo_nit.py`
**Objetivo:** Popular o banco de desenvolvimento com uma base demonstrativa
coerente, **cross-referenciada**, **isolada por tenant** e **idempotente**,
cobrindo todas as fases F1–F5 do NIT.

---

## 1. Como executar

```powershell
cd intelliinpi\backend
.\.venv\Scripts\python.exe -m app.seed_demo_nit
```

O comando imprime um relatório JSON com os identificadores do tenant demo, dos
atores, os papéis/permissões resolvidos por RBAC e os contadores
`created` / `reused` por fase e por entidade.

Via código:

```python
from app.db import SessionLocal
from app.seed_demo_nit import run_demo_seed

with SessionLocal() as db:
    report = run_demo_seed(db)        # commit=True por padrão
```

**Pré-requisito:** o seed base (`app.seed`) já deve ter sido executado, pois o
módulo reutiliza os `Module` (`NIT`) e `Role` globais já existentes. Caso
contrário ele falha com mensagem explícita
(`"Módulo NIT não encontrado; rode app.seed antes."`).

---

## 2. Garantias de projeto

| Garantia | Como é obtida |
| --- | --- |
| **Idempotência** | Todo registro tem identificador estável (protocolo, `code`, e-mail, `(tenant, code)`); re-execuções apenas **reutilizam**. Nada é apagado. |
| **Isolamento por tenant** | Todo dado é gravado sob um único tenant demo resolvido por `social_reason = "Instituto Demo NIT"`. Validação: nenhuma linha NIT aponta para outro tenant. |
| **Trilha de auditoria autêntica** | `WorkflowInstance`, `WorkflowHistory` e `Evaluation` **nunca** são inseridos por ORM direto: são produzidos pelos serviços reais `seed_nit.seed_tenant_workflow` e `services.workflow.apply_transition`. |
| **Sem dado inventado** | Valores monetários/legais só existem quando o demo realmente os representa (montantes marcados como demonstração). Prazos legais fabricados não são criados. |
| **Integrações/e-mails inertes** | `EmailMessage` permanece `QUEUED` e `IntegrationEndpoint` permanece `enabled=False`; nenhuma chamada externa é feita. |

### Regra de arquitetura

```
Domínio (FK em ordem)            →  inserção ORM direta
Técnico (workflow, avaliação)    →  APENAS via serviços reais
```

---

## 3. Atores do tenant demo

Senha única (hash via `security.hash_password`): `Demo_Nit_2026!`

| Papel | Usuário | E-mail | Permissões NIT |
| --- | --- | --- | --- |
| `NIT_RESEARCHER` | Dra. Helena Prado | helena.prado@demo.nit.br | 7 |
| `NIT_ANALYST` | Rafael Coutinho | rafael.coutinho@demo.nit.br | 11 |
| `NIT_MANAGER` | Mariana Alves | mariana.alves@demo.nit.br | 58 |
| `NIT_TT_OPERATOR` | Bruno Tavares | bruno.tavares@demo.nit.br | 19 |
| `NIT_COMMITTEE_MEMBER` | Prof. Sérgio Bastos | sergio.bastos@demo.nit.br | 10 |

Os papéis são atribuídos por `UserRole` sobre os `Role` globais (`tenant_id IS NULL`).

---

## 4. Conteúdo semeado por fase

### Fundação
Tenant, `Company`, `Unity` (Campus Central / MATRIZ), 5 usuários + `Person` +
`UserTenant`, e habilitação de **todos** os módulos ativos (`TenantModule`).

### F1 — Comunicação de invenção
- 5 `InventionDisclosure`s com protocolo gerado por `services.protocol.next_protocol`
  (prefixo `DEMO_PROTOCOL_TITLES`), em estados distintos:
  `PROPOSAL`, `TRIAGE`, `EVALUATION`, `DECISION`, `CLOSED`.
- 10 `DisclosureInventor` (interno 60 % + externo 40 %), 10 `InventionDocument`,
  20 `DocumentAcl` (sujeitos `ROLE` e `UNITY`).
- 5 `WorkflowInstance` e 10 `WorkflowHistory` criados **pelas transições reais**;
  ator correto por transição (analista em TRIAGE/EVALUATION, gestor em
  DECISION/CLOSED com justificativa obrigatória).
- 7 `Evaluation` (técnica, jurídica, comercial) via fluxo do serviço.
- 2 `IPAsset` (patente protegida + software) e 2 `IPAssetPublicLink`.

### F2 — Comitês, TRL e portfólio
- 1 `Committee` ativo, 4 `CommitteeMember`, 2 `CommitteeMeeting` realizadas,
  2 `CommitteeAgendaItem` decididos, 5 `CommitteeVote` (aprovando),
  2 `CommitteeDecision`.
- 3 `TechnologyReadinessLevel` (histórico TRL) registrados via serviço.

### F3 — Transferência de tecnologia
- 2 `TechnologyOffer` publicadas, 2 `ExpressionOfInterest`
  (`CONVERTED` / `IN_NEGOTIATION`), 2 `InterestInteraction`.
- 1 `Negotiation` (fase `CLOSED`) + 5 `NegotiationHistory` cobrindo todas as
  etapas (`QUALIFICATION → FIRST_CONTACT → TECHNICAL → NEGOTIATION → CLOSED`).
- 1 `License`, 1 `Contract` ativo, 2 `ContractParty`, 2 `ContractObligation`,
  2 `Royalty`.

### F4 — Projetos de P&D, startups e incubação
- 1 `Project` (`PRJ-0001`) + 2 `ProjectMember`, 1 `ProjectFunder`,
  2 `ProjectMilestone` (DONE/PENDING), 1 `ProjectAssetLink` (relação `RESULT`).
- 1 `Startup` (`STP-0001`, `INCUBATED`) + 2 `StartupMember` fundadores.
- 1 `IncubationProgram` (`INC-2025`), 1 `IncubationParticipation`,
  2 `IncubationStage` (COMPLETED / IN_PROGRESS).

### F5 — Notificações, portais, BI e integrações
- 3 `Notification` (in-app) e 3 `NotificationPreference`.
- 2 `EmailMessage` em `QUEUED` (outbox — sem transporte real).
- 2 `ExternalPortalAccess` (`COMPANY` / `RESEARCHER`) com `access_token`
  determinístico de 64 caracteres (UUID v5 do e-mail).
- 1 `PortalRequest` triado + 1 `PortalRequestNote`.
- 1 `SavedReport` + 1 `ReportRun` (resultado congelado de demonstração).
- 2 `IntegrationEndpoint` (SIGA / SEI, **desabilitados**) + 2
  `IntegrationDelivery` em `PENDING`.

---

## 5. Prova de idempotência

Execução em `intelliinpi_app` (dev):

| Execução | `created` | `reused` |
| --- | --- | --- |
| 1ª | 176 | 0 |
| 2ª | 0 | 140 |
| 3ª (`python -m app.seed_demo_nit`) | 0 | 140 |

A 2ª/3ª execução recriam **nada**. A diferença entre 176 e 140 corresponde a
resíduos de primeira execução que não fazem parte do mapa de reuso explícito
(por exemplo, dependências internas dos serviços de workflow/avaliação), sem
qualquer duplicação: as contagens de tabela permanecem estáveis entre execuções
(46 tabelas, 142 linhas, `workflow_history = 10`, `evaluations = 7`).

Contagens após a estabilização (todas sob o tenant demo):

| Tabela | Linhas | Tabela | Linhas |
| --- | --- | --- | --- |
| `invention_disclosures` | 5 | `projects` | 1 |
| `workflow_history` | 10 | `startups` | 1 |
| `evaluations` | 7 | `incubation_stages` | 2 |
| `document_acls` | 20 | `nit_notifications` | 3 |
| `trl_history` | 3 | `nit_portal_access` | 2 |
| `committee_votes` | 5 | `nit_integration_endpoints` | 2 |
| `negotiation_history` | 5 | `nit_email_messages` | 2 |

---

## 6. Validação executada

- Reconhecimento de todas as constantes/colunas dos modelos F1–F5.
- Verificação de isolamento: `LEAK` (linhas fora do tenant demo) → **nenhum**.
- Integridade referencial: `orphan disclosures = 0`.
- Suíte de testes do NIT: `test_nit_f1..f5`, `test_nit_migration`,
  `test_nit_storage` → **72 passando**.
- Suíte completa do backend: **181 passed**, 0 falhas.

---

## 7. Observações e dívidas técnicas

1. **Drift modelo × banco em `interest_interactions`.** A tabela física possui
   as colunas `kind` (NOT NULL) e `summary` (NOT NULL) que **não** estão
   mapeadas em `app/models/nit_f3.py`. O seed contorna a lacuna com `INSERT`
   via SQL explícito (`text(...)`). *Recomendação para sessão futura:* mapear
   essas colunas no modelo (ou alinhar a migração) e voltar a usar ORM.
2. **`Empresa Teste`.** Registro deixado por `tests/conftest.py`; o seed demo
   **não** o toca nem depende dele.
3. **`enabled=False` nas integrações.** Deliberado: os endpoints permanecem
   inertes até que um adaptador real seja configurado.
4. **Segredos.** O seed cria apenas hashes de senha de demonstração e tokens de
   portal determinísticos; nenhum segredo real é gravado.

