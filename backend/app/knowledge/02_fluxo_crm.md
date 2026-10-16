# Fluxo — CRM Comercial

## Objetivo

Gerenciar o funil comercial: leads/oportunidades → propostas → fechamento (ganho ou
perda), com registro de atividades de follow-up. Modelos em
`backend/app/models/crm.py`; serviço com as regras em `backend/app/services/crm.py`;
API em `backend/app/routers/crm.py`.

## Entidades

- **CrmOpportunity** (oportunidade/lead)
- **CrmProposal** (proposta comercial)
- **CrmActivity** (atividade de follow-up)

## Fluxo narrativo

1. **Captação:** uma oportunidade é criada (`POST /api/crm/opportunities`) com
   título, cliente/empresa/pessoa relacionada, origem, valor estimado e estágio
   inicial `NEW`.
2. **Qualificação:** a equipe avança o estágio conforme o funil
   (`PATCH /api/crm/opportunities/{id}/stage`).
3. **Proposta:** gera-se uma proposta vinculada à oportunidade
   (`POST /api/crm/proposals`) em status `DRAFT`.
4. **Envio e resposta:** a proposta evolui de rascunho para enviada e depois para
   aceita/recusada.
5. **Fechamento:** ao marcar a oportunidade como ganha, **o cliente é obrigatório**;
   ao marcar como perdida, **o motivo é obrigatório** (regra no serviço). Ao ganhar
   com proposta aceita, a proposta é convertida em contrato/projeto quando aplicável.
6. **Follow-up:** atividades (ligações, reuniões, e-mails, notas, tarefas) são
   registradas ao longo de todo o processo (`POST /api/crm/activities`).

## Estágios do funil (`OPPORTUNITY_STAGES`, em ordem)

`NEW` → `QUALIFICATION` → `PROPOSAL` → `NEGOTIATION` → `WON` / `LOST`

- Estágios terminais: **WON** (ganho) e **LOST** (perdido).
- **WON** exige `customer_id`; **LOST** exige `loss_reason`.

## Status da proposta (`PROPOSAL_STATUSES`)

`DRAFT` → `PENDING_SEND` → `SENT` → `ACCEPTED` / `REJECTED` / `EXPIRED` /
`CANCELLED`.

- Abertos: `DRAFT`, `PENDING_SEND`, `SENT`.
- Fechados: `ACCEPTED`, `REJECTED`, `EXPIRED`, `CANCELLED`.

## Tipos de atividade (`ACTIVITY_KINDS`)

`CALL` (ligação), `MEETING` (reunião), `EMAIL`, `NOTE` (nota), `TASK` (tarefa),
`OTHER` (outro).

## Resultados de atividade (`ACTIVITY_OUTCOMES`)

`PENDING` (pendente), `DONE` (concluída), `NO_ANSWER` (sem resposta),
`RESCHEDULED` (reagendada).

## Telas relacionadas

- Visão comercial: `/crm`
- Oportunidades: `/crm/oportunidades`
- Propostas: `/crm/propostas`
- Atividades: `/crm/atividades`

## Perguntas típicas e onde encontrar

- **"Onde vejo meus clientes?"** → `/clientes` (menu CRM / Clientes → Clientes e
  empresas). API: `GET /api/clientes/customers`.
- **"Como marco uma oportunidade como ganha?"** → altere o estágio para `WON`; o
  sistema exige um cliente associado.
- **"Por que não consigo perder sem motivo?"** → o estágio `LOST` exige
  `loss_reason` (regra de integridade de dados).
