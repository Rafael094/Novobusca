# Plano Mestre de Evolução — IntelliINPI → Plataforma SaaS de Gestão de NIT

**Data:** 2026-10-09
**Natureza:** Consolidação de planejamento. **Nenhuma implementação, migração, refatoração ou alteração de banco foi executada.**
**Base:** nove relatórios em `intelliinpi/docs/` (ver `INDICE_AUDITORIA_NIT.md`) + inspeção somente leitura do repositório em 2026-10-09.

> Este é o documento-âncora. Os demais documentos do plano desdobram seções específicas e **não duplicam** o conteúdo integral das auditorias.

---

## 1. Sumário executivo

O IntelliINPI é hoje uma **plataforma funcional de pesquisa e inteligência em propriedade industrial** (marcas e patentes), multi-tenant, com base real do INPI carregada e fundação de segurança testada. Ele **não é** um sistema de NIT: não existe nenhuma entidade de NIT (comunicação de invenção, ativo institucional, contrato, licença, projeto, documento, workflow).

**Tese central:** a evolução para plataforma de NIT é **aditiva**, não uma reescrita. A fundação (tenancy por token, RBAC granular com escopo Company/Unity, auditoria persistente, ETL rastreável, 94 testes verdes) deve ser preservada e estendida.

**Recomendação:** executar **F0 (fundação/governança) → F1 (MVP de comunicação de invenção + documentos confidenciais + workflow + ativos internos)**, validar com instituição-piloto, e só então decidir F2+ conforme gatilhos de negócio.

**Está pronto para implementação?** Não integralmente. F0 pode iniciar imediatamente. F1 depende de **5 decisões bloqueadoras** (confidencialidade/storage, workflow/alçadas, tipos de ativo/vínculo público, estrutura institucional/escopo, infraestrutura/LGPD) — ver `DECISOES_PENDENTES_PRODUTO.md`.

---

## 2. Correções em relação às auditorias originais (evidência nova)

A inspeção desta etapa **contradiz** um achado central e **confirma** os demais:

| Achado da auditoria | Estado verificado em 2026-10-09 | Ação no plano |
|---|---|---|
| "Não é repositório git" (R1/S2/T1, P0) | **CORRIGIDO.** Existe repositório git na raiz: commit `7a32c4b` ("first commit", autor Rafael Moura, 2026-10-09 06:49 -03), com **130 arquivos versionados**. Apenas `docs/` está não rastreado (`?? docs/`). | Rebaixar o risco de código para **residual**: falta *remote* e *proteção de branch*. Ver `MATRIZ_PRIORIDADES_E_RISCOS.md` (R-02). |
| `.gitignore` protege dados e segredos | **CONFIRMADO.** Ignora `.env`, `data/raw`, `data/extracted`, `data/processed`, `node_modules`, `.next`, `__pycache__`, `.venv`, `reports/*.json`, `reports/*.csv`. | Manter. Verificar que `.env` real nunca foi commitado. |
| 94 testes aprovados | **CONFIRMADO.** `pytest --collect-only` → **94 testes coletados**; `pytest -q` → 100% aprovados. | Manter como gate de regressão. |
| ~6,6M marcas / 1M patentes | **CONFIRMADO.** `marcas` = 6.645.491; `patentes` = 1.018.792. | Manter como critério de volumetria. |
| Segredos default (`dev-secret-change-me`) | **CONFIRMADO.** `config.py` mantém defaults fracos. | Risco permanece **P1**. Ver `PLANO_SEGURANCA_E_PRODUCAO.md` (S-04). |
| Token em `localStorage` | **CONFIRMADO.** `frontend/src/lib/api.ts` usa `localStorage`. | Risco permanece **P1**. |
| Rate limiting só no login | **CONFIRMADO.** `app/rate_limit.py` é in-memory e usado apenas no login. | Risco permanece **P1**. |

> **Consequência para o plano:** um dos três P0 originais (git) **já foi mitigado** pelo próprio responsável. Restam **dois P0 arquiteturais**: escopo intra-tenant (Company/Unity não aplicado a dados) e o desenho de documentos confidenciais.

---

## 3. Estratégia de produto

### 3.1 O que o IntelliINPI já entrega (com valor comercial)
Pesquisa de marcas (6,6M) e patentes (1M) com filtros, exportação e logos; monitoramento seletivo por usuário; análise de risco de marca por IA (DeepSeek, degradação explícita 503); CRM básico (empresa/unidade/cliente/pessoa); administração multi-tenant com RBAC avançado; ingestão rastreável de datasets do INPI.

### 3.2 O que falta para ser um NIT
Ver `MATRIZ_PRIORIDADES_E_RISCOS.md` §matriz funcional e `MATRIZ_ADERENCIA_FUNCIONAL_NIT.md`. Em uma frase: **todo o ciclo de vida interno da inovação** — da comunicação de invenção ao contrato de transferência, com confidencialidade, workflow e indicadores.

