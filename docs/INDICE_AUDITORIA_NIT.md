# Índice da Auditoria — IntelliINPI → Plataforma SaaS de Gestão de NIT

**Projeto:** IntelliINPI
**Tipo de trabalho:** Auditoria somente leitura (nenhum código, configuração, schema, migração ou dado foi alterado)
**Data:** 2026-10-09
**Escopo:** Avaliar o estado atual verificado do IntelliINPI e determinar o que precisa ser conhecido, validado, decidido e planejado antes de transformá-lo em uma plataforma de gestão de NIT.

---

## 1. Relatórios produzidos

| # | Documento | Conteúdo |
|---|---|---|
| 0 | [`INDICE_AUDITORIA_NIT.md`](./INDICE_AUDITORIA_NIT.md) | Este índice; escopo, método e limitações |
| 1 | [`AUDITORIA_EXECUTIVA_NIT.md`](./AUDITORIA_EXECUTIVA_NIT.md) | Resumo executivo, riscos, decisões, recomendação |
| 2 | [`AUDITORIA_TECNICA_INTELLIINPI.md`](./AUDITORIA_TECNICA_INTELLIINPI.md) | Arquitetura de backend, frontend, banco, ETL, testes |
| 3 | [`MATRIZ_ADERENCIA_FUNCIONAL_NIT.md`](./MATRIZ_ADERENCIA_FUNCIONAL_NIT.md) | Domínios A–K × requisito × estado × lacuna |
| 4 | [`MODELO_DOMINIO_NIT.md`](./MODELO_DOMINIO_NIT.md) | Modelo atual comprovado, modelo futuro, ER Mermaid |
| 5 | [`AUDITORIA_SEGURANCA_MULTITENANT.md`](./AUDITORIA_SEGURANCA_MULTITENANT.md) | Isolamento, RBAC, LGPD, tokens, auditoria |
| 6 | [`AUDITORIA_UX_UI.md`](./AUDITORIA_UX_UI.md) | Inventário de telas, perfis, arquitetura de informação |
| 7 | [`QUESTIONARIO_DECISOES_PRODUTO_NIT.md`](./QUESTIONARIO_DECISOES_PRODUTO_NIT.md) | Perguntas essenciais e decisões bloqueadoras |
| 8 | [`ROADMAP_IMPLEMENTACAO_NIT.md`](./ROADMAP_IMPLEMENTACAO_NIT.md) | Fases, dependências, testes e critérios de aceite |

Todos os arquivos estão em `intelliinpi/docs/`. A pasta `docs/` estava vazia antes desta auditoria — **nenhum documento preexistente foi sobrescrito**.

---

## 2. Método de investigação

Foi realizada análise estática completa e somente leitura:

- Leitura integral dos modelos ORM (`app/models/*.py`), catálogo de módulos/permissões/recursos (`app/constants.py`), RBAC (`app/rbac.py`), dependências (`app/deps.py`), segurança (`app/security.py`), configuração (`app/config.py`) e auditoria (`app/audit.py`).
- Leitura de todos os routers: `auth`, `marcas`, `patentes`, `search`, `analises`, `dashboard`, `clientes` e `admin/{access_control, users, tenants, audit, modules, roles, inpi_sync}`.
- Leitura dos schemas Pydantic e do serviço DeepSeek.
- Leitura do pipeline de ingestão (`ingestion/*.py`) e do catálogo declarativo de datasets.
- Leitura do frontend: `AppShell`, `api.ts`, `hooks.ts`, `types.ts`, `lib/marcas.ts` e a árvore de páginas.
- Leitura das migrações Alembic (6 arquivos) e dos scripts SQL auxiliares.
- **Execução da suíte de testes** (`pytest -q`).
- **Inspeção somente leitura do banco local** (`intelliinpi_app`) — contagens via `SELECT count(*)`.

Nenhum comando de escrita, migração, reimportação, commit ou alteração de permissão foi executado.

---

## 3. Estado verificado do ambiente

| Item | Evidência | Valor |
|---|---|---|
| Python (venv backend) | `backend\.venv\Scripts\python.exe` | 3.13.15 |
| Controle de versão | `git status` na raiz | **Não é repositório git** |
| Migrações Alembic | `backend/alembic/versions/` | 6 migrações; head aplicada = `e5f6a7b8c9d0` |
| Suíte de testes | `pytest -q` executado | **94 testes, 94 aprovados (100%)** |
| `marcas` | `SELECT count(*)` | 6.645.491 |
| `patentes` | `SELECT count(*)` | 1.018.792 |
| `tenants` / `users` / `companies` | `SELECT count(*)` | 2 / 1 / 1 |
| `modules` / `resources` / `roles` / `permissions` | `SELECT count(*)` | 10 / 25 / 8 / 52 |
| `inpi_dataset` | `SELECT count(*)` | 18 |
| `audit_logs` | `SELECT count(*)` | 33 |

