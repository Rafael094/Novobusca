# Auditoria Técnica — IntelliINPI

**Data:** 2026-10-09
**Natureza:** Auditoria somente leitura.

---

## 1. Inventário de arquitetura

### 1.1 Estrutura real de diretórios (verificada)

```
intelliinpi/
  backend/
    alembic/{env.py, versions/*.py}        # 6 migrações
    app/
      main.py            # factory FastAPI + CORS + handler 500
      config.py          # Settings (pydantic-settings, .env)
      constants.py       # MODULES/PERMISSIONS/RESOURCES/ROLES
      db.py              # engine + SessionLocal + Base
      deps.py            # auth, require_permission/module, client_meta
      security.py        # Argon2id + JWT (access/refresh)
      rbac.py            # build_access_context + AccessContext
      audit.py           # record_audit()
      rate_limit.py      # LoginRateLimiter (in-memory)
      export.py          # rows_to_csv() streaming
      seed.py            # seed idempotente
      mixins.py          # UUID PK / Timestamp / SoftDelete
      models/{auth,rbac,company,marcas,patentes,inpi}.py
      routers/{auth,marcas,patentes,search,analises,dashboard,clientes}.py
      routers/admin/{access_control,users,tenants,audit,modules,roles,inpi_sync}.py
      schemas/{auth,rbac,company,inpi,analise,search}.py
      services/deepseek.py
    tests/               # 12 arquivos, 94 testes
  frontend/
    src/app/{login,dashboard,marcas,patentes,monitoramento,analises,clientes,relatorios,admin/*}
    src/components/{AppShell,MarcaBadges,ui,charts}
    src/lib/{api,hooks,marcas,masks,types}.ts
  ingestion/             # discover→download→extract→analyze→load
  database/              # 01_extensions.sql, 02_indexes.sql, 03_fts_search.sql, reset_db.py
  scripts/bootstrap.ps1
  reports/               # 3 relatórios + logs
  docs/                  # (vazio antes desta auditoria; agora contém os 9 relatórios)
```

**[CÓDIGO]** confirmado por listagem recursiva.

### 1.2 Controle de versão

**Falha:** `git status` na raiz retornou `fatal: not a git repository`. **Não há git.** Isso impede rastrear alterações e colaborar com segurança. Severidade **P0**.

---

## 2. Backend — análise

### 2.1 Separação de responsabilidades

- **Pontos fortes:** clara separação `models` / `schemas` / `routers` / `services`. Dependências via `Depends`. Configuração centralizada em `Settings`.
- **Ausência:** **não há camada de `services` de domínio** (exceto `deepseek`). Toda a lógica de negócio reside nos routers (ex.: `routers/marcas.py` tem 572 linhas com montagem de detalhe, monitoramento, export e logo). Para o NIT isso não escala — recomenda-se introduzir `services/` de domínio nas novas fases.

### 2.2 Tratamento de erros

- `main.py` instala um handler genérico para `Exception` → 500 `{"detail": "Erro interno do servidor."}` **[CÓDIGO]**.
- Erros de domínio usam `HTTPException` com mensagens em pt-BR.
- **Risco:** o handler genérico engole a exceção sem log estruturado — não há observabilidade de falhas **[CÓDIGO]**.

### 2.3 Transações e concorrência

- Sessão por request via `get_db()`; `autoflush=False`, `expire_on_commit=False` **[CÓDIGO]**.
- Pool: `pool_size=10, max_overflow=20, pool_pre_ping=True` **[CÓDIGO]**.
- Commit explícito nos routers. **Não há tratamento de `IntegrityError`** em criação de entidades (ex.: `create_company` faz `db.add` + `commit` sem catch de conflito de unicidade) **[CÓDIGO]** — risco de 500 em duplicidade.

### 2.4 Paginação, filtros e ordenação

