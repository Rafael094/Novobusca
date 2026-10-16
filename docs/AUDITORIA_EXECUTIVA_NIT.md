# Auditoria Executiva — IntelliINPI → Plataforma SaaS de Gestão de NIT

**Data:** 2026-10-09
**Natureza:** Auditoria somente leitura. Nada foi implementado ou alterado.

---

## 1. Estado atual verificado

O IntelliINPI é hoje uma **plataforma funcional de pesquisa e inteligência em propriedade industrial** (marcas e patentes), multi-tenant, com base de dados real do INPI carregada localmente.

Evidências verificadas:

- **Backend funcional:** FastAPI com 10 routers e 44 endpoints declarados **[CÓDIGO]**.
- **Testes:** `pytest -q` → **94 testes, 94 aprovados** **[TESTE]**.
- **Base de dados real:** `marcas` = 6.645.491; `patentes` = 1.018.792 **[verificado por `SELECT count(*)`]**.
- **RBAC avançado:** 10 módulos, 52 permissões, 25 recursos, 8 papéis, três caminhos de concessão **[CÓDIGO]**.
- **Isolamento multi-tenant** derivado exclusivamente do token JWT **[CÓDIGO] + [TESTE]**.
- **Frontend:** Next.js 15 / React 19 / Tailwind / TanStack Query, 16 arquivos de página/contexto **[CÓDIGO]**.
- **ETL:** pipeline DuckDB → PostgreSQL, 18 datasets registrados **[CÓDIGO] + [DOC]**.

O que **não** existe: qualquer entidade de NIT (comunicação de invenção, projeto de P&D, contrato, licença, startup, documento). O modelo atual cobre **pesquisa de PI pública** + **CRM genérico**. **Não há módulo de NIT.**

---

## 2. Principais capacidades existentes (reaproveitáveis)

| Capacidade | Evidência | Reaproveitamento |
|---|---|---|
| Multi-tenancy por token | `app/deps.py`, `test_tenant_isolation.py` | **Direto** |
| RBAC com escopo Company/Unity | `app/rbac.py`, `models/rbac.py` | **Direto** |
| Auditoria persistente | `app/audit.py`, `AuditLog` | **Direto** |
| Monitoramento seletivo por usuário | `MarcaMonitoramento` | **Alto** |
| CRM (Company/Unity/Customer/Person) | `models/company.py`, `routers/clientes.py` | **Parcial** |
| DeepSeek com degradação explícita | `services/deepseek.py`, `routers/analises.py` | **Médio** |
| Ingestão INPI rastreável | `models/inpi.py`, `ingestion/load.py` | **Direto** |
| Testes de isolamento/RBAC | `backend/tests/` | **Direto** |

---

## 3. Lacunas prioritárias (visão executiva)

1. **Ausência total de modelos de NIT** **[CÓDIGO]**.
2. **Ausência de gestão documental** (anexos/confidencialidade) **[CÓDIGO]**.
3. **Ausência de workflow** (estados, alçadas, pareceres, comitês) **[CÓDIGO]**.
4. **Ausência de contratos/royalties** **[CÓDIGO]**.
5. **Ausência de portais externos** (pesquisador/empresa) **[CÓDIGO]**.
6. **Ausência de indicadores de NIT** **[CÓDIGO]**.
7. **Repositório sem git** **[verificado]**.
8. **Busca de marcas imprecisa** (`SPIKE_...` documenta divergência) **[DOC]**.
9. **Sem métricas de desempenho** **[PARCIAL]**.
10. **Rate limiting apenas no login** **[CÓDIGO]**.

---

## 4. Riscos críticos

| ID | Risco | Severidade | Evidência |
|---|---|---|---|
| R1 | Sem controle de versão (git) | **P0** | `git status` falha na raiz |
| R2 | Documentos confidenciais inexistentes → risco LGPD ao criar sem desenho | **P0** | ausência de modelo de documentos |
| R3 | Rate limiting só em `/auth/login`; busca global sem throttling | **P1** | `app/rate_limit.py` |
| R4 | Busca de marcas com `ILIKE '%x%'` sem `unaccent`/trigram explícito | **P1** | `routers/marcas.py::_base_query` |
| R5 | Segredos com defaults fracos (`dev-secret-change-me`) | **P1** | `app/config.py` |
| R6 | Token em `localStorage` (suscetível a XSS) | **P1** | `frontend/src/lib/api.ts` |
| R7 | Ausência de teste de concorrência e carga | **P2** | suíte atual |
| R8 | Sem backup/restore documentado | **P2** | ausência de script |

---

## 5. Potencial de reaproveitamento

O IntelliINPI **não deve ser reescrito**. A fundação (auth, tenancy, RBAC, auditoria, ingestão, testes) é sólida e testada. A evolução para NIT é **aditiva**: novos módulos de domínio sobre a mesma base, reusando:

- `TenantEntityMixin` + `tenant_id` em todo novo modelo;
- `require_permission()` para autorização;
- `record_audit()` para trilha;
- o padrão Next.js + TanStack Query.

---

## 6. Decisões pendentes (bloqueadoras)

1. **Público-alvo e tipo de instituição** (ICT única vs. rede multi-campus).
2. **Modelo comercial** (SaaS por assinatura vs. implantação institucional).
3. **Escopo do MVP** — qual domínio (A–K) entra primeiro.
4. **Modelo de confidencialidade documental** — storage e LGPD.
5. **Estratégia de workflow** — estados e alçadas (configurável por instituição?).
6. **Portais externos** — pesquisador e empresa autenticados no mesmo sistema?
7. **Integrações institucionais** (SIGA, SEI, sistemas de pesquisa).
8. **FORMICT / relatórios oficiais** — formatos obrigatórios.

Detalhamento em `QUESTIONARIO_DECISOES_PRODUTO_NIT.md`.

---

## 7. Recomendação geral

**Prosseguir com evolução incremental, não com reescrita.** Sequência recomendada:

1. **Fase 0 (fundação):** sanear governança (git, segredos, backup) e fechar o modelo de domínio.
2. **Fase 1 (MVP NIT):** Comunicação de Invenção + Ativos internos + documentos + workflow básico.
3. **Fase 2:** Avaliação/triagem + portfólio institucional.
4. **Fase 3:** Transferência tecnológica + contratos.
5. **Fase 4:** P&D, empreendedorismo, indicadores.
6. **Fase 5:** Portais externos e BI institucional.

Antes de qualquer linha de código nova, é **obrigatório** responder às decisões da seção 6 — elas alteram o modelo de domínio e o isolamento multi-tenant.

---

## 8. Encerramento

- **Investigado:** todo o backend, frontend, ingestão, migrações, testes (executados) e contagens do banco.
- **Relatórios produzidos:** 9 documentos em `intelliinpi/docs/` (ver `INDICE_AUDITORIA_NIT.md`).
- **Nenhuma funcionalidade foi implementada** e **nenhum código, configuração ou dado foi alterado**. As únicas escritas foram a criação dos 9 arquivos de relatório em `docs/` (pasta previamente vazia).
- **Sequência recomendada:** Fase 0 → Fase 1 (MVP) → demais fases conforme `ROADMAP_IMPLEMENTACAO_NIT.md`.
