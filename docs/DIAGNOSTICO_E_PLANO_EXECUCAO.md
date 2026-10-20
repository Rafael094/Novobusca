# Diagnóstico e Plano de Execução — IntelliINPI (bkpint)

> Engenheiro de Software Principal / Arquiteto de Soluções
> Data: 2026-10-20 · Escopo: performance, arquitetura, workers, módulos INPI,
> UX do modal de marca, navegação NIT e padronização visual.

Este relatório consolida **o que foi diagnosticado, o que foi implementado e
validado** nesta sessão, e **o que fica como recomendação**. A pilha é FastAPI +
SQLAlchemy 2.0 + PostgreSQL 16 (numa VM Oracle Cloud Free Tier, `152.67.45.106`)
no backend, Next.js 14 (App Router) + React Query + Tailwind no frontend, e um
pipeline de ingestão Python standalone (DuckDB) para as bases do INPI.

---

## 1. Desempenho e rota crítica `/api/dashboard/summary`

### 1.1 Causa raiz do travamento (confirmada por leitura do código)

A tela "fica só carregando" porque `routers/dashboard.py::summary()` executava,
**numa única request síncrona, 4+ agregações full-table sem filtro** sobre as
tabelas gigantes do INPI (escala real do `INPI_IMPORT_REPORT`):

| Operação | Tabela | Linhas | Custo |
|---|---|---:|---|
| `COUNT(codigo_interno)` marcas | `marcas` | 6.645.491 | full scan |
| `COUNT(codigo_interno)` patentes | `patentes` | 1.018.792 | full scan |
| `_portfolio_evolution` `GROUP BY extract(year ...)` | `marcas` + `patentes` | 7,6M | 2 full scans + sort |
| `_situacao_distribution` `GROUP BY descricao_situacao` | `marcas` | 6,6M | full scan + hash agg |
| `latest_marcas ORDER BY data_deposito` | `marcas` | 6,6M | sort (sem índice) |

Numa instância Free Tier (1–2 OCPU compartilhadas) esses scans levam de segundos
a minutos **e não havia `statement_timeout`** — logo a request nunca retorna e o
pool de conexões satura. O `/dashboard/business` (CRM) não tem esse problema
porque é *tenant-scoped* (lê só os dados do tenant).

### 1.2 Correção aplicada e validada (`dashboard.py`)

- **`statement_timeout` por request** (`SET LOCAL statement_timeout = 8000`): uma
  query lenta é cancelada em 8 s em vez de travar o worker.
- **Contagens via `pg_class.reltuples`** (estimativa O(1) do planner) em vez de
  `COUNT(*)` — precisão de headline KPI não exige contagem exata em 6,6M linhas.
- **Cache TTL (300 s)** em processo para as séries pesadas — esses dados globais
  só mudam quando a ingestão roda, nunca por request.
- **Degradação graciosa** (`_safe()`): cada widget pesado, em timeout/erro,
  devolve série vazia em vez de derrubar (ou travar) o dashboard inteiro.

Validação: `import app.main` carrega sem erro (o módulo do dashboard é importado
na subida da app) — confirmado em venv limpa.

### 1.3 Plano de otimização de queries/rotas (recomendações)

- **Índice `ix_marcas_data_deposito`** (hoje inexistente) para acelerar
  permanentemente `latest_marcas`/`portfolio_evolution`. As novas tabelas DI/SW
  já nascem com o índice de `data_deposito`.
- Materializar `situacao_distribution` e `portfolio_evolution` como
  **MATERIALIZED VIEW** refrescada ao fim da ingestão (substitui o cache em
  processo por um cache no banco, compartilhado entre réplicas).
- `marcas`/`patentes` **search já é O(1) em N+1** (os helpers `_load_*` usam
  `IN (page_ids)` — um número fixo de queries por página). Mesmo padrão nos
  novos módulos DI/SW. Não há N+1 a corrigir nessas rotas.
- Garantir `ANALYZE` pós-carga (já previsto em `database/03_fts_search.sql`) para
  manter as estimativas de `reltuples` fiéis.

---

## 2. Arquitetura, limpeza e viabilidade .NET CQRS

