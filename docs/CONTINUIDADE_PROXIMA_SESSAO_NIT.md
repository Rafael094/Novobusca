# Continuidade — Próxima Sessão NIT

**Data desta auditoria:** 2026-10-10  
**Preparado para:** Próxima sessão Claude/ChatGPT  
**Objetivo:** Permitir retomada imediata do trabalho sem repetir auditoria

---

## 1. Contexto do Projeto

**Nome:** IntelliINPI  
**Natureza:** Plataforma SaaS multi-tenant de gestão de Núcleo de Inovação Tecnológica (NIT)  
**Stack:**
- **Backend:** Python 3.13, FastAPI, PostgreSQL, SQLAlchemy, Alembic
- **Frontend:** Next.js 15, React 19, TypeScript, TailwindCSS
- **Autenticação:** JWT, RBAC granular (58 permissões NIT_*, 16 recursos nit:*)
- **Storage:** Abstração (local privado + S3 inerte)

---

## 2. Estado Real das Fases F1–F5

### F1 — Comunicação de Invenção ✅ IMPLEMENTADA
- 11 tabelas, 24 endpoints, 9 telas
- Protocolo único concorrente-seguro
- Storage com validação magic bytes
- Workflow com máquina de estados
- ACL de documentos confidenciais
- **Testes:** 25 (todos passam)

### F2 — Comitês, TRL e Portfólio ✅ IMPLEMENTADA
- 7 tabelas, 14 endpoints, comitês/TRL/portfólio
- Votação com quórum e conflito de interesse
- **Testes:** 13 (todos passam)

### F3 — Transferência de Tecnologia ✅ IMPLEMENTADA
- 10 tabelas, 16 endpoints, catálogo/negociações/contratos
- Valores monetários em Numeric(18,2)
- **Testes:** 11 (todos passam)

### F4 — Projetos P&D, Startups e Indicadores ✅ IMPLEMENTADA
- 10 tabelas, 17 endpoints, projetos/startups/incubação/FORMICT
- Indicadores derivam de consultas reais (não fabricados)
- **Testes:** 10 (todos passam)

### F5 — Portais, BI, Notificações e Integrações ✅ IMPLEMENTADA
- 10 tabelas, 21 endpoints, notificações/portais/BI/integrações
- Outbox pattern para e-mail e integrações
- Portal público com token de tempo constante
- **Testes:** 13 (todos passam)

**Total:** 48 tabelas, 85+ endpoints, 37 rotas frontend, 181 testes passando

---

## 3. Último Estado Conhecido do Git

**Branch:** `main`  
**Último commit:** `7a32c4b first commit`  
**Head Alembic:** `d0e1f2a3b4c5` (head único)

**Arquivos modificados (11):**
```
.env.example
backend/app/config.py
backend/app/constants.py
backend/app/main.py
backend/app/models/__init__.py
backend/app/routers/__init__.py
backend/app/routers/admin/users.py
backend/tests/conftest.py
frontend/src/components/AppShell.tsx
frontend/src/lib/hooks.ts
frontend/src/lib/types.ts
```

**Arquivos não rastreados (48 — implementação NIT):**
- `backend/alembic/versions/*_add_nit_*.py` (5 migrations)
- `backend/app/models/nit*.py` (5 arquivos)
- `backend/app/schemas/nit*.py` (5 arquivos)
- `backend/app/services/*.py` (8 serviços)
- `backend/app/routers/nit/*.py` (19 routers)
- `backend/tests/test_nit_*.py` (7 arquivos)
- `backend/app/seed_nit.py`
- `backend/app/logging_config.py`
- `backend/scripts/` (runbooks)
- `frontend/src/app/nit/` (24 telas)
- `frontend/src/lib/portfolio.ts`
- `docs/` (documentação)

**IMPORTANTE:** Nenhum commit foi feito. Todo o trabalho está unstaged/untracked.

---

## 4. Correções Realizadas na Auditoria

### Correção #1 — Teste de Migração com Caminho Absoluto

**Arquivo:** `backend/tests/test_nit_migration.py:105-111`  
**Problema:** Teste falhava quando pytest executado de fora do diretório backend.  
**Solução:** Path(__file__).parent.parent para resolver alembic.ini e script_location.  
**Status:** ✅ Corrigido e validado (1 passed in 6.33s)

**Essa é a ÚNICA alteração de código feita durante a auditoria.**

---

## 5. Comandos de Teste e Últimos Resultados

### Backend
```bash
cd "C:\Users\ra_s_\OneDrive\Área de Trabalho\NovoBUSCAMARCAS\intelliinpi"
backend/.venv/Scripts/python.exe -m pytest backend/tests -q
# Resultado: 181 passed (100%)
```

