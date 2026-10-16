# IntelliINPI

Plataforma SaaS multi-tenant para pesquisa e consulta de dados oficiais de
**Marcas** e **Patentes** do INPI (Instituto Nacional da Propriedade Industrial),
com base de dados local carregada a partir dos **datasets reais** do Portal de
Dados Abertos do INPI (https://dadosabertos.inpi.gov.br/).

## Sumário

- [Arquitetura](#arquitetura)
- [Stack](#stack)
- [Pré-requisitos](#pré-requisitos)
- [Instalação rápida (bootstrap)](#instalação-rápida-bootstrap)
- [Backend](#backend)
- [Frontend](#frontend)
- [Ingestão de dados do INPI](#ingestão-de-dados-do-inpi)
- [Testes](#testes)
- [Acesso ao sistema](#acesso-ao-sistema)
- [Docker](#docker)
- [Deploy (Vercel) e variáveis de ambiente](#deploy-vercel-e-variáveis-de-ambiente)
- [Estrutura do projeto](#estrutura-do-projeto)

## Arquitetura

```
Tenant (raiz / grupo empresarial — sem TenantId próprio)
  ├── Company ── Unity (filiais/unidades)
  ├── Module ── Resource ── Policy
  ├── User ── Person (1:1)
  └── ModuleTenant / Department / GutRange / Group …
```

### Núcleo, Tenant, Company e Unity

- **Tenant** é a **raiz** do domínio (`IAggregateRoot`): **não possui** coluna
  `tenant_id`. Contém `social_reason` (razão social), `company_name` (nome
  fantasia), `cnpj` e `mcp_api_key`.
- **Company** (`companies`) é uma `TenantEntity` vinculada ao Tenant e contém
  `company_name`, `external_id` e `file_document`.
- **Unity** (`unities`) são as filiais/unidades de negócio de uma Company
  (`company_id`), com `name`, `social_reason`, `cnpj`, `matriz_type`
  (`MATRIZ`/`FILIAL`), `cnes`, `sanitary_license`, `opening_hours`, entre outros.
- Praticamente **toda** entidade herda de `TenantEntity` (carregando `tenant_id`)
  — exceto o próprio Tenant. Mixin: `app.models.company.TenantEntityMixin`.

### Identidade: Person vs User

- **Person**: pessoa física (`people`) — `name`, `cpf`, `email`, `cell_phone`,
  `address_*`, `responsibility`, `job_title`. Ligada 1:1 a `User` via
  `users.person_id`.
- **User**: credenciais puras (`users`) — `access_code` (login), `password_hash`
  (Argon2id), `salt`, `type`, `mfa`, `refresh_token`. **Sem** dados cadastrais.
- **Multi-tenant**: um `User` pode pertencer a vários tenants pela associação
  N-N `UserTenant`.
- **Lotação**: a lotação efetiva em empresas/unidades é gerenciada por
  `UserCompanyUnity` (`User` × `Company` × `Unity`).

### RBAC: Módulo → Resource → Policies

- **Module** (`IAggregateRoot`) contém `name` e `control_company_unity`
  (indica se o módulo controla escopo por empresa/unidade).
- **Resource** pertence a um módulo (1-N), com `code` no formato
  `"modulo:acao"` (ex.: `marcas:user`, `accesscontrol:admin`),
  `description`, `is_native` e `control_company_unity` (escopo por recurso,
  independente do módulo).
- **Três caminhos de concessão** (todos levam a Resource + `AccessPolicy`):
  1. **UserPolicy** — concessão direta `User → Resource`, com decisão
     `ALLOWED`/`DENIED` e escopo opcional `Company`/`Unity`.
  2. **GroupPolicy** — o `Group` agrega políticas; usuários entram via
     `UserGroup` (com escopo opcional Company/Unity).
  3. **RolePolicy** — vincula um `Role` (conjunto de Resources) ao
     usuário/tenant com escopo Company/Unity. Recursos vindos de Role são
     estritamente `ALLOWED`.
- Um `DENIED` explícito (UserPolicy/GroupPolicy) **prevalece** sobre qualquer
  concessão do mesmo recurso.
- **Menu (UI)**: `Menu` → `MenuItem` → `MenuItemResource` → `Resource`.

Endpoints de administração do RBAC (`/api/admin`):
`resources`, `groups`, `user-policies`, `group-policies`, `role-policies`,
`user-groups` e `users/{id}/effective-access` (diagnóstico do acesso efetivo).

### Monitoramento seletivo

Nas telas de **Marcas** e **Patentes** o monitoramento **nunca é global nem
automático**: nenhum registro é carregado ao abrir a tela (somente o formulário
de busca e uma mensagem orientando a pesquisar). A coluna **Monitoramento** da
tabela permite ativar/desativar o acompanhamento **apenas** das marcas/patentes
de interesse direto do usuário (`POST /api/marcas/{codigo}/monitoramento` e
`POST /api/patentes/{codigo}/monitoramento`, permissões `MARCAS_MONITOR` /
`PATENTES_MONITOR`).

A página **Monitoramento** (`/monitoramento`) lista **somente** os itens que o
usuário marcou — a lista é por usuário (`GET /api/marcas/monitoramento` e
`GET /api/patentes/monitoramento`, filtradas por `user_id`), não o acervo
global. Cada item traz os dados de exibição (título/elemento nominativo,
número INPI, situação, data de depósito) unidos da tabela de origem, e o botão
**Remover** desativa o acompanhamento daquele registro específico.

> Nota de implementação: os endpoints de monitoramento ficam declarados **antes**
> das rotas com parâmetro de caminho (`GET /{codigo_interno}`), pois o FastAPI
> resolve as rotas na ordem de declaração — caso contrário, `/monitoramento`
> seria capturado como um código de marca/patente. Há teste de regressão para
> isso (`tests/test_monitoramento.py`).

### Multi-tenancy e segurança

- **Isolamento**: toda entidade de negócio possui `tenant_id`; o tenant NUNCA é
  aceito do frontend — é resolvido a partir do usuário autenticado (token JWT).
- **Master Admin**: usuário fora do fluxo normal de tenants, com acesso ao painel
  administrativo global (`/admin`).
- **Isolamento**: um usuário jamais acessa dados de outro tenant (testado).

## Stack

| Camada        | Tecnologia                                        |
|---------------|---------------------------------------------------|
| Backend       | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic, JWT, Argon2id |
| Ingestão      | DuckDB, pandas, psycopg, PostgreSQL COPY          |
| Frontend      | Next.js, TypeScript, React, Tailwind CSS, TanStack Query, React Hook Form, Zod |
| Banco         | PostgreSQL 16                                     |
| Infra         | Docker Compose (opcional), PostgreSQL nativo      |

## Pré-requisitos

- **Python 3.13+**
- **Node.js 20+** e npm
- **PostgreSQL 16+** (serviço local OU docker)
- (Opcional) **Docker + Docker Compose**

## Instalação rápida (bootstrap)

PowerShell a partir da raiz `intelliinpi/`:

```powershell
./scripts/bootstrap.ps1
```

O script:
1. cria/atualiza o banco no PostgreSQL;
2. cria o virtualenv e instala dependências Python;
3. roda as migrations (Alembic);
4. executa o seed (Master Admin, módulos, papéis, permissões);
5. valida o backend (healthcheck);
6. imprime os próximos passos para o frontend.

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item ..\.env.example ..\.env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Documentação da API (Swagger): http://localhost:8000/api/docs

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Acesse http://localhost:3000

## Ingestão de dados do INPI

Todos os comandos usam o virtualenv do backend e a raiz do projeto como CWD.
O módulo `ingestion` está na raiz do monorepo.

> **Importante — rode da raiz do projeto.** O pacote `ingestion` fica em
> `intelliinpi\ingestion`, então `cd backend` seguido de `python -m ingestion...`
> **não funciona** (`ModuleNotFoundError: No module named 'ingestion'`). Use o
> python do venv com caminho relativo, a partir de `intelliinpi`:
>
> ```powershell
> cd "C:\Users\ra_s_\OneDrive\Área de Trabalho\NovoBUSCAMARCAS\intelliinpi"
> .\backend\.venv\Scripts\python.exe -m ingestion.status
> ```
>
> Alternativa (ficando em `backend`): `$env:PYTHONPATH = ".."`.

```powershell
# 1. Descobrir os datasets atuais no portal oficial
python -m ingestion.discover

# 2. Baixar (streaming, com hash SHA256) todos os datasets descobertos
python -m ingestion.download            # ou --category marcas --dataset marcas_depositantes

# 3. Extrair (ZIP -> CSV)
python -m ingestion.extract

# 4. Analisar cabeçalhos, tipos e contagens
python -m ingestion.analyze

# 5. Importar tudo (idempotente, com checkpoint, em chunks)
python -m ingestion.import_all

# 6. Status dos datasets/importações
python -m ingestion.status

# 7. Reprocessar itens com falha
python -m ingestion.retry_failed
```

### Logotipos das marcas (pePI)

As imagens das marcas **não** vêm nos CSVs de dados abertos; elas são baixadas do
pePI (`busca.inpi.gov.br`) por sessão anônima:

```powershell
# (da raiz: intelliinpi) teste DNS/TCP/TLS/HTTP do pePI e sai — não toca no banco
.\backend\.venv\Scripts\python.exe -m ingestion.logos --diagnostico

# Baixa os logotipos pendentes (resume automático)
.\backend\.venv\Scripts\python.exe -m ingestion.logos                       # todas as apresentações
.\backend\.venv\Scripts\python.exe -m ingestion.logos --apresentacao Mista  # só um tipo (repetível)
.\backend\.venv\Scripts\python.exe -m ingestion.logos --codigos 2890218     # um código específico
.\backend\.venv\Scripts\python.exe -m ingestion.logos --concorrencia 2 --delay 0.5
```

> **Instabilidade do host legado.** O `busca.inpi.gov.br` fica atrás de um
> front-end TLS frágil e às vezes **derruba o handshake** (`SSLEOFError:
> UNEXPECTED_EOF_WHILE_READING` / `ConnectionResetError`) ou bloqueia o IP de
> origem. Nesse caso o comando agora faz um **preflight** e falha rápido com uma
> mensagem clara, em vez de gravar milhares de linhas `ERROR` em `marcas_logos`.
> Use `--diagnostico` para ver em qual camada está falhando (DNS, TCP, TLS ou
> HTTP) e `--force` para pular o preflight. Se o TLS for o problema, aguarde e
> tente de novo mais tarde ou rode de outra rede/VPN.

Relatório final: `reports/INPI_IMPORT_REPORT.md`

## Testes

```powershell
cd backend
.\.venv\Scripts\activate
pytest -v
```

Suíte com **94 testes**, incluindo:

- **Tenant isolation** (`tests/test_tenant_isolation.py`) — teste obrigatório.
- **RBAC / policies** (`tests/test_rbac_policies.py`) — os três caminhos de
  concessão (UserPolicy / GroupPolicy / RolePolicy), escopo Company/Unity e o
  catálogo de Resources.
- **Monitoramento seletivo** (`tests/test_monitoramento.py`) — prova que o
  monitoramento é por usuário, seletivo e nunca automático.
- **Company / Unity / Person** (`tests/test_company_customer.py`).

> Se o schema do banco de testes estiver desatualizado após um pull, recrie-o:
> `.\backend\.venv\Scripts\python.exe database\reset_db.py intelliinpi_test`

## Acesso ao sistema

- Frontend: http://localhost:3000
- Login: use o Master Admin definido em `.env`
  (`MASTER_ADMIN_EMAIL` / `MASTER_ADMIN_PASSWORD`).
- Painel administrativo: http://localhost:3000/admin

## Docker

```powershell
docker compose up -d postgres
# opcional: backend e frontend
docker compose up -d
```

O volume `pgdata` persiste o PostgreSQL.

## Deploy (Vercel) e variáveis de ambiente

> **Política de segredos:** nenhuma credencial é versionada. `DATABASE_URL` e
> `DEEPSEEK_API_KEY` vivem **apenas** no `.env` local (git-ignored) e, em
> produção, nas *Environment Variables* da plataforma de deploy.

### Local

1. `Copy-Item .env.example .env` (na raiz do projeto).
2. Preencha **apenas no `.env`**:
   - `DATABASE_URL` (formato `postgresql+psycopg://USER:SENHA@HOST:PORTA/DB`);
   - `DEEPSEEK_API_KEY` (opcional — vazio desabilita a IA com HTTP 503).

O arquivo `.env` **nunca** é commitado/pushado (`git check-ignore -v .env` confirma).

### Vercel

Configure as variáveis em **Project → Settings → Environment Variables**
(aplique a Production, Preview e Development conforme necessário):

| Variável | Escopo | Observação |
|---|---|---|
| `DATABASE_URL` | Servidor | URL SQLAlchemy completa. Use o host/credenciais reais do seu PostgreSQL. |
| `DEEPSEEK_API_KEY` | Servidor | Opcional. Sem ela, a análise de IA responde 503. |
| `ENVIRONMENT` | Servidor | Use algo ≠ `local` (ex.: `production`) em produção — ver nota abaixo. |
| `JWT_SECRET` | Servidor | **Obrigatório** em produção: ≥ 32 caracteres, diferente de `JWT_REFRESH_SECRET`. |
| `JWT_REFRESH_SECRET` | Servidor | **Obrigatório** em produção: ≥ 32 caracteres, diferente de `JWT_SECRET`. |
| `MASTER_ADMIN_EMAIL` | Servidor | Domínio real (TLD `.local` é recusado). |
| `MASTER_ADMIN_PASSWORD` | Servidor | Trocar o valor de exemplo. |
| `CORS_ORIGINS` | Servidor | Domínio do frontend na Vercel (ex.: `https://seu-app.vercel.app`). |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend | URL pública do backend (ex.: `https://sua-api.exemplo`). |

> **Importante:** com `ENVIRONMENT` ≠ `local` (ex.: `production`), o backend
> **recusa iniciar** enquanto `JWT_SECRET` / `JWT_REFRESH_SECRET` /
> `MASTER_ADMIN_PASSWORD` ainda tiverem os valores de exemplo, se os dois
> segredos JWT forem iguais, ou se um deles tiver menos de 32 caracteres
> (validação em `backend/app/config.py`).

> **Atenção (arquitetura):** a Vercel hospeda o **frontend Next.js**. O
> **backend FastAPI** é um processo persistente de longa duração (connection
> pool do PostgreSQL, `uvicorn`) e **não roda** na Vercel. Para publicar o
> frontend na Vercel, hospede a API em um serviço que suporte processos
> persistentes (VM, container, Render, Railway, Fly.io, etc.) e aponte
> `NEXT_PUBLIC_API_BASE_URL` para ela. Os segredos `DATABASE_URL` e
> `DEEPSEEK_API_KEY` pertencem ao serviço que roda o backend.

## Estrutura do projeto

```
intelliinpi/
  backend/       # API FastAPI + SQLAlchemy + Alembic + testes
  frontend/      # Next.js + TypeScript + Tailwind
  ingestion/     # Pipeline de ingestão dos datasets do INPI
  database/      # Scripts SQL auxiliares (índices, FTS, pg_trgm) + reset_db.py
  scripts/       # Bootstrap e utilidades
  docs/          # Documentação técnica
  data/          # raw / extracted / processed (não versionado)
  docker-compose.yml
  .env.example
```

### Utilitário: recriar um banco

`database/reset_db.py` dropa e recria um banco (útil para validar as migrations
Alembic do zero). Rode da raiz com o venv do backend:

```powershell
.\backend\.venv\Scripts\python.exe database\reset_db.py intelliinpi_test
```

### Migrations e modelo de domínio

A migration `e5f6a7b8c9d0` aplica toda a reestruturação (core/tenant/company/
unity, identidade Person/User, RBAC Module→Resource→Policies e o monitoramento
seletivo). É **data-preserving** (as colunas renomeadas têm os valores copiados
antes do rename) e **idempotente**, com `downgrade` completo:

```powershell
cd backend
alembic upgrade head     # aplica tudo
alembic downgrade -1     # reverte só a reestruturação
```
