# Plano de Testes e Critérios de Aceite — Evolução NIT

**Data:** 2026-10-09 · **Natureza:** Planejamento.
**Base verificada:** 94 testes existentes, 100% aprovados (`pytest -q`), contra PostgreSQL dedicado (`intelliinpi_test`, criado no `conftest.py`).

> **Princípio:** o número de testes **não** é medida suficiente de qualidade. O critério é a cobertura dos cenários de risco (isolamento, autorização, confidencialidade, integridade de dados).

---

## 1. Preservação da suíte atual

- Os 94 testes permanecem **gate de regressão obrigatório** em toda fase.
- Nenhuma entrega é aceita se **qualquer** teste existente ficar vermelho.
- Novos testes seguem o padrão de `backend/tests/conftest.py` (DB dedicado, fixtures de tenant/usuário/tenant A×B).

---

## 2. Camadas e tipos de teste

| Tipo | Alvo | Exemplo de cenário | Fase |
|---|---|---|---|
| **Unitário** | Serviços de domínio | Geração de protocolo; validação de transição; cálculo de participação de inventor | F1 |
| **Integração** | Modelo + serviço + DB | Criar comunicação com inventores internos e externos; versionamento de documento | F1 |
| **Endpoints** | Contrato HTTP | `POST /api/nit/disclosures` retorna 201 + protocolo; `GET` lista com paginação | F1 |
| **Autorização** | `require_permission` + RBAC | Sem `NIT_DISCLOSURE_VIEW` → 403; DENY explícito vence | F1 |
| **Isolamento de tenant** | tenant A × B | Tenant A não vê comunicação/ativo de B (espelha `test_tenant_isolation.py`) | F1 |
| **Escopo por unidade** | Company/Unity | Usuário da Unidade A → 403 em ativo da Unidade B | F1 |
| **Documentos confidenciais** | ACL + storage | Doc `restrito` inacessível sem ACL; download gera `AuditLog` | F1 |
| **Transições de workflow** | Máquina de estados | Transição não permitida → 409; alçada insuficiente → 403 | F1 |
| **Concorrência** | Transição/edição simultânea | Duas transições concorrentes → apenas uma vence | F2 |
| **Migrações** | Alembic | `upgrade head` + `downgrade -1` em DB vazio e com dados | F1 |
| **Contrato frontend↔backend** | OpenAPI/Tipos | Campos obrigatórios batem com `types.ts`; 400 em payload inválido | F1 |
| **Desempenho** | Buscas públicas | `EXPLAIN ANALYZE` sem Seq Scan; p95 dentro do alvo | F1/F2 |
| **Acessibilidade** | Telas novas | Contraste, foco, ARIA em fluxos-chave | F2 |
| **Backup/restore** | Operação | Dump + restore reproduz estado | F0 |

---

## 3. Testes mínimos por domínio novo

| Domínio | Testes obrigatórios |
|---|---|
| Invention Disclosure | CRUD, protocolo único por tenant, inventores externos sem conta, isolamento tenant/unidade |
| Documents | upload com MIME válido/inválido, limite de tamanho, ACL, download auditado, URL expira |
| Workflow/Evaluation | transições válidas/inválidas, alçada, parecer por tipo |
| IP Asset | CRUD escopado, vínculo opcional a registro público, procedência preservada |
| Public link | associação sem FK dura; `external_ref` inexistente não quebra |
| F2 Committees | quórum, voto, conflito de interesse |
| F3 TT/Contracts | pipeline, vigência, obrigações, alertas |

---

## 4. Critérios de aceite transversais (Definition of Done de qualidade)

Uma entrega **só é considerada concluída** se:
1. `pytest -q` verde (94 antigos + novos).
2. Novo endpoint protegido por `require_permission` (ou justificativa explícita).
3. Teste de **isolamento de tenant** para toda entidade interna.
4. Teste de **escopo por unidade** para toda entidade escopável.
5. Migração com **downgrade** funcional e dado preservado.
6. Auditoria emitida nos eventos sensíveis (submissão, decisão, download).
7. Sem segredo/credencial nova em código ou config versionada.
8. Documentação de endpoint (OpenAPI) coerente com os schemas.

## 5. Bloqueio por regressão

- Pipeline/validação local deve rodar `pytest -q` antes de qualquer merge.
- Regressão em teste existente **bloqueia** a entrega até correção ou aprovação explícita documentada.
- Testes de isolamento e de confidencialidade são **não negociáveis** (não podem ser marcados como skip).