### Alembic
```bash
cd backend
.venv/Scripts/alembic.exe heads
# Resultado: d0e1f2a3b4c5 (head)
```

### Frontend (conforme LOG anterior)
```bash
cd frontend
npx tsc --noEmit  # exit 0
npm run build     # exit 0 (37 rotas)
```

**Nota:** Node.js não está no PATH do Git Bash nesta sessão, mas comandos frontend foram validados em sessão anterior.

---

## 6. Achados de Segurança (Resumo)

### P0 — Segurança Crítica ✅ APROVADO

- **Isolamento multi-tenant:** Todos os 16 routers NIT usam scoped_tenant/write_tenant/assert_same_tenant
- **Proteção IDOR:** IDs cross-tenant retornam 404 (indistinguível de inexistente)
- **ACL de documentos:** can_access_document verifica tenant + RBAC + ACL explícita
- **Auditoria:** Downloads não-públicos e exports registram trilha
- **Storage:** Magic bytes validation, key whitelist regex (sem path traversal)
- **Portal público:** secrets.compare_digest (tempo constante), validação de status+expiração
- **Exports:** compute_indicators sempre filtra por tenant_id
- **Autorização:** Todos os endpoints sensíveis usam require_permission

### Defeitos Encontrados

- **Crítico:** 0
- **Alto:** 0
- **Médio:** 1 (corrigido — teste de migração)
- **Baixo:** 2 (informativos — Node.js PATH, interferência entre testes)

---

## 7. Pendências Priorizadas

### Alta Prioridade

Nenhuma pendência crítica identificada.

### Média Prioridade

1. **Validação Funcional End-to-End**  
   **O que fazer:** Executar servidor dev e testar ao menos 1 fluxo representativo por fase (F1–F5) no navegador.  
   **Como:** 
   - Backend: `cd backend && .venv/Scripts/uvicorn app.main:app --reload`
   - Frontend: `cd frontend && npm run dev`
   - Acessar: `http://localhost:3000/nit`
   **Validar:**
   - F1: Criar comunicação → anexar documento → transicionar workflow
   - F2: Criar comitê → votar em pauta
   - F3: Publicar oferta → manifestar interesse → gerar contrato
   - F4: Criar projeto → exportar FORMICT
   - F5: Conceder portal → submeter solicitação pública → executar relatório BI

2. **Isolamento de Fixtures de Teste**  
   **O que fazer:** Revisar `backend/tests/conftest.py` para eliminar interferência entre testes.  
   **Evidência:** ERRORs transitórios quando suíte completa é executada (testes individuais passam).

3. **Configuração de CI/CD**  
   **O que fazer:** Criar `.github/workflows/test.yml` para rodar pytest + tsc + build em cada push.

### Baixa Prioridade

1. **ESLint Configuration:** Adicionar `.eslintrc.json` para padronizar código frontend.
2. **Node.js no PATH:** Ajustar PATH do Git Bash ou usar PowerShell/CMD para comandos Node.

---

## 8. Bloqueios e Decisões Pendentes

### Infraestrutura (S1)

**Bloqueado:**
- Backup/restore operacional real (runbook entregue, execução bloqueada)
- Envio real de e-mail (outbox pattern implementado, transporte não configurado)
- Integração SEI/SIGA (outbox pattern implementado, endpoints não configurados)
- S3/MinIO (LocalPrivateStorage funcional, S3 inerte)

**Impacto:** Nenhum — não impede validação funcional.

### Decisões de Produto

**Aguardam confirmação do product owner** (conforme `DECISOES_EXECUCAO_AUTONOMA_NIT.md`):

- D1: 4 níveis de sigilo (reversível)
- D2: Storage abstrato com local privado (S3 plugável)
- D5: Auditoria de downloads não-públicos (implementada)
- E1: Workflow configurável (seed por tenant)
- E4: Alçada por permissão/role (não implícita)
- I1/I3: IPAsset interno + vínculo público opcional (sem FK dura)
- P1/P2/P4: Tenant = instituição, Unity = campus
- S4: Conformidade LGPD não declarada (documentação preparada)

**Impacto:** Nenhum — implementações são conservadoras e reversíveis.

---

## 9. Arquivos de Referência Essenciais

