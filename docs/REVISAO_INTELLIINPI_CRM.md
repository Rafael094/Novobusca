# Revisão IntelliINPI — CRM comercial, Visão Geral do negócio e redesign de navegação

**Data:** 2026-10-10
**Escopo:** Fases 1–9 do prompt master (auditoria, navegação, dashboard do negócio, CRM, design system, backend, testes)
**Restrições respeitadas:** sem commit/push/deploy, sem reset de banco, sem dados fictícios em migrations, sem dependências novas.

---

## 1. Resumo executivo

| Frente | Estado |
|---|---|
| Auditoria e mapeamento (Fase 1) | ✅ Completa — matriz recurso × situação × alteração entregue |
| Navegação (Fase 2) | ✅ Implementada — hierarquia Visão Geral / CRM / INPI / NIT; Administração fora da sidebar |
| Dashboard do negócio (Fase 3) | ✅ Implementado — 8 cartões, gráfico comercial, funil, propostas pendentes, prazos, atividade |
| CRM completo (Fase 4) | ✅ Implementado — oportunidades, propostas, atividades, conversão, detalhe do cliente |
| Redesign visual (Fase 5) | ⚠️ Parcial — design system centralizado (`PageHeader`, `StatCard`, `Funnel`) aplicado na Visão Geral, CRM e Monitoramento; telas NIT/INPI preservadas |
| Backend e dados (Fase 6) | ✅ Implementado — 19 endpoints novos, agregações tenant-scoped |
| Validação e testes (Fase 7) | ✅ **195 testes backend passando**; `tsc --noEmit` limpo; `npm run build` OK (44 rotas) |
| Validação no navegador (Fase 7) | ❌ **Não executada** — sem navegador automatizado disponível nesta sessão |
| Documentação (Fase 9) | ✅ Este documento + atualização do `CONTINUIDADE_PROXIMA_SESSAO_NIT.md` |

---

## 2. Auditoria — achados que motivaram o trabalho

1. **A Visão Geral mostrava o universo do INPI, não a operação do tenant.**
   `GET /api/dashboard/summary` executava `count(Marca)` / `count(Patente)` sem
   qualquer filtro de tenant (`app/routers/dashboard.py:49-50`) e o gráfico
   `portfolio_evolution` era composto por anos de depósito do INPI. Os rótulos da
   tela ("Últimos eventos do INPI", "Vigências mais próximas") confirmavam a
   leitura errada.

2. **Não existia nenhuma entidade comercial.** Nem proposta, nem oportunidade,
   nem funil, nem follow-up. `Company` / `Unity` / `Customer` / `Person`
   existiam com CRUD completo (`routers/clientes.py`, 745 linhas), mas eram um
   cadastro isolado, sem ciclo comercial.

3. **Administração ocupava um item de topo na sidebar** e era apenas ocultada
   por permissão no frontend — não havia guarda de rota.

4. **A navegação era plana:** 8 itens de primeiro nível + 17 filhos do NIT, sem
   agrupamento semântico.

---

## 3. Backend implementado

### 3.1 Novos arquivos

| Arquivo | Conteúdo |
|---|---|
| `backend/app/models/crm.py` | `CrmOpportunity`, `CrmProposal`, `CrmActivity` + vocabulários (etapas, status, transições, tipos de atividade, origens) |
| `backend/app/schemas/crm.py` | Create/Update/Out/paginados + `BusinessDashboard` e seus componentes |
| `backend/app/services/crm.py` | Códigos sequenciais (`OPP-000001`/`PRO-000001`), validação de transições, conversão lead→cliente anti-duplicidade, agregados do dashboard |
| `backend/app/routers/crm.py` | 18 endpoints sob `/api/crm` |
| `backend/alembic/versions/e1a2b3c4d5e6_add_crm_commercial.py` | 3 tabelas + índices + 7 permissões + 4 recursos (idempotente, `downgrade` real) |
| `backend/tests/test_crm_api.py` | 14 testes |

### 3.2 Endpoints novos (19)