- Padrão consistente: `page`/`page_size` com `Query(ge=1, le=100)`, `LIMIT/OFFSET` + `COUNT(*)` da subquery **[CÓDIGO]** em marcas, patentes e clientes.
- **Risco de desempenho:** `COUNT(*)` sobre `marcas` (6,6M) com filtro `ILIKE '%x%'` faz varredura completa a cada página **[PARCIAL]**.
- Ordenação em marcas é fixa (`data_deposito DESC NULLS LAST`); o usuário não escolhe a ordenação **[CÓDIGO]**.

### 2.5 Validação de entrada

- Pydantic v2 com `EmailStr`, `Field(min_length, max_length)`, `Literal` para enums simples (`MatrizType`) **[CÓDIGO]**.
- Falta validação de formato de CPF/CNPJ (armazenados como `String` livre) **[CÓDIGO]**.

### 2.6 Idempotência

- `seed.py` é idempotente (upsert por `code`) **[CÓDIGO] + [DOC]**.
- Ingestão tem idempotência via `force=True` (DELETE antes do insert) e checkpoint **[CÓDIGO] + [DOC]**.
- **Ausência:** endpoints de criação não são idempotentes (sem chave de idempotência) — aceitável, mas a duplicidade não é tratada com erro amigável.

### 2.7 Logs e observabilidade

- **Não há logging estruturado** na API (nenhum `structlog`/`logging` configurado nos routers) **[CÓDIGO]**.
- O pipeline de ingestão usa `util.get_logger` **[CÓDIGO]**.
- Sem métricas (Prometheus/OpenTelemetry) e sem tracing. **Lacuna relevante para operação SaaS.**

### 2.8 Documentação OpenAPI

- `docs_url="/api/docs"`, `redoc_url="/api/redoc"`, `openapi_url="/api/openapi.json"` **[CÓDIGO]**.
- `DESCRIPTION` da app documenta auth, multi-tenancy e RBAC **[CÓDIGO]**.

### 2.9 Operações demoradas / processamento assíncrono

- `/api/admin/inpi/sync` chama o pipeline **sincronamente no processo da API** (`run(categories=..., force=...)`) **[CÓDIGO]** — bloqueia o worker. **Risco P1** para operação real; deveria ser fila/background worker.
- A análise IA chama o DeepSeek com `urlopen` **síncrono** (timeout 60s) **[CÓDIGO]** — bloqueia o worker até 60s.

### 2.10 Integrações externas

- **DeepSeek:** cliente real via `urllib`; degrada para 503 (não configurado) ou 502 (falha) **[CÓDIGO]**.
- **INPI:** apenas download de datasets no pipeline; **não há consumo da BuscaWeb / API do INPI em tempo real** — o SPIKE confirma a ausência do link de detalhe oficial **[DOC]**.
- **Logos:** downloader do pePI (`ingestion/logos.py`) com preflight de TLS **[CÓDIGO] + [DOC]**.

---

## 3. Frontend — análise

### 3.1 Organização

- App Router (Next.js 15). 16 arquivos em `src/app`, componentes reutilizáveis em `src/components` (`ui/index.tsx` com design system próprio, `charts/`, `AppShell`).
- Páginas: `login`, `dashboard`, `marcas`, `patentes`, `monitoramento`, `analises`, `clientes`, `relatorios`, `admin` (+`modulos`, `tenants`, `usuarios`). **[CÓDIGO]**

### 3.2 Separação de responsabilidades

- Boa: `lib/api.ts` (cliente tipado), `lib/hooks.ts` (React Query), `lib/types.ts` (tipos), `lib/marcas.ts`/`masks.ts` (utilidades). Páginas consomem hooks. **[CÓDIGO]**

### 3.3 TanStack Query

- Uso consistente de `useQuery`/`useMutation` com `invalidateQueries` **[CÓDIGO]**.
- **Ausência:** a busca de marcas dispara a cada tecla (sem `debounce`), gerando requisições parciais **[DOC]** (`SPIKE_...`, seção 4).

### 3.4 Estados de interface

