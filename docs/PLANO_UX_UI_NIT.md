# Plano de UX/UI — Evolução NIT

**Data:** 2026-10-09 · **Natureza:** Planejamento. **Nenhuma tela foi redesenhada ou implementada.**
**Base:** `AUDITORIA_UX_UI.md` (preservada) + design system existente (`frontend/src/components/ui`, `charts`, `AppShell.tsx`).

> Direção: transmitir um **SaaS profissional de gestão institucional** sem perder a eficiência das ferramentas de pesquisa de PI. **Não redesenhar tudo de uma vez** — priorizar os fluxos essenciais do MVP e **preservar os componentes que funcionam**.

---

## 1. Arquitetura de informação (evolução do `AppShell`)

Agrupar o menu (hoje plano) por domínio, mantendo a filtragem por permissão (`has(perm)`):

1. **Visão Geral** — dashboards (PI + NIT).
2. **Pesquisa de PI** — Marcas, Patentes, Análises IA (inalterado).
3. **NIT** — Comunicações de Invenção, Triagem/Avaliação, Portfólio de Ativos.
4. **Transferência** — Catálogo, Negociações, Contratos (F3).
5. **Relacionamento** — Clientes/Parceiros (reuso de `/clientes`).
6. **Relatórios** — Indicadores de NIT, relatórios institucionais.
7. **Administração** — Usuários, Papéis/Recursos, Módulos, Sincronização INPI, Auditoria.

> Reuso do componente de menu existente; apenas agrupamento e novos itens. Portais externos (F5) usam **layout próprio**, separado do shell interno.

---

## 2. Dossiê central do ativo (conceito-chave)

Unificar o "ativo" como objeto central, com abas:
- **Resumo** (dados, tipo, status, titularidade, protocolo).
- **Documentos** (com nível de confidencialidade visível).
- **Workflow** (estado atual + histórico de transições).
- **Avaliações/Pareceres**.
- **Registro público vinculado** (referência INPI, com procedência e data de sincronização).
- **Contratos/Obrigações** (F3).

Esse dossiê é reusado tanto para o ativo institucional quanto para a comunicação de invenção (antes de virar ativo).

---

## 3. Telas prioritárias do MVP

| Tela | Objetivo | Usuário | Informações | Ações | Permissões | Critérios de aceite |
|---|---|---|---|---|---|---|
| **Comunicações de Invenção (lista)** | Ver/submeter comunicações | Pesquisador, Coordenador | protocolo, título, status, unidade, inventores | criar, filtrar, abrir | `NIT_DISCLOSURE_VIEW`/`_CREATE` | Lista paginada, filtros, estado vazio claro |
| **Detalhe da Comunicação** | Dossiê + tramitação | Coordenador, Analista | dados, inventores, docs, workflow | editar, anexar, transicionar, avaliar | `NIT_DISCLOSURE_VIEW`/`_MANAGE` | Abas do dossiê; transições só se permitidas |
| **Nova Comunicação** | Submissão guiada | Pesquisador, NIT | campos + inventores + anexos | salvar, submeter | `NIT_DISCLOSURE_CREATE` | Protocolo gerado; anexo com nível de sigilo |
| **Triagem/Avaliação** | Registrar parecer/decisão | Avaliador, Comitê | parecer, tipo, decisão, justificativa | parecer, decidir | `NIT_EVAL_*` | Decisão exige alçada; grava auditoria |
| **Portfólio de Ativos** | Ver ativos internos | Gestor, Analista | tipo, status, unidade, vínculo público | filtrar, abrir, editar | `NIT_ASSET_VIEW`/`_MANAGE` | Respeita escopo de unidade |
| **Detalhe do Ativo** | Dossiê central | Analista, Jurídico | todas as áreas do dossiê | manter, vincular registro, anexar | `NIT_ASSET_MANAGE` | Abas completas; vínculo opcional ao INPI |
| **Dashboard de NIT** | KPIs operacionais | Gestor, Coordenador | invenções por status, decisões, prazos | filtrar, exportar | `NIT_REPORT_VIEW` | Números coerentes com a base |

---

## 4. Estados e feedback

- **Vazio:** mensagem + ação primária (ex.: "Nenhuma comunicação ainda — submeter").
- **Carregamento:** skeletons reutilizando UI existente (TanStack Query `isLoading`).
- **Erro:** mensagem clara em pt-BR usando o `ApiError` já existente; 403 explicando permissão faltante.
- **Sucesso:** confirmação (toast) + auditoria registrada.
- **Operações longas:** progresso visível (upload, export) — corrige U8.

---

## 5. Melhorias nas telas existentes (sem reescrita)

| Tela | Melhoria | Origem |
|---|---|---|
| `/marcas` | Debounce na busca + ordenação pelo usuário | U1, U3 |
| `/dashboard` | Adicionar painéis de NIT | §7 auditoria |
| `/relatorios` | Relatórios institucionais / FORMICT | §7 |
| `/admin` | Expor recursos/políticas/grupos do RBAC avançado | §7 |
| `AppShell` | Agrupamento por domínio | U2 |

---

## 6. Responsividade e acessibilidade

- **Responsividade:** telas de dossiê e listas utilizáveis em tablet; tabelas com scroll/colunas responsivas.
- **Acessibilidade (critério de aceite, não opcional):** foco navegável, rótulos ARIA em controles, contraste adequado, navegação por teclado nos fluxos-chave (submissão, avaliação). Corrige U7.
- Reusar `components/ui` para consistência de tokens (`brand-600`, `sidebar-muted`).

---

## 7. Onboarding de instituições

Assistente inicial (wizard): instituição → unidades → usuários → módulos → workflow, reusando `admin/tenants` + `admin/usuarios`. Corrige U4.

---

## 8. Escopo desta fase

- Apenas **planejamento**: objetivos, informações, ações, permissões e critérios de aceite por tela.
- **Nenhum componente foi criado ou alterado.** A implementação visual integra F1 (telas de NIT) e F5 (portais externos).