```
GET    /api/crm/dashboard
GET    /api/crm/opportunities            POST   /api/crm/opportunities
GET    /api/crm/opportunities/{id}       PATCH  /api/crm/opportunities/{id}
DELETE /api/crm/opportunities/{id}       POST   /api/crm/opportunities/{id}/stage
POST   /api/crm/opportunities/{id}/convert
GET    /api/crm/proposals                POST   /api/crm/proposals
GET    /api/crm/proposals/{id}           PATCH  /api/crm/proposals/{id}
DELETE /api/crm/proposals/{id}           POST   /api/crm/proposals/{id}/status
GET    /api/crm/activities               POST   /api/crm/activities
PATCH  /api/crm/activities/{id}          DELETE /api/crm/activities/{id}
GET    /api/dashboard/business
```

`GET /api/dashboard/summary` foi **preservado** (contrato existente intacto).

### 3.3 Migração `e1a2b3c4d5e6`

* Tabelas `crm_opportunities`, `crm_proposals`, `crm_activities` com FKs
  `tenants`/`customers`/`companies`/`people`/`users` e índices
  `(tenant_id, stage)`, `(tenant_id, status)`,
  `(tenant_id, subject_type, subject_id)`, `(tenant_id, due_at)`.
* RBAC: permissões `CRM_DASHBOARD_VIEW`, `CRM_OPPORTUNITY_VIEW/_MANAGE`,
  `CRM_PROPOSAL_VIEW/_MANAGE`, `CRM_ACTIVITY_VIEW/_MANAGE`; recursos
  `clientes:opportunity`, `clientes:proposal`, `clientes:activity`,
  `clientes:crm_dashboard`.
* **Sem dados de demonstração.** Inserts idempotentes com `CAST(:param AS ...)`
  para evitar inferência ambígua de tipo do psycopg.
* `downgrade()` remove tabelas, índices e as linhas de RBAC introduzidas —
  validado pelo teste de round-trip de migração.

### 3.4 Regras de negócio impostas no backend

* `WON` exige cliente vinculado (409 caso contrário) — a conversão é o caminho.
* `LOST` exige motivo (422 caso contrário).
* Transições validadas contra `OPPORTUNITY_TRANSITIONS` / `PROPOSAL_TRANSITIONS`
  (409 fora da máquina de estados).
* `sent_at` / `replied_at` / `decision_at` são carimbados pelo servidor — **nunca**
  pelo frontend.
* **Aprovar uma proposta não cria marca nem patente** e não executa serviço
  (teste dedicado garante que o monitoramento do tenant fica intacto).
* Conversão: busca por documento → e-mail → nome antes de criar cliente novo;
  acha e reutiliza. Vincula as propostas da oportunidade na mesma transação.
* Referências cross-tenant em `customer_id` / `company_id` / `contact_id` /
  `owner_id` / `subject_id` → **422**.
* Acesso por ID a registro de outro tenant → **404** (indistinguível de
  inexistente, nos endpoints de CRM assim como em `clientes`).

---

## 4. Frontend implementado

### 4.1 Navegação (`components/AppShell.tsx`)

```
Visão Geral
CRM / Clientes  ▾   Visão comercial · Leads e oportunidades · Propostas comerciais
                    Atividades e follow-ups · Clientes e empresas
INPI            ▾   Marcas · Patentes · Monitoramento · Análises de IA · Relatórios
NIT             ▾   (17 módulos existentes, inalterados)
```

* Administração **removida da sidebar**; acessível pelo dropdown do usuário.
* `findActiveGroup` / `findActiveLabel` fazem match por prefixo mais longo, com
  destaque do grupo e do subitem ativo.
* O grupo expandido persiste ao navegar; clique em grupo inativo leva à
  `GROUP_LANDING` (`/inpi` → `/marcas`) evitando rota inexistente.
* Sidebar responsiva preservada (overlay mobile inalterado).

### 4.2 Componentes novos

| Componente | Papel |
|---|---|
| `components/PageHeader.tsx` | Título + descrição + ações padronizadas (telas novas) |
| `components/StatCard.tsx` | Cartão de indicador: valor, detalhe, período, tom, navegação opcional |
| `components/Funnel.tsx` | Funil com barras proporcionais e clique por etapa |
| `components/UserMenu.tsx` | Dropdown do usuário; "Administração" só com permissão |