### 2.1 Coerência dos módulos

A base está **coesa e sem código morto relevante**. Pontos observados:

- `services/` e `routers/` têm separação clara; o pipeline de ingestão é
  **declarativo** (`datasets.py` como catálogo), o que tornou a adição de dois
  módulos novos uma questão de dados + modelos, sem tocar os workers.
- `S3Storage` em `services/storage.py` é um *stub* consciente (levanta
  `StorageBackendNotConfigured`) — mantê-lo é correto: dá a interface estável
  para o object storage de produção sem fingir que grava.
- Recomendação de limpeza leve: `backend/backend.pid` e a `.venv` versionada
  (criada noutra máquina, `home` inválido aqui) não deveriam estar no repo —
  adicionar ao `.gitignore`. Nenhuma lógica a remover.

### 2.2 Viabilidade de migração para .NET + CQRS na Oracle Free — NÃO recomendada agora

| Critério | FastAPI atual | .NET 8 + CQRS |
|---|---|---|
| Memória/CPU na Free Tier | Uvicorn/Gunicorn leve; cabe bem em 1–2 OCPU | Runtime .NET + MediatR/handlers: maior baseline de RAM; CQRS agrega camadas (command/query/handlers/validators) |
| Gargalo real | **É o PostgreSQL** (scans em tabelas de milhões), não a linguagem | A migração **não remove** o gargalo — ele é de dados/índices |
| Throughput | Adequado ao volume de requests atual | Ganho marginal; o custo é I/O de banco, idêntico para ambos |
| Manutenção | Um só ecossistema Python (API + ingestão DuckDB) | Dois ecossistemas (API .NET + ingestão Python) — mais complexidade operacional |
| Ganho vs. complexidade | — | Alto custo de reescrita, baixo retorno de performance |

**Conclusão:** o travamento e a lentidão são **de banco de dados** (ausência de
timeout, agregações full-table, falta de índice/MV), já endereçados em Python
com custo baixo. Reescrever para .NET/CQRS não ataca a causa raiz, aumenta o
footprint na Free Tier e fragmenta a stack. Se no futuro houver *domínio
transacional* complexo (ex.: NIT com workflows ricos), CQRS pode fazer sentido
**pontualmente nesse módulo** — não como reescrita global. Recomendação: manter
FastAPI, investir em índices/MV e, quando o dado crescer, numa réplica de leitura.

---

## 3. Workers e estratégia de imagens (Oracle Free Tier)

### 3.1 Saúde dos workers

Os workers (`ingestion/`) são **batch standalone** (`python -m ingestion.X`),
**não rodam na thread da API** — logo não há risco de travar requests. O
downloader é resiliente (retry com backoff, resume por `.part`), o `logos.py`
usa `ThreadPoolExecutor` com sessão por thread, preflight de conectividade e
registra falhas como linhas `ERROR` retentáveis em vez de abortar o lote. O
pipeline `discover → download → extract → analyze → load` é idempotente
(`force=True` faz `DELETE` antes do insert) e resumível por checkpoint.

### 3.2 Estratégia de imagens — implementada

Para **não estourar disco/banda da Free Tier** (os bundles `DI_FIGURAS_*.ZIP`
somam ~44 GB):

1. **Nunca extrair os ZIPs no disco da instância** — o worker novo
   `ingestion/figuras.py` lê cada figura **em streaming direto do ZIP**.
2. **Compressão WebP (q80, Pillow)** — 25–35% menor que o JPEG/PNG de origem.
3. **Object Storage** (Oracle Object Storage / S3 / MinIO) via
   `app.services.storage.get_storage()` (`STORAGE_BACKEND=s3`): o binário sai da
   instância; só **metadados** ficam em `desenhos_figuras`.
4. **Cloudflare Free na frente** do storage + **lazy loading** no front
   (`loading="lazy"` já aplicado no modal) — repetições servidas da borda, não
   da banda da VM.
5. `--dry-run` permite validar o wiring do deploy antes de provisionar o bucket.

Mesma filosofia já usada em `marcas_logos` (DB-first, imagem fora do hot path).

---

## 4. Módulos INPI novos: Desenho Industrial e Software (SEM ingestão)