- Há tratamento de loading/erro/vazio em telas principais (inferido dos componentes `ui`).
- **Não verificado em execução** — frontend não foi rodado **[NÃO VERIF]**.

### 3.5 Tratamento de tokens

- `localStorage` + refresh transparente em 401 **[CÓDIGO]**. **Risco XSS (P1)** — não há cookie httpOnly.

### 3.6 Acessibilidade e responsividade

- Tailwind com breakpoints (`lg:`, `sm:`) e overlay mobile em `AppShell` **[CÓDIGO]**.
- **Não há ARIA explícito** nem teste de acessibilidade **[NÃO VERIF]**.

### 3.7 Tipos TypeScript

- `types.ts` com 10.964 bytes de tipos espelhando os schemas do backend **[CÓDIGO]** — bom alinhamento manual (risco de drift por não ser gerado).

---

## 4. Banco de dados — análise

### 4.1 Modelos, constraints e índices

- Todas as tabelas usam PK UUID (`UUIDPrimaryKeyMixin`), `created_at`/`updated_at` (`TimestampMixin`) e `deleted_at` (`SoftDeleteMixin`) **[CÓDIGO]**.
- Unicidade natural: `uq_marcas_codigo_interno`, `uq_patentes_codigo_interno`, `uq_<tabela>_tenant_code`, `uq_<tabela>_tenant_cnpj` **[CÓDIGO]**.
- Índices de busca: em `numero_inpi`, `codigo_situacao`, `codigo_interno` das tabelas-filhas, `depositante`/`autor` **[CÓDIGO]**.
- Índices pós-carga (SQL manual): `pg_trgm`, `unaccent`, `fold()`, GIN trigram, `tsvector` português **[CÓDIGO] + [DOC]**.

### 4.2 Integridade referencial

- FKs com `ondelete` explícito (CASCADE/SET NULL) **[CÓDIGO]**.
- **Exceção relevante:** as tabelas-filhas de marcas/patentes (`marcas_depositantes`, `patentes_inventores`, etc.) **NÃO têm FK** para a tabela-mãe — o vínculo é lógico via `codigo_interno` **[CÓDIGO]**. Isso é intencional (volume/deduplicação), mas impede integridade referencial garantida pelo banco.
- Relação `marcas → marcas_depositantes` é `viewonly` com `primaryjoin` por `codigo_interno` **[CÓDIGO]**.

### 4.3 Estratégia de tenant

- Todo dado de aplicação carrega `tenant_id` FK → `tenants.id` (**exceto** os dados públicos de PI, que são globais) **[CÓDIGO]**.
- `Tenant` é a raiz e **não tem** `tenant_id` próprio **[CÓDIGO]**.

### 4.4 Compatibilidade modelo × migration × banco

- 6 migrações; a `e5f6a7b8c9d0_restructure_core_rbac.py` (37.697 bytes) faz a reestruturação core, data-preserving e com `downgrade` completo **[CÓDIGO] + [DOC]**.
- Contagens reais conferem com o relatório de importação **[verificado por contagem]**.

---

## 5. ETL / Ingestão — análise

### 5.1 Catálogo e pipeline

- Catálogo declarativo em `ingestion/datasets.py` (2 categorias; 18 datasets registrados no banco) **[CÓDIGO]**.
- Orquestração `discover → download → extract → analyze → load` em `import_all.py` **[CÓDIGO]**.
- Carga via **DuckDB + extensão `postgres`** com `INSERT INTO pg.<tabela> SELECT ... FROM read_csv(...)` **[DOC]**.

### 5.2 Deduplicação e idempotência

- `QUALIFY row_number() OVER (PARTITION BY <chave>) = 1` quando há UNIQUE de coluna única; caso contrário `SELECT DISTINCT` **[DOC]**.
- `force=True` faz DELETE antes do insert **[DOC]**.
- Checkpoints resumíveis (`InpiImportCheckpoint`) **[CÓDIGO]**.

### 5.3 Rastreabilidade