### 4.3 Páginas novas

| Rota | Conteúdo |
|---|---|
| `/crm` | Visão comercial: cartões, propostas que precisam de ação, funil, período |
| `/crm/oportunidades` | Tabela + filtros + criação + converter/perder (com motivo) |
| `/crm/propostas` | Ciclo completo: registrar envio, registrar retorno, negociar, aprovar, recusar |
| `/crm/atividades` | Follow-ups com conclusão e filtro de pendentes |
| `/clientes/[id]` | Detalhe: dados cadastrais, oportunidades, propostas, atividades |
| `admin/layout.tsx` | Guarda de rota administrativa com mensagem de acesso restrito |

### 4.4 Visão Geral reescrita (`app/dashboard/page.tsx`)

Consome exclusivamente `GET /api/dashboard/business`:

* **8 cartões**: clientes ativos, oportunidades em negociação, propostas a enviar,
  propostas aguardando retorno, propostas aprovadas, marcas monitoradas,
  patentes monitoradas, alertas críticos.
* **Gráfico de evolução comercial** (clientes, enviadas, aprovadas, ganhas) com
  12/24 meses — série real, ou **estado vazio explícito** quando não há histórico.
* **Funil de vendas** clicável.
* **Propostas que precisam de ação**, priorizadas: vencida → a enviar → aprovada
  sem cliente → aguardando retorno → vence em breve.
* **Próximos prazos**, com `domain` separando `COMMERCIAL` de
  `PROPRIEDADE_INTELECTUAL` (badges distintas).
* **Atividade recente** real (clientes, oportunidades, propostas, follow-ups,
  monitoramento).
* `conversion_rate` é `null` quando não há decisões — a UI mostra
  "sem histórico decisório" em vez de inventar um percentual.

### 4.5 Outras telas

* **Monitoramento**: estado vazio reescrito com explicação do modelo seletivo,
  benefícios e CTAs para `/marcas` e `/patentes`.
* **Clientes**: coluna "Abrir" leva ao detalhe.
* **Relatórios / Análises / NIT**: **preservados** sem alteração funcional.


---

## 5. Testes e validação

| Verificação | Comando | Resultado |
|---|---|---|
| Suíte backend | `.venv\Scripts\python.exe -m pytest tests` | **195 passed, 0 failed** (era 181; +14 CRM) |
| CRM isolado | `pytest tests/test_crm_api.py -q` | 14 passed |
| Migração round-trip | `pytest tests/test_nit_migration.py -q` | 1 passed |
| TypeScript | `npx tsc --noEmit` | exit 0, sem erros |
| Build produção | `npm run build` | ✅ 44 rotas (era 37) |
| Alembic heads | `.venv\Scripts\alembic.exe heads` | `e1a2b3c4d5e6` (head único) |

### Cobertura dos testes CRM

* permissões (403 sem papel), isolamento em list/get/update/delete/convert;
* referência cross-tenant rejeitada (422) em oportunidade e atividade;
* códigos sequenciais por tenant;
* funil: caminho feliz + `WON` sem cliente (409) + `LOST` sem motivo (422) +
  transição ilegal (409) + `LOST` registra motivo;
* propostas: transição ilegal (409), `sent_at`/`replied_at`/`decision_at`
  carimbados, códigos sequenciais, **aprovar não cria PI**;
* conversão: reutiliza cliente existente por documento normalizado
  (`12345678000199` ≡ `12.345.678/0001-99`), vínculo a cliente existente com
  back-fill das propostas;
* dashboard: contadores tenant-scoped, tenant vazio devolve tudo zero,
  `conversion_rate` `null` sem decisões, funil sempre com 7 etapas na ordem,
  12/24 buckets de evolução, `pending_proposals` com `reason`, atividade recente
  ordenada, `months=99` → 422.

### Validação em navegador — NÃO EXECUTADA

Não havia navegador automatizado disponível nesta sessão. A validação ficou
restrita a `tsc` + `build` + suíte backend. Os 15 passos da Fase 7 permanecem
**pendentes** e devem ser executados manualmente com os servidores dev ativos.