### 3.3 MVP proposto
Núcleo: comunicação de invenção (com inventores externos sem conta), anexos com confidencialidade e ACL, workflow de triagem/avaliação/decisão, ativo institucional com vínculo **opcional** a registro público, escopo por instituição/unidade, histórico e dashboard operacional.

### 3.4 Fora do MVP (com gatilho de retomada)
BI avançado · portais externos completos · integrações institucionais (SIGA/SEI) · financeiro abrangente/contabilidade de royalties · ecossistema de startups · personalização irrestrita de workflow. Gatilhos em `ROADMAP_EXECUCAO_NIT.md`.

---

## 4. Princípios arquiteturais não negociáveis

1. **Preservar a stack:** FastAPI + SQLAlchemy + PostgreSQL + Alembic + Next.js 15/React 19/Tailwind/TanStack Query. Nenhuma migração para .NET é recomendada; nenhuma reescrita é recomendada.
2. **Aditividade:** mudanças de schema são novas tabelas/colunas; tabelas existentes não são reestruturadas sem necessidade demonstrada + plano de dados.
3. **Tenant do token, sempre:** `tenant_id` nunca vem do corpo/query do cliente; escopo é validado no backend.
4. **Escopo em profundidade:** toda entidade interna carrega `tenant_id`; ativos internos também respeitam escopo Company/Unity.
5. **Reuso dos padrões comprovados:** `TenantEntityMixin`, `UUIDPrimaryKeyMixin`/`TimestampMixin`/`SoftDeleteMixin`, `require_permission()`, `record_audit()`, padrão Next.js + TanStack Query.
6. **Sem abstrações prematuras:** sem CQRS, event sourcing ou mensageria enquanto o negócio não exigir.
7. **Separação de conceitos:** registro público ≠ ativo interno ≠ comunicação ≠ processo ≠ contrato.
8. **Observabilidade e reversibilidade:** logging estruturado, backup testado, migrações pequenas com rollback.

Detalhamento técnico em `ARQUITETURA_ALVO_NIT.md`.

---

## 5. Inventário de ativos a preservar

| Ativo | Localização verificada | Como será reutilizado na evolução |
|---|---|---|
| Multi-tenancy por token | `app/deps.py::get_current_user`, `app/rbac.py::build_access_context` | Toda entidade NIT herda `tenant_id` e o escopo derivado do usuário. |
| RBAC (3 caminhos, DENY-wins) | `app/rbac.py`, `app/models/rbac.py`, `app/constants.py` | Novos módulos/recursos/permissões `NIT_*` no catálogo existente (sem schema novo). |
| Escopo Company/Unity | `AccessContext.scoped_resources`, `UserCompanyUnity` | Aplicado aos ativos internos (hoje só resolvido, não imposto). |
| Auditoria | `app/audit.py::record_audit`, `AuditLog` | Registra submissões, downloads, transições e decisões de NIT. |
| Soft delete + timestamps + UUID | `app/mixins.py` | Mixins obrigatórios em toda tabela nova. |
| CRM (Company/Unity/Customer/Person) | `app/models/company.py`, `app/routers/clientes.py` | Base para empresas parceiras, inventores (`Person` sem conta) e titulares. |
| Monitoramento seletivo | `MarcaMonitoramento`/`PatenteMonitoramento` | Padrão reaproveitado para alertas de NIT (prazos/anuidades). |
| PI pública (marcas/patentes) | `app/models/{marcas,patentes}.py` | Fonte de vínculo opcional via `IPAssetPublicLink` (sem FK dura). |
| Análise IA | `app/services/deepseek.py`, `app/routers/analises.py` | Apoio a avaliação de anterioridade na triagem. |
| ETL INPI | `ingestion/*`, `app/models/inpi.py` | Mantido intacto; alimenta a busca pública. |
| Suíte de testes | `backend/tests/*` (94 testes) | Gate de regressão em toda fase. |
| Frontend | `AppShell.tsx`, `components/ui`, `lib/{api,hooks,types}.ts` | Novo agrupamento de menu NIT reusando o design system. |

> **Nenhum módulo existente será substituído.** `routers/marcas.py` (20 KB) e `clientes.py` (26 KB) permanecem; extrações para `services/` só ocorrem se o novo código precisar delas.

---

## 6. Riscos consolidados

A matriz completa (ID, evidência, probabilidade × impacto, severidade, prioridade, dependências, consequência, ação, critério de aceite, fase) está em **`MATRIZ_PRIORIDADES_E_RISCOS.md`**. Resumo:

- **P0 (2):** (1) escopo Company/Unity resolvido mas não aplicado a dados internos; (2) ausência de modelo de documentos/confidencialidade — risco LGPD ao criar sem desenho.
- **P1:** segredos default, token em `localStorage`, rate limiting in-memory só no login, busca "contains" sem trigram explícito, papel de outro tenant atribuível, ausência de backup/restore.
- **P2:** logging estruturado, retenção/LGPD, MFA, export CSV em memória, tratamento de `IntegrityError`, sync INPI síncrono na API.
- **P3:** tipos TS manuais (drift), validação de schema da fonte INPI.