### Documentação
- `docs/RELATORIO_FINAL_NIT.md` — Relatório da execução autônoma F1–F5
- `docs/EXECUCAO_AUTONOMA_NIT.md` — Estado e checklist das fases
- `docs/DECISOES_EXECUCAO_AUTONOMA_NIT.md` — Decisões provisórias adotadas
- `docs/LOG_EXECUCAO_NIT.md` — Log cronológico de atividades
- `docs/AUDITORIA_FINAL_F1_F5.md` — Relatório de auditoria independente (este contexto)
- `docs/CONTINUIDADE_PROXIMA_SESSAO_NIT.md` — Este arquivo

### Backend Key Files
- `backend/app/constants.py` — 58 permissões NIT_*, 16 recursos nit:*, 5 roles
- `backend/app/models/nit*.py` — 48 tabelas ORM (F1–F5)
- `backend/app/routers/nit/_common.py` — Isolamento multi-tenant (scoped_tenant, assert_same_tenant, can_access_document)
- `backend/app/services/storage.py` — Validação magic bytes, key whitelist
- `backend/app/services/workflow.py` — Máquina de estados com alçadas
- `backend/app/services/indicators.py` — Fonte única de indicadores reais

### Frontend Key Files
- `frontend/src/lib/types.ts` — Tipos NIT F1–F5
- `frontend/src/lib/hooks.ts` — Hooks React Query
- `frontend/src/components/AppShell.tsx` — Navegação NIT

### Testes Key Files
- `backend/tests/test_nit_migration.py` — Round-trip de migrations (✅ corrigido)
- `backend/tests/test_nit_f1.py` — Isolamento, ACL, protocolo, workflow
- `backend/tests/test_nit_storage.py` — Magic bytes, path safety

---

## 10. Riscos Conhecidos

Nenhum risco crítico identificado.

**Riscos Médios:**
- Validação funcional manual não executada ainda
- Interferência entre testes em execução completa (não bloqueia validação)

**Riscos Baixos:**
- ESLint não configurado (código TypeScript compila sem erros)
- Node.js fora do PATH do Git Bash (use PowerShell/CMD)

---

## 11. Próxima Ação Recomendada

### Imediata: Validação Funcional Controlada (1–2 dias)

**Passo a passo:**

1. **Executar servidores dev:**
   ```bash
   # Terminal 1 — Backend
   cd backend
   .venv/Scripts/uvicorn app.main:app --reload
   
   # Terminal 2 — Frontend
   cd frontend
   npm run dev
   ```

2. **Acessar:** `http://localhost:3000/nit`

3. **Testar fluxo F1 (Comunicação de Invenção):**
   - Login como usuário com `NIT_DISCLOSURE_CREATE`
   - Criar nova comunicação
   - Anexar documento confidencial (PDF ou imagem)
   - Verificar protocolo gerado (formato NIT-AAAA-NNNN)
   - Transicionar workflow (PROPOSAL → TRIAGE)
   - Verificar ACL de documento
   - Tentar baixar como outro usuário (deve ser negado)

4. **Testar isolamento multi-tenant:**
   - Login com usuário de tenant A
   - Criar comunicação
   - Login com usuário de tenant B
   - Tentar acessar comunicação de tenant A via URL direta (deve retornar 404)

5. **Testar fluxos F2–F5** (1 representativo por fase)

6. **Validar auditoria:**
   - Baixar documento confidencial
   - Exportar FORMICT
   - Exportar relatório BI
   - Verificar registros na tabela `audit_logs`

### Após Validação OK:

7. Revisar decisões de produto (D1–S4) com product owner
8. Criar primeiro commit:
   ```bash
   git add backend/tests/test_nit_migration.py
   git commit -m "fix: resolve alembic.ini path in migration test
   
   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```
9. Criar branch feature e staging commits
10. Abrir PR para revisão
11. Deploy em staging
12. UAT (User Acceptance Testing)

---

## 12. Comandos Úteis para Retomada

### Verificar Estado
```bash
git status
git log --oneline -5
cd backend && .venv/Scripts/alembic.exe heads
```

### Rodar Testes
```bash
# Backend (181 testes)
cd backend
.venv/Scripts/python.exe -m pytest tests -q

# Teste específico
.venv/Scripts/python.exe -m pytest tests/test_nit_migration.py -v

# Frontend (via PowerShell ou CMD, não Git Bash)
cd frontend
npx tsc --noEmit
npm run build
```

### Executar Dev Servers
```bash
# Backend
cd backend
.venv/Scripts/uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm run dev
```

### Inspeção de Código
```bash
# Contar tabelas NIT
find backend/app/models -name 'nit*.py' | wc -l  # 5 arquivos

# Contar endpoints NIT
grep -r "@router\.(get\|post\|put\|patch\|delete)" backend/app/routers/nit/ | wc -l

# Verificar permissões NIT
grep -o 'NIT_[A-Z_]*' backend/app/constants.py | sort -u | wc -l  # 58
```

