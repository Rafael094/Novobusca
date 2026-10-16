# Referência de API (endpoints por módulo)

Todos os endpoints ficam sob o prefixo `/api` e exigem token JWT (Bearer). O tenant
é derivado do usuário autenticado.

## Autenticação (`/api/auth`)

- `POST /api/auth/login` — autentica e retorna access + refresh.
- `POST /api/auth/refresh` — renova o access token.
- `POST /api/auth/logout` — encerra a sessão (invalida o refresh).
- `GET  /api/auth/me` — dados do usuário, papéis, módulos e permissões.

## Dashboard e busca

- `GET /api/dashboard` — resumo do painel.
- `GET /api/search` — busca global (marcas + patentes).

## INPI

- `GET  /api/marcas/search` — pesquisa de marcas.
- `GET  /api/marcas/{id}` — detalhe de marca.
- `GET  /api/marcas/monitoramento` — monitoramento.
- `GET  /api/patentes/search` — pesquisa de patentes.
- `GET  /api/patentes/{id}` — detalhe de patente.
- `GET  /api/analises/status` — status da IA.
- `POST /api/analises` — análise de risco de marca (IA).
- `GET  /api/relatorios` — relatórios/exportações.

## Clientes e CRM

- `GET/POST /api/clientes/customers`, `GET /api/clientes/customers/{id}`.
- `GET/POST /api/clientes/companies`, `GET /api/clientes/companies/{id}`.
- `GET  /api/crm/dashboard`.
- `GET/POST /api/crm/opportunities`, `PATCH .../{id}/stage`.
- `GET/POST /api/crm/proposals`, transições de status.
- `GET/POST /api/crm/activities`.

## NIT

- **Comunicações:** `GET/POST /api/nit/disclosures`, `GET/api/nit/disclosures/{id}`,
  transição de estado pelo workflow.
- **Documentos:** `POST /api/nit/documents` (upload), `GET /api/nit/documents`,
  `GET /api/nit/documents/{id}/download`, ACL (`/api/nit/documents/{id}/acl`).
- **Ativos:** `GET/POST /api/nit/assets`, `GET /api/nit/assets/{id}`.
- **Portfólio:** `GET /api/nit/portfolio`.
- **Comitês:** `GET/POST /api/nit/committees`, membros e reuniões.
- **Ofertas:** `GET/POST /api/nit/offers`.
- **Interesses:** `GET/POST /api/nit/interests`.
- **Negociações:** `GET/POST /api/nit/negotiations`.
- **Contratos:** `GET/POST /api/nit/contracts`.
- **Obrigações:** obrigações e alertas de vencimento.
- **Royalties:** `GET /api/nit/royalties` (+ resumo).
- **Projetos:** `GET/POST /api/nit/projects`.
- **Startups:** `GET/POST /api/nit/startups`.
- **Indicadores:** `GET /api/nit/indicators`.
- **Notificações:** `GET /api/nit/notifications`.
- **Dashboard NIT:** `GET /api/nit/dashboard`.

## Administração (`/api/admin`)

- Usuários, tenants, módulos, papéis, permissões e recursos.
- `GET /api/admin/audit` — trilha de auditoria.

## Assistente (chat)

- `POST /api/chat` — pergunta em linguagem natural; responde com base na
  documentação do sistema (RAG). Corpo: `{ "message": "...", "history": [...] }`.
- `GET  /api/chat/status` — informa se o assistente (IA) está configurado.

> Sem `DEEPSEEK_API_KEY`, o assistente responde com os trechos de documentação
> recuperados e avisa que a IA está indisponível — nunca inventa resposta.
