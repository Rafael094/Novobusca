# Auditoria de UX/UI e Produto SaaS — IntelliINPI

**Data:** 2026-10-09
**Natureza:** Avaliação estática (frontend não foi executado). Itens não observáveis em execução são **[NÃO VERIF]**.

---

## 1. Inventário de telas atuais

| Rota | Arquivo | Tamanho | Perfil principal |
|---|---|---|---|
| `/login` | `login/page.tsx` | 3.477 | Todos |
| `/dashboard` | `dashboard/page.tsx` | 8.246 | Gestor/analista |
| `/marcas` | `marcas/page.tsx` | 27.228 | Analista de PI |
| `/patentes` | `patentes/page.tsx` | 9.127 | Analista de PI |
| `/monitoramento` | `monitoramento/page.tsx` | 7.347 | Analista |
| `/analises` | `analises/page.tsx` | 15.784 | Analista |
| `/clientes` | `clientes/page.tsx` | 23.277 | Gestor/CRM |
| `/relatorios` | `relatorios/page.tsx` | 4.001 | Gestor |
| `/admin` | `admin/page.tsx` | 7.173 | Admin SaaS |
| `/admin/usuarios` | `admin/usuarios/page.tsx` | 8.937 | Admin institucional |
| `/admin/tenants` | `admin/tenants/page.tsx` | 7.707 | Admin SaaS |
| `/admin/modulos` | `admin/modulos/page.tsx` | 4.528 | Admin institucional |

**[CÓDIGO]** — 12 telas, todas de uso **interno**. Faltam todas as telas de NIT.

---

## 2. Arquitetura de informação (navegação atual)

`AppShell.tsx` **[CÓDIGO]**: Visão Geral, Clientes, Marcas, Patentes, Monitoramento, Análises IA, Relatórios, Administração (Sincronização INPI, Usuários, Tenants, Módulos & Papéis).

- Itens filtrados por permissão (`has(perm)`) — **bom**: o menu reflete o RBAC.
- **Lacuna:** não há agrupamento temático (PI / NIT / Gestão / Admin).

---

## 3. Design system

- `components/ui/index.tsx` (13.829 bytes) — botões, inputs, tabelas, badges.
- `components/charts/index.tsx` — gráficos. Tailwind com tokens (`brand-600`, `sidebar-muted`) **[CÓDIGO]**.
- **Ponto forte:** consistência visual razoável e reuso.

---

## 4. Necessidades por perfil

| Perfil | Telas atuais | Telas que faltam |
|---|---|---|
| Administrador SaaS | `/admin/*` | — (atende) |
| Gestor institucional | `/dashboard`, `/relatorios` | Indicadores de NIT, portfólio |
| Coordenador do NIT | parcial | Triagem, comitê, alçadas |
| Analista de PI | `/marcas`, `/patentes`, `/analises` | Avaliação de invenção |
| Pesquisador/inventor | **nenhuma** | Portal do pesquisador |
| Responsável jurídico | **nenhuma** | Contratos, NDA |
| Gestor de transferência | parcial (`/clientes`) | Catálogo, negociações |
| Representante de empresa | **nenhuma** | Portal de empresas |
| Auditor/comitê | parcial | Auditoria ampliada, comitês |

---

## 5. Problemas de usabilidade identificados

| # | Problema | Evidência | Impacto |
|---|---|---|---|
| U1 | Busca de marcas dispara a cada tecla (sem debounce) | `SPIKE_...`; `hooks.ts` | Requisições excessivas |
| U2 | Sem agrupamento de menu | `AppShell.tsx` | Escalabilidade ruim |
| U3 | Ordenação fixa em marcas | `routers/marcas.py` | Sem ordenação pelo usuário |
| U4 | Sem onboarding de tenant | ausência | Nova instituição não guiada |
| U5 | Sem ajuda contextual | ausência | Curva de aprendizado |
| U6 | Estados vazios não documentados | **[NÃO VERIF]** | — |
| U7 | Acessibilidade não testada | `AppShell` sem ARIA | Barreira de inclusão |
| U8 | Feedback de operações longas | **[PARCIAL]** | Sem progresso visível |

---

## 6. Telas AUSENTES recomendadas (especificação funcional)

> Apenas especificação — **nada foi desenhado ou implementado**.

| Tela | Objetivo | Usuário | Ações | Permissões | Dependências |
|---|---|---|---|---|---|
| Comunicações de Invenção | Registrar/acompanhar invenções | Pesquisador, Coordenador | Criar, editar, anexar, submeter | `NIT_DISCLOSURE_*` | Domínio A |
| Detalhe da Comunicação | Ver dossiê, inventores, docs, workflow | Coordenador, Analista | Avaliar, anexar, transicionar | `NIT_DISCLOSURE_VIEW` | Workflow + docs |
| Triagem/Comitê | Avaliar e decidir | Comitê, Avaliador | Parecer, votar, decidir | `NIT_EVAL_*` | Domínio B |
| Portfólio de Ativos | Ver ativos internos | Gestor, Analista | Filtrar, editar, vincular registro | `NIT_ASSET_*` | Domínio C |
| Detalhe do Ativo | Dossiê, prazos, custos | Analista, Jurídico | Manter, renovar | `NIT_ASSET_MANAGE` | C + F |
| Catálogo de Tecnologias | Vitrine para TT | Gestor TT | Publicar, editar | `NIT_TT_*` | E |
| Negociações | Pipeline de TT | Gestor TT | Avançar etapas | `NIT_TT_*` | E |
| Contratos e Obrigações | Gerir contratos | Jurídico | Criar, alertas, royalties | `NIT_CONTRACT_*` | F |
| Projetos de P&D | Gerir projetos | Gestor P&D | CRUD, vínculos | `NIT_PROJECT_*` | D |
| Startup/Spin-off | Acompanhar | Gestor | CRUD | `NIT_STARTUP_*` | G |
| Indicadores de NIT | KPIs institucionais | Gestor, Direção | Ver, exportar | `NIT_REPORT_*` | H |
| Portal do Pesquisador | Autosserviço | Pesquisador | Submeter, acompanhar | própria | I |
| Portal de Empresas | Vitrine + interesse | Empresa | Ver, manifestar | pública | J |
| Auditoria ampliada | Trilha de NIT | Auditor | Consultar | `AUDIT_VIEW` | K |

---

## 7. Telas a REFORMULAR

| Tela | Problema | Direção |
|---|---|---|
| `/dashboard` | Só PI + CRM | Adicionar painéis de NIT |
| `/relatorios` | Muito enxuta (4 KB) | Relatórios institucionais/FORMICT |
| `/marcas` | Grande (27 KB), sem debounce | Debounce + ordenação |
| `/admin` | Subutiliza o RBAC avançado | Expor recursos/políticas/grupos |
| `AppShell` | Menu plano | Agrupar por domínio |

---

## 8. Onboarding e multi-instituição

- **Ausente:** nenhum assistente de configuração inicial do tenant **[CÓDIGO]**.
- **Recomendação:** wizard (instituição → unidades → usuários → módulos → workflow), reusando `admin/tenants` + `admin/usuarios`.

---

## 9. Recomendação de UX para o NIT

1. **Agrupar o menu** por domínio (PI · NIT · Transferência · Gestão · Admin).
2. **Unificar "ativo"** como objeto central (dossiê: dados, docs, workflow, contratos).
3. **Separar visão interna** de **portais externos** (layout próprio).
4. **Reusar o design system** (`components/ui`).
5. **Acessibilidade** como critério de aceite.

Nenhuma tela foi redesenhada ou alterada nesta auditoria.