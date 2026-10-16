# Auditoria de Segurança e Multi-Tenancy — IntelliINPI

**Data:** 2026-10-09
**Natureza:** Auditoria somente leitura. Nenhum teste ofensivo foi executado.
**Prioridade:** Esta é a fase prioritária. O isolamento de dados entre tenants é o ativo mais crítico do produto.

---

## 1. Isolamento multi-tenant — como funciona

### 1.1 Derivação do tenant

O tenant é **sempre** derivado do usuário autenticado, nunca do corpo/query da requisição:

- `get_current_user()` (`app/deps.py`) decodifica o JWT, valida `type == "access"`, carrega o `User` e checa `active`, `deleted_at` e se o tenant está ativo **[CÓDIGO]**.
- `build_access_context()` (`app/rbac.py`) usa `user.tenant_id` — **o `tenant_id` do token não é usado para autorização** (só para emissão) **[CÓDIGO]**.
- Nos routers CRM (`clientes.py`), o parâmetro `tenant_id` da query só é aceito por **master admin**; para os demais, `_scoped_tenant()` força `ctx.user.tenant_id` e rejeita 403 se divergir **[CÓDIGO]**.

### 1.2 Evidência por teste

`tests/test_tenant_isolation.py` prova (executado, verde):

- `test_list_users_only_returns_own_tenant` — admin do Tenant A não vê usuários do B.
- `test_list_users_ignores_cross_tenant_filter` — `?tenant_id=<outro>` é ignorado.
- `test_get_other_tenant_user_is_forbidden` — 403 ao acessar usuário de outro tenant.
- `test_create_user_in_other_tenant_is_forbidden` / `test_tenant_derived_from_token_not_request_body` — `tenant_id` forjado no body → 403.
- `test_master_admin_can_see_all_tenants` — master opera cross-tenant.

**[TESTE]** — todas as garantias acima estão cobertas e passando.

### 1.3 Onde o escopo de tenant NÃO se aplica (por design)

- **Dados públicos de PI** (`marcas`, `patentes` e tabelas-filhas) são **globais**, compartilhados entre todos os tenants **[CÓDIGO]**. Isso é correto: são dados abertos do INPI.
- **Monitoramento** (`marcas_monitoramento`, `patentes_monitoramento`) tem `tenant_id` **e** `user_id` — é por usuário, dentro do tenant **[CÓDIGO]**.
- **Auditoria** filtra por tenant para não-master **[CÓDIGO]**.

### 1.4 Acesso direto por identificador

- `GET /marcas/{codigo_interno}` e `GET /patentes/{codigo_interno}` retornam dados **públicos**, sem escopo de tenant (correto) **[CÓDIGO]**.
- `GET /clientes/companies/{id}`, `/unities/{id}`, `/customers/{id}`, `/people/{id}` chamam `_assert_tenant()` → 403 cross-tenant **[CÓDIGO]**.
- **Achado:** `GET /marcas/{codigo_interno}/logo` **não** verifica tenant — mas a imagem é dado público; aceitável.
- **Achado (P2):** `GET /api/admin/modules`, `/roles`, `/resources` — verificar se exigem permissão e escopo. `access_control.list_resources` usa `require_permission("RESOURCE_VIEW")` **[CÓDIGO]** (catálogo global, aceitável).

### 1.5 Joins entre tenants

- **Não foram encontrados joins cruzando tenants** em dados de aplicação **[CÓDIGO]**. As queries filtram por `ctx.user.tenant_id` antes de juntar.
- O `dashboard` conta marcas/patentes globalmente (dados públicos) e conta entidades de CRM escopadas **[CÓDIGO]**.

---

## 2. RBAC — modelo e avaliação

### 2.1 Estrutura

- 10 módulos, 52 permissões, 25 recursos, 8 papéis **[CÓDIGO]**.
- Três caminhos de concessão: `UserPolicy` (ALLOW/DENY), `GroupPolicy` (ALLOW/DENY), `RolePolicy` (só ALLOW) **[CÓDIGO]**.
- **`DENIED` explícito vence** qualquer allow **[CÓDIGO]** — regra correta e testada.
- Escopo por `Company`/`Unity` via `control_company_unity` **[CÓDIGO]**.

### 2.2 Avaliação para o caso NIT (universidade multi-campus)

O modelo **suporta** o cenário:

- `Tenant` = a ICT.
- `Company`/`Unity` = campus/departamento/laboratório.
- `Group` + `GroupPolicy` + `UserGroup` (com escopo Company/Unity) = equipes de projeto com permissões específicas.
- `Group` = comitê de avaliação, com `DENIED` para membros com conflito de interesse.