---

## 6. Limitações e integrações pendentes

| Item | Situação |
|---|---|
| PDF de proposta, envio por e-mail, assinatura eletrônica, cobrança | **Não implementados.** A tela de propostas declara isso em faixa de aviso; nenhuma simulação é feita |
| Integração automática de e-mail/WhatsApp para follow-ups | Não implementada — a tela apenas *registra* interações realizadas |
| Empresa Teste (`conftest.py`) | Fixture de teste, não tocada pelo seed nem pelo CRM |
| `interest_interactions.kind/summary/actor_id` (drift NIT) | Dívida técnica pré-existente, inalterada |
| S3/MinIO, backup/restore | Bloqueios de infraestrutura pré-existentes |

---

## 7. Riscos remanescentes

1. **Validação funcional no navegador pendente** (risco médio) — os fluxos foram
   exercitados por testes de API, não por clique real.
2. **`to_char` com literal em SQL** (`app/services/crm.py`) — o formato é passado
   como `literal_column` porque, como parâmetro, o Postgres rejeita o `GROUP BY`
   (parâmetros distintos em SELECT e GROUP BY). Comentado no código.
3. **Códigos sequenciais** derivam do `count()` do tenant e são protegidos pelo
   UNIQUE `(tenant_id, code)`; em concorrência alta o segundo request recebe 409
   e o operador repete. Documentado no serviço (fluxo humano, baixo volume).
4. **Design system não aplicado a todas as telas** — Marcas, Patentes, Análises e
   Relatórios mantêm o layout anterior (preservação deliberada).

---

## 8. Estado do Git

Nenhum commit, push, merge ou deploy foi executado.

**Modificados:**
```
backend/app/constants.py
backend/app/models/__init__.py
backend/app/routers/__init__.py
backend/app/routers/dashboard.py
frontend/src/components/AppShell.tsx
frontend/src/app/dashboard/page.tsx
frontend/src/app/monitoramento/page.tsx
frontend/src/app/clientes/page.tsx
frontend/src/lib/types.ts
frontend/src/lib/hooks.ts
docs/CONTINUIDADE_PROXIMA_SESSAO_NIT.md
docs/REVISAO_INTELLIINPI_CRM.md (novo)
```

**Novos (não rastreados):**
```
backend/alembic/versions/e1a2b3c4d5e6_add_crm_commercial.py
backend/app/models/crm.py
backend/app/schemas/crm.py
backend/app/services/crm.py
backend/app/routers/crm.py
backend/tests/test_crm_api.py
frontend/src/components/PageHeader.tsx
frontend/src/components/StatCard.tsx
frontend/src/components/Funnel.tsx
frontend/src/components/UserMenu.tsx
frontend/src/app/admin/layout.tsx
frontend/src/app/crm/page.tsx
frontend/src/app/crm/oportunidades/page.tsx
frontend/src/app/crm/propostas/page.tsx
frontend/src/app/crm/atividades/page.tsx
frontend/src/app/clientes/[id]/page.tsx
```

---

## 9. Próximos passos recomendados

1. **Executar a validação funcional no navegador** (15 passos da Fase 7).
2. Aplicar o design system (`PageHeader` + `Card`) às telas de Marcas, Patentes,
   Análises e Relatórios — hoje preservadas.
3. Avaliar a promoção de `OPPORTUNITY_SOURCES` / `activity kinds` para um
   catálogo configurável por tenant.
4. Reforçar `test_proposal_is_not_a_registered_trademark` para asserir
   explicitamente que nenhuma linha em `marcas`/`patentes` foi criada.

---

## 10. Pendência imediata de infraestrutura

A migração `e1a2b3c4d5e6` **ainda não foi aplicada ao banco de desenvolvimento**.
Para ativar o CRM no ambiente dev:

```bash
cd backend
.venv/Scripts/alembic.exe upgrade head
```

Até isso ser feito, `/api/crm/*` e `/api/dashboard/business` respondem com erro
de tabela inexistente. Testes e migração round-trip já validam o script.
