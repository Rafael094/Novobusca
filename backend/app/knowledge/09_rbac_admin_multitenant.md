# RBAC, Multi-tenancy, Administração e Auditoria

## Papéis e permissões

O controle de acesso é **RBAC** (Tenant → Usuário → Papel → Módulo → Permissão).
O catálogo de permissões fica em `backend/app/constants.py`. Para verificar o que o
usuário pode fazer: `GET /api/auth/me` retorna `roles`, `modules`, `permissions` e
`resources`.

## Papéis padrão e quem pode fazer o quê no NIT

Permissões de documentos (`NIT_DOCUMENT_UPLOAD`): **SUPER_ADMIN**, **TENANT_ADMIN**,
**NIT_RESEARCHER**, **NIT_ANALYST**, **NIT_MANAGER**, **NIT_TT_OPERATOR**.

Principais autoridades do fluxo NIT:

- `NIT_WORKFLOW_TRIAGE` — iniciar triagem, enviar para avaliação, devolver/rejeitar
  na triagem.
- `NIT_EVALUATION_CREATE` — registrar parecer, encaminhar para decisão, devolver à
  triagem, rejeitar após avaliação.
- `NIT_DECISION` — aprovar e encerrar ou rejeitar na decisão.
- `NIT_DOCUMENT_VIEW` / `NIT_DOCUMENT_UPLOAD` / `NIT_DOCUMENT_MANAGE` — acesso aos
  documentos de invenção.

## Multi-tenancy (isolamento)

- O tenant **nunca** vem do corpo/consulta: é derivado do usuário autenticado.
  Helpers em `backend/app/routers/nit/_common.py`:
  - `write_tenant` — tenant de um registro novo;
  - `scoped_tenant` / `list_scope` — filtro de listagens;
  - `assert_same_tenant` — bloqueia acesso a id de outro tenant (403);
  - `assert_unity_scope` — valida unidade pertencente ao tenant.
- O **Master Admin** pode atuar cross-tenant (escopo amplo); demais usuários ficam
  restritos ao próprio tenant.

## Documentos — controle de acesso

`can_access_document` decide leitura/escrita:

- Outro tenant → nunca.
- Master Admin → sempre.
- `NIT_DOCUMENT_MANAGE` → sempre (dentro do tenant).
- Documento `PUBLIC` → qualquer portador de `NIT_DOCUMENT_VIEW`.
- Caso contrário → exige **ACL explícita** (por usuário, papel ou unidade).

## Administração

Menu do usuário (canto superior direito) → **Administração**:

- `/admin` — visão geral;
- `/admin/usuarios` — usuários e atribuição de papéis;
- `/admin/tenants` — tenants e módulos habilitados;
- `/admin/modulos` — módulos, permissões e recursos.

## Auditoria

As ações relevantes são registradas na **trilha de auditoria**
(`GET /api/admin/audit`), incluindo execuções de IA (`ANALISE_IA_EXECUTE`) e
movimentações do workflow.

## Perguntas típicas

- **"Como dou acesso a um usuário?"** → `/admin/usuarios`, atribuindo papéis.
- **"Quem pode aprovar uma invenção?"** → quem tem `NIT_DECISION`.
- **"Por que vejo dados de vários tenants?"** → você é Master Admin (acesso
  cross-tenant).