> O projeto **não está sob controle de versão git** neste diretório — achado relevante de governança.

---

## 4. Classificação de evidência

- **[CÓDIGO]** confirmado por leitura do código-fonte.
- **[TESTE]** confirmado por teste executado (94/94 verdes).
- **[DOC]** confirmado por documentação do repositório.
- **[PARCIAL]** parcialmente confirmado.
- **[NÃO VERIF]** não verificado nesta auditoria.
- **[NEGÓCIO]** dependente de decisão do responsável pelo produto.

---

## 5. Limitações explícitas

1. **Sem teste de carga/benchmark.** Métricas de tempo de resposta são inferidas do código e dos índices, não medidas — **[PARCIAL]**.
2. **Sem exploração ofensiva.** Nenhum pentest/fuzzing.
3. **Integrações externas não exercitadas.** DeepSeek sem chave; portal do INPI não acessado.
4. **Sem atestado de conformidade legal.** LGPD tratada como requisito de projeto.
5. **Frontend não executado.** UX/UI avaliada estaticamente.
6. **`alembic current` não executado** para evitar efeitos colaterais de conexão; inferência via relatório **[DOC]**.
7. **Volumetria de tabelas auxiliares** vem do `INPI_IMPORT_REPORT.md` **[DOC]**.

---

## 6. Ordem de leitura recomendada

1. `AUDITORIA_EXECUTIVA_NIT.md`
2. `AUDITORIA_SEGURANCA_MULTITENANT.md` (P0)
3. `MATRIZ_ADERENCIA_FUNCIONAL_NIT.md`
4. `MODELO_DOMINIO_NIT.md`
5. `QUESTIONARIO_DECISOES_PRODUTO_NIT.md`
6. `ROADMAP_IMPLEMENTACAO_NIT.md`
7. `AUDITORIA_TECNICA_INTELLIINPI.md` e `AUDITORIA_UX_UI.md`

---

## 7. Documentos de planejamento e execução (adicionados após a auditoria)

> Estes documentos foram criados **depois** dos 9 relatórios de auditoria originais, que
> **permanecem íntegros e não foram sobrescritos**. A lista abaixo é um complemento ao índice.

### 7.1 Planejamento (8 documentos)

| # | Documento | Conteúdo |
|---|---|---|
| P1 | [`PLANO_MESTRE_EVOLUCAO_NIT.md`](./PLANO_MESTRE_EVOLUCAO_NIT.md) | Consolidação do plano de evolução |
| P2 | [`MATRIZ_PRIORIDADES_E_RISCOS.md`](./MATRIZ_PRIORIDADES_E_RISCOS.md) | Prioridades e riscos R-01..R-19 |
| P3 | [`ARQUITETURA_ALVO_NIT.md`](./ARQUITETURA_ALVO_NIT.md) | Arquitetura-alvo, domínios e invariantes |
| P4 | [`ROADMAP_EXECUCAO_NIT.md`](./ROADMAP_EXECUCAO_NIT.md) | F0–F5, dependências e caminho crítico |
| P5 | [`PLANO_SEGURANCA_E_PRODUCAO.md`](./PLANO_SEGURANCA_E_PRODUCAO.md) | Requisitos B1–B4 de segurança/produção |
| P6 | [`PLANO_TESTES_E_CRITERIOS_ACEITE.md`](./PLANO_TESTES_E_CRITERIOS_ACEITE.md) | Estratégia de testes e DoD |
| P7 | [`DECISOES_PENDENTES_PRODUTO.md`](./DECISOES_PENDENTES_PRODUTO.md) | Decisões bloqueadoras e recomendações |
| P8 | [`PLANO_UX_UI_NIT.md`](./PLANO_UX_UI_NIT.md) | IA, telas do MVP, estados e acessibilidade |

### 7.2 Execução da Fase 0 (2026-10-09)

| # | Documento | Conteúdo |
|---|---|---|
| E1 | [`RELATORIO_F0_FUNDACAO.md`](./RELATORIO_F0_FUNDACAO.md) | O que foi implementado/testado/bloqueado na F0 |
| E2 | [`RUNBOOK_BACKUP_RESTORE.md`](./RUNBOOK_BACKUP_RESTORE.md) | Procedimento de backup/restauração e RPO/RTO |
| E3 | [`PENDENCIAS_INFRA_F0.md`](./PENDENCIAS_INFRA_F0.md) | Checklist objetivo de infraestrutura faltante (S1) |

**Nota de estado:** a F0 foi executada **parcialmente** — correções independentes de decisão
(R-04, R-08, R-10, 500-safe/409) implementadas e cobertas por 15 novos testes; execução real de
backup/restore e observabilidade ativa permanecem **bloqueadas** por S1. A suíte passou de 94 para
**109 testes aprovados**. Nenhum commit, push ou deploy foi realizado.