**Ressalva (P1):** o escopo Company/Unity é **armazenado e resolvido**, mas **não é aplicado de forma transparente a queries de dados de PI** (que são globais). Para o NIT, ativos internos/precisa de enforcement explícito de escopo nos endpoints — hoje os únicos consumidores de escopo são as `UserPolicy`/`GroupPolicy` resolvidas em `AccessContext.scoped_resources`, que **nenhum endpoint de dados usa ainda** **[CÓDIGO]** — lacuna importante a endereçar antes de criar ativos internos.

### 2.3 Riscos de RBAC

| # | Risco | Sev. | Evidência |
|---|---|---|---|
| S1 | `scoped_resources` resolvido mas não aplicado a dados | **P1** | `rbac.py` vs routers |
| S2 | Concessão de papel sem validar que o papel pertence ao tenant | **P2** | `admin/users.py::_set_roles` (comentário pede validação) |
| S3 | Sem revisão periódica de acessos (recertificação) | **P2** | ausência |
| S4 | Master admin sem MFA obrigatório | **P2** | `User.mfa` existe mas não é exigido |

---

## 3. Autenticação e tokens

- **Senhas:** Argon2id (`time_cost=3, memory_cost=64MiB, parallelism=4`) **[CÓDIGO]** — parâmetros sólidos.
- **Access token:** JWT HS256, TTL 30 min, contém `sub`, `tenant_id`, `type`, `jti` **[CÓDIGO]**.
- **Refresh token:** JWT assinado com **segredo separado**, TTL 14 dias, **armazenado como hash SHA-256** e revogável (`revoked_at`) **[CÓDIGO]**. Rotação a cada refresh (revoga o antigo) **[CÓDIGO]**.
- **Logout:** revoga o refresh token **[CÓDIGO]**.
- **Login:** mensagem genérica, rate limit e auditoria **[CÓDIGO]**.

| # | Risco | Sev. | Evidência |
|---|---|---|---|
| S5 | Backend usa `tenant_id` do usuário no token; trocar de tenant exigiria novo login | P2 | `security.py` |
| S6 | Token no `localStorage` (XSS exfiltra) | **P1** | `frontend/src/lib/api.ts` |
| S7 | Sem revogação de **access tokens** (só refresh) | P2 | `security.py` |
| S8 | `jwt_secret` default `dev-secret-change-me` | **P1** | `config.py` |

---

## 4. Proteção contra ataques comuns

| Vetor | Estado | Evidência |
|---|---|---|
| **SQL Injection** | **Mitigado** — SQLAlchemy parametrizado | `routers/*` |
| **XSS** | **Parcial** — React escapa; risco residual no `localStorage` | `api.ts` |
| **CSRF** | **Baixo** — usa Bearer header, não cookie | `main.py` |
| **Rate limiting** | **Só no login** (10/5min por IP, in-memory) | `rate_limit.py` |
| **Abuso de API** | **Sem throttling** fora do login | ausência |
| **Timing attack no login** | Mitigado (mensagem genérica + Argon2) | `routers/auth.py` |

### Achado P1 — Rate limiting insuficiente

O `LoginRateLimiter` é **in-memory e por processo** — em multi-worker o limite não é compartilhado **[CÓDIGO]**. E **nenhum outro endpoint** (busca, export, IA) tem limite. Export de 6,6M linhas e a análise IA (com custo) são alvos de abuso.

**Recomendação:** rate limiting compartilhado (Redis) e por usuário nos endpoints caros; cota de export por tenant/dia.

---

## 5. Gestão de segredos

- Segredos apenas via `.env`/ambiente **[CÓDIGO]**.
- **Risco (P1):** defaults fracos para `jwt_secret`, `jwt_refresh_secret` e senha do master **[CÓDIGO]**; se o `.env` faltar, sobe com segredos públicos.
- **Recomendação:** falhar o boot com `JWT_SECRET` default e exigir senha de master não-default.

---

## 6. Upload/download de arquivos

- **Download existente:** logo de marca (`GET /marcas/{cod}/logo`) valida `status == "OK"` e existência física **[CÓDIGO]**.
- **Upload:** **não existe** endpoint de upload **[CÓDIGO]**. Central para o NIT (documentos confidenciais) e precisa de desenho antes da Fase 1:
  - validação de MIME real (magic bytes);
  - limite de tamanho;
  - storage fora do webroot;
  - antivírus;
  - URL assinada temporária;
  - ACL documental por ativo/contrato.

---

## 7. Auditoria e trilha

