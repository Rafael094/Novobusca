# Navegação e Telas (onde encontro cada coisa)

Cada tela corresponde a um arquivo `page.tsx` em `frontend/src/app`. A permissão
listada é a que controla a visibilidade do item no menu.

## Bloco 1 — Visão Geral

| Tela | Rota | Permissão |
|------|------|-----------|
| Dashboard | `/dashboard` | — |
| Login | `/login` | — |

## Bloco 2 — CRM / Clientes (`COMPANY_VIEW`)

| Tela | Rota | Permissão |
|------|------|-----------|
| Visão comercial | `/crm` | `CRM_DASHBOARD_VIEW` |
| Leads e oportunidades | `/crm/oportunidades` | `CRM_OPPORTUNITY_VIEW` |
| Propostas comerciais | `/crm/propostas` | `CRM_PROPOSAL_VIEW` |
| Atividades e follow-ups | `/crm/atividades` | `CRM_ACTIVITY_VIEW` |
| Clientes e empresas | `/clientes` | `COMPANY_VIEW` |
| Detalhe de cliente | `/clientes/[id]` | `COMPANY_VIEW` |

## Bloco 3 — INPI (`MARCAS_SEARCH`)

| Tela | Rota | Permissão |
|------|------|-----------|
| Marcas | `/marcas` | `MARCAS_SEARCH` |
| Patentes | `/patentes` | `PATENTES_SEARCH` |
| Monitoramento | `/monitoramento` | `MARCAS_VIEW` |
| Análises de IA | `/analises` | `MARCAS_SEARCH` |
| Relatórios | `/relatorios` | `RELATORIOS_VIEW` |

## Bloco 4 — NIT (`NIT_DISCLOSURE_VIEW`)

| Tela | Rota | Permissão |
|------|------|-----------|
| Painel do NIT | `/nit` | `NIT_REPORT_VIEW` |
| Comunicações | `/nit/comunicacoes` | `NIT_DISCLOSURE_VIEW` |
| Detalhe da comunicação | `/nit/comunicacoes/[id]` | `NIT_DISCLOSURE_VIEW` |
| Portfólio de Ativos | `/nit/ativos` | `NIT_ASSET_VIEW` |
| Detalhe do ativo | `/nit/ativos/[id]` | `NIT_ASSET_VIEW` |
| Portfólio avançado | `/nit/portfolio` | `NIT_PORTFOLIO_VIEW` |
| Comitês | `/nit/comites` | `NIT_COMMITTEE_VIEW` |
| Detalhe do comitê | `/nit/comites/[id]` | `NIT_COMMITTEE_VIEW` |
| Catálogo de Tecnologias | `/nit/catalogo` | `NIT_OFFER_VIEW` |
| Detalhe do catálogo | `/nit/catalogo/[id]` | `NIT_OFFER_VIEW` |
| Negociações | `/nit/negociacoes` | `NIT_NEGOTIATION_VIEW` |
| Contratos | `/nit/contratos` | `NIT_CONTRACT_VIEW` |
| Detalhe do contrato | `/nit/contratos/[id]` | `NIT_CONTRACT_VIEW` |
| Projetos de P&D | `/nit/projetos` | `NIT_PROJECT_VIEW` |
| Detalhe do projeto | `/nit/projetos/[id]` | `NIT_PROJECT_VIEW` |
| Startups | `/nit/startups` | `NIT_STARTUP_VIEW` |
| Detalhe da startup | `/nit/startups/[id]` | `NIT_STARTUP_VIEW` |
| Incubação | `/nit/incubacao` | `NIT_STARTUP_VIEW` |
| Indicadores & FORMICT | `/nit/indicadores` | `NIT_INDICATOR_VIEW` |
| Notificações | `/nit/notificacoes` | `NIT_NOTIFICATION_VIEW` |
| BI & Relatórios | `/nit/bi` | `NIT_BI_VIEW` |
| Portais externos | `/nit/portais` | `NIT_PORTAL_VIEW` |
| Integrações | `/nit/integracoes` | `NIT_INTEGRATION_VIEW` |
| Documentos | `/nit/documentos` | `NIT_DOCUMENT_VIEW` |

## Bloco 5 — Administração (menu do usuário)

| Tela | Rota | Observação |
|------|------|-----------|
| Administração (visão geral) | `/admin` | Requer papel administrativo |
| Usuários | `/admin/usuarios` | Gestão de usuários e papéis |
| Tenants | `/admin/tenants` | Gestão de tenants |
| Módulos | `/admin/modulos` | Módulos, permissões e recursos |

## Como chego em uma tela pelo menu

1. Abra o bloco correspondente no **menu lateral** (Visão Geral, CRM, INPI ou NIT).
2. Blocos expansíveis (INPI e NIT) abrem a lista de telas.
3. A **Administração** não fica no menu lateral: clique no seu nome no **canto
   superior direito** e escolha a opção de administração.

> Observação: o bloco **INPI** não tem tela própria — ao clicar, ele abre em
> **Marcas** (`/marcas`). O mesmo vale para **CRM**, que abre em `/crm`.
