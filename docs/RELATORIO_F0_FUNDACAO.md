# Relatório de Execução — FASE 0 (Fundação)

**Data:** 2026-10-09 · **Fase:** F0 · **Natureza:** Execução real (código alterado e testado) + bloqueios documentados.
**Regra de honestidade:** cada item é classificado como **Implementado e testado**, **Parcial** ou **Bloqueado**.

---

## 1. Resumo executivo

A F0 entregou correções de segurança **independentes de decisão de produto** e todas foram
validadas por testes automatizados. Itens que dependem de infraestrutura (**S1**) ou de decisão
de produto (**D1/D2/D5, E1/E4, I1/I3, P1/P2/P4, S4**) permanecem **bloqueados de forma explícita**,
sem implementação especulativa.

- Suíte de testes: **109 aprovados** (94 originais + 15 novos), 0 falhas.
- Frontend: `tsc --noEmit` **exit 0**; `npm run build` **exit 0** (16 rotas).
- Nenhum commit/push/deploy. Nenhuma migração nova. Nenhuma operação destrutiva.

---

## 2. Estado inicial × final

| Item | Inicial | Final |
|---|---|---|
| Testes backend | 94 aprovados | **109 aprovados** |
| `ENVIRONMENT` | inexistente | implementado (default `local`) |
| Segredo default em produção | aceito silenciosamente | **recusado no boot** |
| Papel de outro tenant | aceito (R-08) | **recusado (403)** |
| Erro 500 | sem log / sem stack | **logado com stack; resposta genérica** |
| Conflito de integridade | 500 | **409** |
| Correlação de requisição | inexistente | **`X-Request-ID` + logs JSON** |
| Backup/restore | não documentado | **runbook + scripts (sintaxe validada)** |
| Git | branch `main`, remote `origin` presente | inalterado (sem push) |

---

## 3. Arquivos criados e alterados

| Arquivo | Ação | Finalidade |
|---|---|---|
| `backend/app/config.py` | alterado | `ENVIRONMENT` + recusa de segredos default fora de local (R-04) |
| `backend/app/logging_config.py` | **novo** | logging JSON + `request_id` por contexto (R-10) |
| `backend/app/main.py` | alterado | middleware request-id; handler de integridade → 409; 500 com stack logado |
| `backend/app/routers/admin/users.py` | alterado | `_set_roles` valida tenant do papel (R-08) |
| `backend/tests/conftest.py` | alterado | `ENVIRONMENT=test` (mantém a suíte legítima) |
| `backend/tests/test_foundation_hardening.py` | **novo** | 15 testes dos controles de F0 |
| `backend/scripts/backup_db.ps1` | **novo** | backup `pg_dump -Fc` sem segredos embutidos |
| `backend/scripts/restore_db.ps1` | **novo** | restore para banco isolado, exige `-Confirm` |
| `.env.example` | alterado | documenta `ENVIRONMENT` e a política de segredos |
| `docs/RUNBOOK_BACKUP_RESTORE.md` | **novo** | procedimento, RPO/RTO propostos, teste de restore |
| `docs/PENDENCIAS_INFRA_F0.md` | **novo** | checklist objetivo do que falta (S1) |
| `docs/RELATORIO_F0_FUNDACAO.md` | **novo** | este relatório |

---

## 4. Controles de F0 — evidência por item

| ID | Controle | Status | Evidência |
|---|---|---|---|
| F0-1 | Recusa de segredos default fora de local (R-04) | **Implementado e testado** | `test_production_refuses_*` (6 testes); verificação manual CLI |
| F0-2 | Papel de outro tenant recusado (R-08) | **Implementado e testado** | `test_tenant_admin_cannot_attach_another_tenants_role` (403 + sem concessão) |
| F0-3 | Logging estruturado + `request_id` (R-10) | **Implementado e testado** | `test_response_echoes_request_id`, `test_json_logging_formatter_*` |
| F0-4 | 500 sem vazamento de detalhes | **Implementado e testado** | `test_internal_error_returns_generic_500` |
| F0-5 | Runbook de backup/restore | **Scripts criados; sintaxe validada**; execução real **Bloqueada** | `pg_dump` ausente no PATH; requer ambiente isolado (S1) |
| F0-6 | Governança Git | **Verificado** | remote `origin` presente; nenhum push; `.env` não versionado |
| F0-7 | Checklist de infraestrutura faltante | **Documentado** | `PENDENCIAS_INFRA_F0.md` |

### Nota sobre RBAC e escopo intra-tenant (R-01 / B1-3)