- `record_audit()` grava em `audit_logs` (commit imediato) **[CÓDIGO]**.
- Ações registradas: LOGIN/LOGOUT/REFRESH, falhas de login, CRUD de usuários/tenants, USER_POLICY, USER_GROUP, TENANT_*, ANALISE_IA_EXECUTE, SYNC_TRIGGER **[CÓDIGO]**.
- Consulta via `GET /api/admin/audit` com filtros e escopo de tenant **[CÓDIGO]**.

**Lacunas:** nem toda alteração é auditada; não há política de retenção nem imutabilidade.

---

## 8. LGPD e dados pessoais

Dados pessoais presentes: `people` (nome, CPF, e-mail, telefone, endereço), `users` (e-mail, IP, user-agent), `audit_logs` (IP/UA), `customers`.

| Requisito | Estado | Observação |
|---|---|---|
| Base legal / finalidade | **NEGÓCIO** | Não documentada no código |
| Minimização | Parcial | CPF/endereço coletados |
| Direito de acesso/portabilidade | Ausente | Sem endpoint de export do titular |
| Direito de eliminação | Parcial | Soft delete; sem anonimização |
| Retenção/descarte | **Ausente** | Sem política nem job |
| Registro de tratamento | Ausente | — |
| Criptografia em repouso | **Não verificado** | Depende do Postgres/host |

> **Não é possível declarar conformidade LGPD** com base apenas nos controles técnicos. A conformidade depende de processos, base legal e políticas institucionais.

---

## 9. Backup, recuperação e operação

- **Sem script de backup documentado** **[verificado]**.
- Docker compose usa volume `pgdata`, mas sem rotina de dump **[CÓDIGO]**.
- **Sem plano de recuperação de desastre** documentado.
- **Recomendação (P1):** `pg_dump` agendado, teste de restore, retenção (ex.: 30 dias), documentação de RTO/RPO.

---

## 10. Matriz de segurança consolidada

| ID | Risco | Evidência | Impacto | Probabilidade | Cenário | Mitigação | Teste de validação | Prioridade |
|---|---|---|---|---|---|---|---|---|
| S1 | Escopo Company/Unity não aplicado a dados | `rbac.py` + routers | Vazamento intra-tenant | Média | Membro de um lab vê ativo de outro | Aplicar `scoped_resources` nos endpoints de ativos | Teste de isolamento por unidade | **P0** |
| S2 | Sem git | `git status` | Perda de histórico/código | Alta | Alteração irreversível | Inicializar git + remote | Verificar `git log` | **P0** |
| S3 | Documentos confidenciais sem desenho | ausência | Vazamento grave/LGPD | Alta (ao criar) | Download indevido de dossiê | ACL + storage privado + URL assinada | Teste de acesso cruzado | **P0** |
| S4 | Segredos default | `config.py` | Comprometimento total | Média | Boot sem `.env` | Falhar boot com default | Teste de config | **P1** |
| S5 | Token em localStorage | `api.ts` | Roubo de sessão via XSS | Média | XSS em dependência | Cookie httpOnly + CSP | Revisão de segurança | **P1** |
| S6 | Rate limiting só no login / in-memory | `rate_limit.py` | DoS / abuso de custo IA | Média | Script de export/IA | Redis + limites por usuário | Teste de carga | **P1** |
| S7 | Papel de outro tenant atribuível | `admin/users.py` | Elevação de privilégio | Baixa | Papel forjado | Validar tenant do papel | Teste de atribuição | **P1** |
| S8 | Sem MFA para master | `User.mfa` | Conta mais poderosa frágil | Média | Credencial vazada | MFA obrigatório | Teste de login | **P2** |
| S9 | Sem política de retenção | ausência | Não conformidade | Média | Dados além do prazo | Job de retenção | Revisão | **P2** |
| S10 | Sem backup/restore | ausência | Perda de dados | Média | Falha de disco | Dump agendado + restore testado | Simulado | **P1** |
| S11 | Sem logging de falhas | `main.py` | Dificuldade forense | Alta | Incidente sem rastro | Log estruturado | Revisão | **P2** |
| S12 | `_set_roles` sem validação de pertencimento | `admin/users.py` | Confusão de RBAC | Baixa | Papel indevido | Validar | Teste | **P2** |

---

## 11. Conclusão de segurança

O IntelliINPI tem uma **base de segurança acima da média para um produto em estágio inicial**: isolamento por token comprovado por testes, RBAC granular, Argon2id, refresh rotativo com hash, auditoria persistente e ausência de SQL injection.

As **lacunas críticas para virar SaaS de NIT** são: (1) aplicar o escopo Company/Unity aos dados internos; (2) desenhar com segurança o armazenamento de documentos confidenciais; (3) garantir governança (git, segredos, backup); (4) ampliar rate limiting. Nenhuma delas exige reescrita — são extensões sobre a base atual.