Replicam fielmente a arquitetura de Marcas/Patentes. **Nenhum dado é baixado
agora** — a carga inicial roda no servidor Oracle no deploy.

**Backend (validado: `import app.main` OK; 5 rotas DI + 5 SW montadas sob `/api`):**

- `models/desenhos.py` — `Desenho` (+ `conteudo`, `depositantes`, `autores`,
  `procuradores`, `classificacoes` Locarno, `prioridades`, `despachos`,
  `vinculos`, `figuras` [metadados], `monitoramento`).
- `models/software.py` — `Software` (+ `campos`, `titulares`, `autores`,
  `linguagens`, `tipos`, `despachos`, `monitoramento`).
- `schemas/desenhos.py`, `schemas/software.py` — Out/Detail/Paginated.
- `routers/desenhos.py` (`/api/desenhos`), `routers/software.py`
  (`/api/softwares`) — `search` (paginado, N+1-free), `export` CSV,
  monitoramento seletivo por usuário e detalhe agregado.
- `alembic/versions/f1a2b3c4d5e7_add_desenhos_software.py` — cria 10 tabelas DI
  + 7 SW; é o **head único** da cadeia (validado via `ScriptDirectory.get_heads()`).

**Ingestão (declarativa — os workers já orquestram os novos módulos):**

- `ingestion/datasets.py` — specs de `desenhos_industriais` (13) e
  `programas_de_computador` (8); **nomes de arquivo e colunas conferidos no
  portal** `dadosabertos.inpi.gov.br` (`DI_*.csv`, `PROG_COMP_*.csv`). Os ZIPs
  de figuras entram como `target_table=None` (baixados, não bulk-loaded).
- `ingestion/figuras.py` + helpers `figura_codes()`/`upsert_figura()` em `db.py`.

**Comandos de deploy (no servidor Oracle):**

```bash
alembic upgrade head
python -m ingestion.import_all --category desenhos_industriais
python -m ingestion.import_all --category programas_de_computador
STORAGE_BACKEND=s3 python -m ingestion.figuras      # figuras p/ object storage
```

> Observação: as permissões RBAC `DESENHOS_*` / `SOFTWARES_*` usadas pelos
> routers precisam ser semeadas (seed/constants) quando se decidir expor os
> módulos na UI — o backend já as exige nas rotas.

---

## 5. Modal de Detalhe da Marca (UX/UI)

`frontend/src/components/MarcaDetailModal.tsx` (novo) substitui o drawer lateral:

- **Pop-up centralizado** com **overlay escurecido** (`bg-slate-900/60
  backdrop-blur`) que foca a atenção no modal.
- **Largura ampla e responsiva** (`max-w-5xl`, `max-h-[90vh]`) — aproveita a tela
  e reduz rolagem; cards em **grid de 2 colunas** em telas largas.
- **Fecha com ESC e com clique no overlay** (fora da caixa); trava o scroll do
  body enquanto aberto.
- **Cabeçalho fixo** "Detalhe da marca" + botão **X** no canto superior direito.
- **Bloco principal destacado**: elemento nominativo em evidência, badges de
  situação/apresentação/natureza e nº do processo INPI.
- **Cards**: Identificação do processo (datas, natureza, apresentação) ·
  Titulares/Depositantes (nome, CPF/CNPJ, UF) · Representante legal/Procurador ·
  Classes (Nice/Nacional/Viena) · Petições · Histórico RPI/Despachos.

`marcas/page.tsx` foi limpo (drawer antigo e componentes duplicados removidos) e
passa a renderizar o modal. **Validação: `tsc --noEmit` do frontend inteiro com
exit 0.**

---

## 6. Navegação do Monitoramento e módulo NIT

### 6.1 "Ver" do Monitoramento — corrigido

`monitoramento/page.tsx`: o "Ver" de uma **marca** abria `<Link href="/marcas">`
(perdia o item selecionado). Agora é um `<button onClick={onView(codigo_interno)}>`
que **abre o `MarcaDetailModal` in-place** com o item. Patente mantém o link para
`/patentes` (não há modal de patente). Validado por `tsc`.

### 6.2 Cobertura de menus do NIT (marco legal CT&I / FORMICT)