- `InpiDataset` guarda `sha256`, `file_size`, `reference_date`, `source_url`, `status` **[CÓDIGO]**.
- `InpiImport` guarda contadores (read/inserted/updated/skipped/failed) e duração **[CÓDIGO]**.
- `InpiImportError` guarda linha bruta e erro por linha, permitindo reprocessamento **[CÓDIGO]**.

### 5.4 Lacunas de qualidade

- **Sem validação de schema da fonte** (se o INPI mudar colunas, o `read_csv` pode falhar silenciosamente ou quebrar) **[CÓDIGO]**.
- **Sem reconciliação automática** de contagens pós-carga no código (o relatório é manual) **[PARCIAL]**.
- **Sem alerta** quando um dataset fica `FAILED` **[CÓDIGO]**.

---

## 6. Desempenho — riscos identificados (sem benchmark)

> Nenhuma medição real foi feita (**[PARCIAL]**). Os pontos abaixo são inferidos de código e índices.

| Área | Risco | Evidência |
|---|---|---|
| Busca exata de marca | Usa `fold()` funcional — bom, indexado | `routers/marcas.py` |
| Busca "contains" | `ILIKE '%x%'` sem trigram explícito → full scan | `_base_query` |
| Busca de patentes | `EXISTS` correlacionado + `ILIKE` em `titulo`/`resumo` | `routers/patentes.py` |
| `COUNT(*)` | Sobre 6,6M linhas a cada request | routers |
| Export CSV | Monta `StringIO` completo em memória antes de streamar | `app/export.py` |
| Dashboard | Agregações `GROUP BY` sobre `marcas` inteira | `routers/dashboard.py` |
| Análise IA | `urlopen` síncrono, até 60s | `services/deepseek.py` |
| Sync INPI | Executa pipeline no worker da API | `admin/inpi_sync.py` |

**Recomendação para medir:** `EXPLAIN (ANALYZE, BUFFERS)` nas queries principais; `pg_stat_statements`; teste de carga com `locust`/`k6` fora de produção.

---

## 7. Testes — análise

**[TESTE]** `pytest -q` executado nesta auditoria: **94 testes, 94 aprovados**.

Cobertura funcional por arquivo:

| Arquivo | Foco |
|---|---|
| `test_tenant_isolation.py` | Isolamento multi-tenant (obrigatório) |
| `test_rbac_policies.py` | 3 caminhos de policy, escopo Company/Unity |
| `test_rbac.py` | RBAC básico |
| `test_monitoramento.py` | Monitoramento seletivo por usuário |
| `test_marcas_search.py` / `test_marcas_enrich.py` | Busca e enriquecimento de marcas |
| `test_company_customer.py` / `test_clientes_api.py` | CRM |
| `test_auth.py` | Autenticação |
| `test_analises.py` | Análise IA |

**Lacunas de teste:** sem teste de carga, concorrência, migração (upgrade/downgrade), upload/download de arquivos, acessibilidade e contrato. Ver `ROADMAP_IMPLEMENTACAO_NIT.md`, seção de QA.

---

## 8. Riscos técnicos classificados

| # | Risco | Sev. | Evidência | Recomendação |
|---|---|---|---|---|
| T1 | Sem git | P0 | `git status` falha | Inicializar repositório e versionar |
| T2 | Sync INPI síncrono na API | P1 | `admin/inpi_sync.py` | Mover para worker/fila |
| T3 | Sem logging/observabilidade | P1 | ausência em routers | Adicionar logging estruturado |
| T4 | `IntegrityError` não tratado | P1 | `clientes.py` | Catch e retornar 409 |
| T5 | Export CSV em memória | P2 | `export.py` | Streaming real por chunks |
| T6 | Sem validação de schema de fonte | P2 | `ingestion/dataset*` | Validar colunas esperadas |
| T7 | Ausência de camada `services` | P2 | routers grandes | Introduzir em novos módulos |
| T8 | Tipos TS manuais (drift) | P3 | `types.ts` | Gerar de OpenAPI |