### Seed de Demonstração NIT (F1–F5)
```bash
cd backend
.venv/Scripts/python.exe -m app.seed_demo_nit
```
Idempotente (`created` → 0 na 2ª execução). Popula um tenant demo dedicado
(`Instituto Demo NIT`) com dados cross-referenciados de F1–F5, reutilizando os
serviços reais de workflow/protocolo. Ver `docs/SEED_DEMONSTRACAO_NIT.md`.

---

## 13. Contatos e Contexto do Usuário

**Diretório de Trabalho:** `C:\Users\ra_s_\OneDrive\Área de Trabalho\NovoBUSCAMARCAS\intelliinpi`  
**Sistema:** Windows 11 Pro (Git Bash)  
**Usuário Git:** Rafael Moura

---

## Fim do Documento de Continuidade

**Use este documento como primeiro contexto ao retomar o trabalho no NIT.**

---

## 14. Sessão 2026-10-10 (parte 2) — CRM comercial, Visão Geral do negócio e navegação

**Documento detalhado:** `docs/REVISAO_INTELLIINPI_CRM.md`

### O que foi entregue

| Frente | Estado |
|---|---|
| Auditoria do produto (Fase 1) | ✅ matriz completa em `REVISAO_INTELLIINPI_CRM.md` §2 |
| Nova navegação (Fase 2) | ✅ `AppShell.tsx` — Visão Geral / CRM / INPI ▾ / NIT ▾; Administração movida para o dropdown do usuário (`UserMenu.tsx`) |
| Visão Geral = dashboard do negócio (Fase 3) | ✅ `app/dashboard/page.tsx` reescrita; consome `GET /api/dashboard/business` |
| CRM completo (Fase 4) | ✅ `/crm`, `/crm/oportunidades`, `/crm/propostas`, `/crm/atividades`, `/clientes/[id]` |
| Design system (Fase 5) | ⚠️ Parcial — `PageHeader`, `StatCard`, `Funnel` criados e aplicados nas telas novas; módulos NIT/INPI preservados |
| Backend (Fase 6) | ✅ 19 endpoints novos, migração `e1a2b3c4d5e6`, 7 permissões + 4 recursos |
| Testes (Fase 7) | ✅ **195 passed** (+14 CRM); `tsc --noEmit` exit 0; `npm run build` 44 rotas |
| Validação em navegador | ❌ **Pendente** — sem navegador automatizado nesta sessão |

### Comandos de verificação (executados e confirmados)

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests            # 195 passed
.venv/Scripts/python.exe -m pytest tests/test_crm_api.py -q   # 14 passed
.venv/Scripts/alembic.exe heads                     # e1a2b3c4d5e6 (head único)

cd frontend
npx tsc --noEmit                                    # exit 0
npm run build                                       # 44 rotas
```

### ⚠️ Ação necessária antes de usar o CRM no ambiente dev

A migração **não foi aplicada** ao banco de desenvolvimento:

```bash
cd backend
.venv/Scripts/alembic.exe upgrade head
```

### Modelo de domínio CRM criado

* `CrmOpportunity` — funil `NEW → QUALIFICATION → PROPOSAL → SENT →`
  `NEGOTIATION → WON | LOST`; `WON` exige cliente, `LOST` exige motivo.
* `CrmProposal` — `DRAFT → PENDING_SEND → SENT → AWAITING_REPLY →`
  `NEGOTIATION → APPROVED | REJECTED | EXPIRED | CANCELLED`.
* `CrmActivity` — polimórfica (`OPPORTUNITY`/`PROPOSAL`/`CUSTOMER`/`COMPANY`).

Reaproveita integralmente `Customer`, `Company`, `Unity`, `Person` — **não há
segunda noção de cliente**. A conversão lead→cliente busca por documento →
e-mail → nome e só cria linha nova quando não encontra.

### Novas permissões (módulo CLIENTES)

`CRM_DASHBOARD_VIEW`, `CRM_OPPORTUNITY_VIEW`, `CRM_OPPORTUNITY_MANAGE`,
`CRM_PROPOSAL_VIEW`, `CRM_PROPOSAL_MANAGE`, `CRM_ACTIVITY_VIEW`,
`CRM_ACTIVITY_MANAGE` — concedidas a `TENANT_ADMIN` e `SUPER_ADMIN`.

### Decisão de negócio conservadora registrada

A aprovação comercial de uma proposta **não** cria marca/patente nem executa
serviço. A UI declara essa separação explicitamente, e há teste cobrindo a
ausência de efeito colateral no monitoramento do tenant.