> O risco "sem git" foi **corrigido** (resta apenas *remote* + proteção de branch).

---

## 7. Roadmap (resumo)

Fases, dependências, caminho crítico, escopo dentro/fora, testes, critérios de aceite, DoD e estimativas estão em **`ROADMAP_EXECUCAO_NIT.md`**.

| Fase | Objetivo | Depende de | Estimativa (faixa) |
|---|---|---|---|
| **F0** Governança e segurança da fundação | git remote + proteção, segredos, backup/restore, logging, fechar modelo | — | 1–2 sem |
| **F1** MVP: comunicação de invenção + ativos internos | submeter/avaliar/decidir, docs confidenciais, ativo + vínculo público | F0 + 5 decisões | 8–14 sem |
| **F2** Avaliação avançada, comitês e portfólio | pareceres, TRL, comitês, custos/prazos, indicadores | F1 | 6–10 sem |
| **F3** Transferência tecnológica e contratos | oferta, negociação, licença, contrato, obrigações | F1 (+F2 recomendada) | 8–12 sem |
| **F4** P&D, startups e indicadores ampliados | projetos, financiadores, startups, BI | F2+F3 | 8–12 sem |
| **F5** Portais externos, BI e integrações | portal pesquisador/empresa, notificações, SSO | F4 | 10–16 sem |

**Caminho crítico:** F0 → F1 → F2 → F4 → F5 (F3 paralelizável após F1).
**Premissas das estimativas:** 1–2 devs full-stack sênior, dedicação contínua, decisões respondidas antes da fase dependente. **Não são compromissos.**

---

## 8. Segurança e produção

Plano ordenado por risco, separando *bloqueios para docs confidenciais*, *bloqueios para piloto*, *requisitos de produção* e *melhorias adiáveis*: **`PLANO_SEGURANCA_E_PRODUCAO.md`**.

Bloqueios essenciais antes de F1 (docs confidenciais):
1. Modelo de confidencialidade e storage privado decidido e implementado.
2. ACL por documento/dossiê + auditoria de download.
3. Escopo intra-tenant aplicado às entidades internas.
4. Segredos reais obrigatórios (boot recusa default).
5. Backup/restore testado.

---

## 9. UX/UI

Prioridades de interface para o MVP, reusando `components/ui`: **`PLANO_UX_UI_NIT.md`**. Foco: agrupar o menu por domínio, dossiê central do ativo, telas de comunicação/triagem/portfólio, estados vazios/erro/loading e acessibilidade como critério de aceite.

---

## 10. Documentos criados por este plano

| Documento | Finalidade |
|---|---|
| `PLANO_MESTRE_EVOLUCAO_NIT.md` | Este documento — âncora, estratégia, princípios, correções de evidência. |
| `MATRIZ_PRIORIDADES_E_RISCOS.md` | Matriz única de riscos + matriz funcional consolidada. |
| `ARQUITETURA_ALVO_NIT.md` | Arquitetura incremental por domínio, modelo de dados, separação PI pública/interna, multi-tenancy, migrações. |
| `ROADMAP_EXECUCAO_NIT.md` | Roadmap detalhado F0–F5 com dependências, testes, DoD e estimativas. |
| `PLANO_SEGURANCA_E_PRODUCAO.md` | Plano de segurança/LGPD/operação ordenado por bloqueio. |
| `PLANO_TESTES_E_CRITERIOS_ACEITE.md` | Estratégia de testes e critérios de regressão. |
| `DECISOES_PENDENTES_PRODUTO.md` | Registro de decisões (recomendação, impacto, bloqueio, fase). |
| `PLANO_UX_UI_NIT.md` | Plano de UX/UI e arquitetura de informação para o MVP. |

> Os **nove relatórios de auditoria originais permanecem intactos** e são referenciados, não reescritos.

---

## 11. Declaração de escopo

- **Código:** não alterado. `git diff` limpo para arquivos de código.
- **Banco/migrations:** nenhuma migração criada ou executada; nenhum schema alterado.
- **Configuração/deploy:** inalteradas. Nenhum commit/push. Nenhum arquivo excluído.
- **Única escrita:** criação dos 8 documentos de planejamento acima em `intelliinpi/docs/`.

> Confirmado por `git status` → apenas `?? docs/` (novos documentos) e nenhuma modificação em arquivos rastreados.

---

## 12. Pendências para aprovação

Ver `DECISOES_PENDENTES_PRODUTO.md` §"Decisões indispensáveis para aprovar F0/F1". Em resumo, antes de iniciar **F1** o product owner precisa decidir **5 itens** (D1/D2/D5, E1/E4, I1/I3, P1/P2/P4, S1/S4). **F0 pode iniciar sem elas**, exceto a decisão de infraestrutura (S1), que define onde rodar backup/logging.

**Fim do plano.** A implementação **não foi iniciada** e só começará após aprovação explícita da fase e do escopo.