A auditoria aponta pontos em que `scoped_resources` é calculado mas não aplicado em entidades
**internas**. Como essas entidades pertencem ao domínio NIT (ainda **não implementado** por
depender de decisões bloqueadoras), **não há hoje onde aplicar o escopo sem criar código
especulativo**. O item fica registrado como **pendente de F1** e será aplicado junto às
entidades novas (ver `PLANO_SEGURANCA_E_PRODUCAO.md`, B1-3).

---

## 5. Testes executados

```
cd intelliinpi/backend
.\.venv\Scripts\python.exe -m pytest -q --no-header -p no:cacheprovider
# => 109 passed in 75.87s
```

Frontend:
```
cd intelliinpi/frontend
npx tsc --noEmit   # exit 0
npm run build      # exit 0 (16 rotas)
```

> **Limitação conhecida (não é regressão):** o projeto **não possui configuração ESLint** nem o
> binário `eslint` em `devDependencies`. `npm run lint` (`next lint`) é interativo e tenta
> instalar/configurar o ESLint no primeiro uso — por isso não é usado como gate. O gate de
> frontend válido neste projeto é `tsc --noEmit` + `npm run build`.

---

## 6. Bloqueios explícitos (não implementados)

| Bloqueio | Decisão/Recurso necessário | Fase afetada |
|---|---|---|
| Documentos confidenciais (storage privado, níveis, ACL, auditoria de download) | **D1/D2/D5 + S4** | F1 |
| Workflow (estados, transições, alçadas) | **E1/E4** | F1 |
| Ativos institucionais (`IPAsset` + vínculo público) | **I1/I3** | F1 |
| Escopo institucional/portfólio | **P1/P2/P4** | F1 |
| Execução real de backup/restore | **S1** (ambiente isolado + `pg_dump`) | F0 (operacional) |
| Observabilidade ativa (logs centralizados, métricas, alertas) | **S1** | F0/F4 |
| Rate limiting distribuído | Redis/Valkey no alvo | F4 |

**Nada disso foi implementado por antecipação.** A implementação de F1 deve começar somente após
respostas às 7 perguntas de `DECISOES_PENDENTES_PRODUTO.md` §4.

---

## 7. Riscos remanescentes

| Risco | Prioridade | Próximo passo |
|---|---|---|
| R-04 (segredos) | **Mitigado** | — |
| R-08 (papel cross-tenant) | **Mitigado** | — |
| R-10 (logging) | **Mitigado** | Centralização depende de S1 |
| R-09 (backup/restore) | **Parcial** | Provisionar ambiente isolado e executar teste |
| R-01 (escopo intra-tenant) | **Aberto** | Aplicar em F1 nas entidades NIT |
| R-05 (sessão/XSS) | **Aberto** | Cookie httpOnly + CSP antes do piloto (B2-1) |
| R-11 (LGPD) | **Aberto** | RIPD/política antes de docs sigilosos (S4) |

---

## 8. Estado do Git

- Branch: `main` (inalterada).
- Modificados: `.env.example`, `backend/app/config.py`, `backend/app/main.py`,
  `backend/app/routers/admin/users.py`, `backend/tests/conftest.py`.
- Novos (não rastreados): `backend/app/logging_config.py`, `backend/scripts/`,
  `backend/tests/test_foundation_hardening.py`, `docs/`.
- **Nenhum commit, push ou deploy** (aguardando autorização explícita).

---

## 9. Checklist de aceite (F0)

| Critério | Status | Evidência |
|---|---|---|
| Funcionalidades existentes continuam funcionando | **Aprovado** | 94 testes originais verdes |
| Regressão sem testes desabilitados | **Aprovado** | 109 passed, sem skip |
| Correções independentes implementadas | **Aprovado** | itens F0-1..F0-4 |
| Testes dos novos controles | **Aprovado** | 15 novos testes |
| Sem segredos novos em código/config versionada | **Aprovado** | apenas `.env.example` rastreado |
| Frontend compila e contratos coerentes | **Aprovado** | tsc exit 0; build exit 0 |
| Backup/restore reproduzível | **Parcial** | runbook + scripts; execução bloqueada (S1) |
| Observabilidade ativa | **Bloqueado** | depende de S1 |
| Isolamento intra-tenant aplicado | **Bloqueado (F1)** | sem entidade interna ainda |
| Documentação reflete o código real | **Aprovado** | este relatório + runbook + pendências |

---

## 10. Próximo passo

1. **Aguardar** respostas às 7 perguntas objetivas (S1 em especial).
2. Após autorização, iniciar **F1** (modelo de domínio + comunicação de invenção + documentos +
   workflow + ativos) com migrações pequenas e testadas em banco isolado.
3. Executar o teste real de backup/restore quando houver ambiente isolado (S1).
