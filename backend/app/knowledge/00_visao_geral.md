# IntelliINPI — Visão Geral do Sistema

## O que é

O **IntelliINPI** é uma plataforma **multi-tenant** para pesquisa de marcas e
patentes a partir das bases públicas do INPI, complementada por:

- um **CRM comercial** (clientes, empresas, oportunidades, propostas, atividades);
- um **módulo NIT** (Núcleo de Inovação Tecnológica) que cobre o ciclo completo de
  uma invenção: comunicação, triagem, pareceres, decisão, ativo de PI, transferência
  de tecnologia, contratos, projetos de P&D, startups e indicadores;
- **integrações de IA** para análise de risco de marcas (anterioridade).

## Blocos da navegação (menu lateral)

O menu tem quatro blocos, definidos em `frontend/src/components/AppShell.tsx`:

1. **Visão Geral** → `/dashboard` (sem permissão específica).
2. **CRM / Clientes** → `/crm` (requer `COMPANY_VIEW`).
3. **INPI** → `/marcas` (requer `MARCAS_SEARCH`).
4. **NIT** → `/nit` (requer `NIT_DISCLOSURE_VIEW`).

A **Administração** fica no menu do usuário (canto superior direito), não no menu
lateral: `/admin`, `/admin/usuarios`, `/admin/tenants`, `/admin/modulos`.

## Arquitetura técnica

- **Backend:** FastAPI + SQLAlchemy 2.0 + PostgreSQL. Todos os routers são
  agregados sob `/api` (`backend/app/routers/__init__.py`).
- **Frontend:** Next.js 15 (App Router) + React 19 + TanStack Query + Tailwind.
- **Multi-tenant:** o tenant **nunca** vem do corpo/consulta da requisição; é sempre
  derivado do usuário autenticado (token JWT). Ver `backend/app/deps.py`.
- **RBAC:** Tenant → Usuário → Papel → Módulo → Permissão. Catálogo em
  `backend/app/constants.py`.
- **IA:** cliente DeepSeek real em `backend/app/services/deepseek.py`; sem chave
  configurada, os recursos de IA degradam explicitamente (HTTP 503) e **nunca
  fabricam resultado**.

## Mapa rápido de módulos → área

| Módulo | Área/pasta | Página inicial |
|--------|-----------|----------------|
| `CORE` | Núcleo/autenticação | `/dashboard` |
| `ADMIN` | Administração | `/admin` |
| `MARCAS` | Pesquisa de marcas | `/marcas` |
| `PATENTES` | Pesquisa de patentes | `/patentes` |
| `BUSCA` | Busca global | `/search` (API) |
| `RELATORIOS` | Relatórios e exportações | `/relatorios` |
| `CONFIGURACOES` | Preferências da conta | — |
| `INPI_SYNC` | Sincronização de datasets do INPI | `/admin` (aba INPI) |
| `AUDITORIA` | Trilha de auditoria | `/admin` |
| `CLIENTES` | Empresas e clientes | `/clientes` |
| `NIT` | Inovação tecnológica | `/nit` |

## Respostas rápidas (FAQ)

- **"Onde vejo meus clientes?"** → Menu **CRM / Clientes → Clientes e empresas**
  (`/clientes`). API: `GET /api/clientes/customers`.
- **"Onde pesquiso marcas?"** → Menu **INPI → Marcas** (`/marcas`). API:
  `GET /api/marcas/search`.
- **"Onde pesquiso patentes?"** → Menu **INPI → Patentes** (`/patentes`). API:
  `GET /api/patentes/search`.
- **"Onde vejo os indicadores do NIT?"** → Menu **NIT → Indicadores & FORMICT**
  (`/nit/indicadores`). API: `GET /api/nit/indicators`.
- **"Onde fica a administração de usuários?"** → Menu do usuário (canto superior
  direito) → **Administração → Usuários** (`/admin/usuarios`).