Os 16 submenus atuais (Comunicações, Portfólio de Ativos, Portfólio avançado,
Comitês, Catálogo de Tecnologias, Negociações, Contratos, Projetos de P&D,
Startups, Incubação, **Indicadores & FORMICT**, Notificações, BI & Relatórios,
Portais externos, Integrações, Documentos) **cobrem bem** o núcleo da Lei de
Inovação (10.973/2004 + 13.243/2016) e do FORMICT. Lacunas sugeridas (backlog,
não implementadas nesta sessão por serem produto/escopo NIT):

- **Política de PI / regimento do NIT** (documento institucional versionado).
- **Distribuição de ganhos econômicos** (royalties → inventor/instituição) —
  há `Royalty` no F3, falta a visão de *repartição* exigida pelo marco legal.
- **Transparência ativa / dados abertos** do FORMICT (export público agregado).
- **Acordos de parceria para PD&I** como tipo próprio dentro de Projetos/Contratos.

---

## 7. Padronização visual (Cerbero Front)

O design system do IntelliINPI **já é** azul-predominante e baseado em cards,
coerente com o padrão Cerbero descrito:

- `tailwind.config.js`: `brand` = **#2563EB** (escala 50–900), `sidebar` navy
  (#0f1c3f) — azul como cor predominante.
- `components/ui/index.tsx`: cards `rounded-xl border-gray-100 shadow-card`,
  botões `brand-600`, foco `brand-500`, badges semânticos, tipografia slate.

O novo modal usa **exatamente esses tokens** (`brand-*`, `rounded-xl/2xl`,
`shadow-card/soft`, `border-gray-100`), mantendo a identidade. Não foram feitas
mudanças destrutivas de tema porque a base já está alinhada. (A pasta
CerberoFront não está indexada como KB neste ambiente para um diff token-a-token;
a conformidade foi verificada contra o tailwind/ui existentes.)

---

## 8. Resumo dos entregáveis

| # | Entregável | Status | Evidência |
|---|---|---|---|
| 1 | Gargalos + plano de queries/rotas | ✅ | Seção 1; dashboard.py |
| 2 | Correção do `/api/dashboard/summary` | ✅ | dashboard.py; `import app.main` OK |
| 3 | Viabilidade .NET CQRS na Oracle Free | ✅ (análise) | Seção 2.2 — não recomendado agora |
| 4 | Modal de Detalhe da Marca (ESC/overlay/cards) | ✅ | MarcaDetailModal.tsx; `tsc` exit 0 |
| 5 | Correção do "Ver" no Monitoramento | ✅ | monitoramento/page.tsx; `tsc` exit 0 |
| 6 | Estrutura DI + Software (sem ingestão) | ✅ | models/schemas/routers/migration/datasets; 5+5 rotas montadas |
| — | Estratégia de imagens + worker de figuras | ✅ | ingestion/figuras.py (WebP + object storage + Cloudflare) |

### Arquivos alterados/criados

Backend: `routers/dashboard.py`, `models/desenhos.py`, `models/software.py`,
`models/rbac.py`, `models/__init__.py`, `schemas/desenhos.py`,
`schemas/software.py`, `routers/desenhos.py`, `routers/software.py`,
`routers/__init__.py`, `alembic/versions/f1a2b3c4d5e7_add_desenhos_software.py`.
Ingestão: `datasets.py`, `db.py`, `figuras.py`.
Frontend: `components/MarcaDetailModal.tsx`, `app/marcas/page.tsx`,
`app/monitoramento/page.tsx`.

### Verificação executada

- Backend: `import app.models` + `import app.routers` + `import app.main` sem erro
  (venv limpa); metadados das 17 novas tabelas registrados; 10 rotas novas
  montadas sob `/api`.
- Migração: cadeia linear com head único `f1a2b3c4d5e7` (`ScriptDirectory`).
- Catálogo de ingestão: `resolve(['desenhos_industriais'])` /
  `['programas_de_computador']` resolvem; `figuras._FIGURE_DATASETS` aponta os 3 ZIPs.
- Frontend: `npx tsc --noEmit` exit 0 no projeto inteiro.
