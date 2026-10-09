# RELATÓRIO DE AUDITORIA — EVOLUÇÃO DOS RESULTADOS DA PESQUISA DE MARCAS

> Objetivo: evoluir a **apresentação e o modelo de dados** dos resultados da pesquisa
> de marcas para oferecer riqueza de informação equivalente à BuscaWeb do INPI,
> usando **exclusivamente** os dados que já existem na base local ou deriváveis deles.
>
> Esta é a **auditoria obrigatória (§2, §23, §30)**. Nenhuma alteração de código,
> schema, dado ou migração foi feita nesta etapa. Todas as conclusões abaixo foram
> verificadas com consultas **read-only** (`SELECT`/`count`) no banco real
> `intelliinpi_app` (PostgreSQL 16.14) e leitura do código-fonte.
>
> *Investigação conduzida apenas com consultas read-only. Nenhum dado, tabela,
> índice, migração ou código foi modificado.*

---

## 1. Metodologia

Pipeline auditado, de ponta a ponta:

```text
CSV original (data/raw)
        ↓
dataset importado (ingestion/)
        ↓
tabela PostgreSQL (intelliinpi_app)
        ↓
SQLAlchemy/model (backend/app/models/marcas.py)
        ↓
endpoint (backend/app/routers/marcas.py)
        ↓
schema response (backend/app/schemas/search.py)
        ↓
frontend (frontend/src/app/marcas/page.tsx, src/lib/hooks.ts, src/lib/types.ts)
```

Fontes de evidência:
- `backend/app/models/marcas.py` — 5 modelos de marcas.
- `backend/app/routers/marcas.py` — `_base_query`, `/search`, `/export`, `/{codigo}`.
- `backend/app/schemas/search.py` — `MarcaOut`, `MarcaDetail`.
- `frontend/src/lib/types.ts`, `hooks.ts`, `app/marcas/page.tsx`.
- Banco real: contagens e amostras (ver §4).

---

## 2. Descoberta do esquema (o que realmente existe)

O modelo é **normalizado** e espelha os CSVs oficiais do INPI. As 5 tabelas de marcas:

| Tabela | Modelo | Chave de ligação | Papel |
|---|---|---|---|
| `marcas` | `Marca` | `codigo_interno` (unique), `numero_inpi` | Ficha principal (dados bibliográficos) |
| `marcas_depositantes` | `MarcaDepositante` | `codigo_interno` | Titulares/depositantes (N por processo) |
| `marcas_classificacoes_nacionais` | `MarcaClassificacaoNacional` | `codigo_interno` | Classificação nacional (classe/subclasses) |
| `marcas_classificacoes_nice` | `MarcaClassificacaoNice` | `codigo_interno` | Classificação de Nice |
| `marcas_classificacoes_viena` | `MarcaClassificacaoViena` | `codigo_interno` | Classificação de Viena |

**Observação crítica de cardinalidade:** a ligação entre as tabelas é por
`codigo_interno` (coluna avulsa com índice próprio), **não** por `ForeignKey` de banco.
O relacionamento ORM existe apenas de `Marca → depositantes` (`viewonly=True`). As
demais relações exigem `join` explícito por `codigo_interno`.

Existe ainda o relacionamento global `/api/search` (`backend/app/routers/search.py`)
que faz `OR(elemento_nominativo ILIKE, numero_inpi ILIKE)` — **fora do escopo** desta
tarefa (é a BUSCA_GLOBAL, não a pesquisa de marcas). Não será tocado.


---

## 3. AUDITORIA DE CAMPOS (§23)

| Campo INPI | Fonte local | Disponível? | Arquivo/Modelo (coluna) | Observação |
|---|---|---|---|---|
| **Número do processo** | `marcas.numero_inpi` | **SIM** (100%) | `models/marcas.py` → `Marca.numero_inpi` | 6.645.491/6.645.491 preenchidos. Chave pública do processo (ex.: `814317448`). |
| **Data (Depósito)** | `marcas.data_deposito` | **SIM** (~100%) | `Marca.data_deposito` (Date) | 6.645.478 preenchidos (13 nulos). **É data de depósito, NÃO de prioridade.** |
| **Data de prioridade** | — | **NÃO** (marcas) | — | `data_prioridade` só existe em **patentes** (`PatentePrioridade`). Não há tabela de prioridade de marcas importada. |
| **Marca (nome)** | `marcas.elemento_nominativo` | **SIM** (~95,5%) | `Marca.elemento_nominativo` (Text) | 6.345.925 preenchidos. Campo da busca (fold). |
| **Apresentação / Tipo** | `marcas.descricao_apresentacao` | **SIM** (100%) | `Marca.descricao_apresentacao` (Text) | Valores reais: `Mista` (4,16M), `Nominativa` (2,30M), `Figurativa` (187k), `Tridimensional` (4.680), `Marca de posição` (764). **É exatamente o "Tipo" da BuscaWeb.** |
| **Natureza** | `marcas.descricao_natureza` | **SIM** (100%) | `Marca.descricao_natureza` (Text) | `Produtos e/ou Serviço`, `De Produto`, `De Serviço`, `Coletiva`, `Certific.` etc. Complementa a apresentação. |
| **Situação** | `marcas.descricao_situacao` | **SIM** (100%) | `Marca.descricao_situacao` (Text) | Descrição real (ex.: `Registro de marca em vigor`, `Pedido Definitivamente Arquivado`). Há também `codigo_situacao` (código, ex. `IPAS023`, `50`). |
| **Titular** | `marcas_depositantes.nome` | **SIM** (relação) | `MarcaDepositante.nome` | 6.710.537 linhas, 6.710.507 com nome. Cada marca tem ≥1 depositante. Múltiplos por processo (ver §8). |
| **Classe** | `marcas_classificacoes_nice` + `marcas_classificacoes_nacionais` | **SIM** (relação) | `MarcaClassificacaoNice.classe_nice`/`edicao_nice`; `MarcaClassificacaoNacional.classe`/subclasses/especificacao | Nice: 5.331.074; Nacional: 1.084.129. Formatos variados (`NCL(8) 20`, `33 : 10`) — ver §9. |
| **Classe de Viena** | `marcas_classificacoes_viena` | **SIM** (relação) | `MarcaClassificacaoViena.simbolo`/`classificacao_viena` | 9.978.524 linhas — elemento figurativo. |
| **Tradução** | `marcas.traducao` | **SIM** (~6%) | `Marca.traducao` | 408.468 preenchidos. |
| **Publicação/Concessão/Vigência** | `marcas.data_publicacao`/`data_concessao`/`data_vigencia` | **SIM** | `Marca.*` (Date) | Já no `MarcaDetail` (parcial). |
| **Apostila** | `marcas.apostila` | **SIM** | `Marca.apostila` | Já no `MarcaDetail`. |
| **Histórico / Movimentações** | `marcas_despachos` | **SIM** (relação) | `MarcaDespacho.*` | Dataset `MARCAS_DESPACHOS.csv` **importado** (§17.8). Presente no `MarcaDetail.despachos`. |
| **Documentos** | — | **NÃO** | — | Não existe tabela de documentos/anexos de marcas. |
| **Ícone oficial N/M** | — | **NÃO** | — | Não há asset/imagem do INPI importada. Ícone será **derivado** de `descricao_apresentacao` (Nominativa→N, Mista→M, etc.). |
| **URL de detalhe do INPI** | — | **NÃO** | — | Não há coluna com o `CodPedido` sequencial da BuscaWeb (`detail&CodPedido=21747`). O `numero_inpi` **não** é o mesmo identificador. Ver §11. |

### Amostra real — os 11 processos de `MAGU` (exact)

| codigo_interno | numero_inpi | nome | apresentacao | situação | data_deposito | depositantes | nice | nac. |
|---|---|---|---|---|---|---|---|---|
| 431822 | 814317448 | MAGU | Nominativa | Pedido Definitivamente Arquivado | 1988-07-04 | 1 | 0 | 1 |
| 2501967 | 903782294 | MAGU | Mista | Pedido definitivamente arquivado | 2011-06-27 | 1 | 1 | 0 |
| 2503092 | 903782367 | MAGU | Mista | Pedido definitivamente arquivado | 2011-06-27 | 1 | 1 | 0 |
| 3615312 | 913502928 | MAGU | Nominativa | Indeferido (sem recurso) | 2017-10-04 | 1 | 1 | 0 |
| 4151488 | 919268080 | magu | Nominativa | Aguardando recurso contra indeferimento | 2020-02-20 | 1 | 1 | 0 |
| 4362154 | 921233175 | MAGU | Mista | Aguardando recurso contra indeferimento | 2020-11-05 | 1 | 1 | 0 |
| 4482935 | 922437041 | MAGU | Mista | Registro de marca em vigor | 2021-03-23 | **2** | 1 | 0 |
| 5112835 | 928509699 | Magu | Nominativa | Pedido definitivamente arquivado | 2022-10-31 | 1 | 1 | 0 |
| 5139416 | 928817423 | MAGU | Mista | Registro de marca em vigor | 2022-12-01 | 1 | 1 | 0 |
| 6067815 | 937780863 | MAGU | Mista | Registro de marca em vigor | 2025-01-27 | 1 | 1 | 0 |
| 6248375 | 939393107 | Magu | Mista | Aguardando prazo de apresentação de oposição | 2025-06-02 | 1 | 1 | 0 |

Confirma: **todos** os campos-alvo (número, nome, tipo, situação, data, titular,
classe) existem para os 11 processos. Um deles (`4482935`) tem **2 titulares** →
justifica a UI "Titular + N".

---

## 4. Contagens de cobertura (banco real)

```text
marcas: total=6.645.491  apres=6.645.491  nome=6.345.925  sit=6.645.491
        data_deposito=6.645.478  numero_inpi=6.645.491  natureza=6.645.491  traducao=408.468
marcas_depositantes: total=6.710.537  com_nome=6.710.507  com_cnpj=5.829.100
marcas_classificacoes_nacionais: 1.084.129
marcas_classificacoes_nice:      5.331.074
marcas_classificacoes_viena:     9.978.524
```


---

## 5. Classificação de implementação (§24)

| Campo | Classe | Ação |
|---|---|---|
| Número (`numero_inpi`) | **A** | Já no response. Melhorar apresentação (+ copiar). |
| Data (`data_deposito`) | **A** | Já no response. Rotular como **"Depósito"** (não "Prioridade"). |
| Marca (`elemento_nominativo`) | **A** | Já no response. Destaque principal. |
| Apresentação (`descricao_apresentacao`) | **A** | Já no response. + badge/ícone derivado. |
| Natureza (`descricao_natureza`) | **A** | Já no response. Mostrar no detalhe. |
| Situação (`descricao_situacao`/`codigo_situacao`) | **A** | Já no response. + badge com descrição real. |
| **Titular** | **C** | Disponível via relação `marcas_depositantes`. **Não** está no `/search` atual → adicionar com **1 join agregado (sem N+1)**. |
| **Classe** | **C** | Disponível via `marcas_classificacoes_nice`/`_nacionais`. **Não** está no `/search` atual → adicionar com join agregado. |
| Data de prioridade (marcas) | **E** | Não existe. Não inventar; documentar limitação. |
| Histórico/Movimentações | **A** | Dataset `MARCAS_DESPACHOS.csv` **importado** (§17.8). Exposto em `MarcaDetail.despachos`. |
| Documentos | **E** | Não existe. Não inventar. |
| URL detalhe INPI | **E** | Sem `CodPedido`. Não montar URL fabricada. |

---

## 6. Alterações backend propostas (seguras, sem migration)

Arquivo: `backend/app/schemas/search.py` e `backend/app/routers/marcas.py`.

**Schema (`MarcaOut`)** — adicionar campos opcionais (todos com default `None`, para
não quebrar outros consumidores):

```text
titulares: list[str] = []          # nomes (titular principal + demais)
titular_principal: str | None = None
num_titulares: int = 0
classificacoes: list[str] = []     # strings já formatadas p/ exibição (ex.: "NCL(8) 20")
```

**Query `/search`** — manter a paginação atual (LIMIT/OFFSET + COUNT) e acrescentar
**duas** consultas agregadas em lote (evita N+1), calculadas apenas para os ≤100
`codigo_interno` da página:

- titulares: `ARRAY_AGG(nome ORDER BY nome)` por `codigo_interno` (join em `marcas_depositantes`);
- classes: `STRING_AGG` das classificações Nice e Nacionais por `codigo_interno`.

Implementação: após a página principal, **uma** query por relação com
`.where(codigo_interno.in_(page_ids))` → 2 consultas extras fixas (não N+1).

**Regra semântica:** **nenhuma** alteração em `_base_query`/`match_mode`. Os filtros,
a ordenação (`data_deposito DESC NULLS LAST`) e a paginação permanecem idênticos.

---

## 7. Alterações frontend propostas

Arquivo(s): `frontend/src/lib/types.ts`, `src/lib/hooks.ts`, `src/app/marcas/page.tsx`
(+ componentes novos quando justificado: `MarcaStatusBadge`, `MarcaTipoBadge`,
`MarcaDetail`).

- Coluna/lista: **Marca** (destaque), **Situação** (badge com texto real),
  **Titular** (nome + N), e secundárias: **Nº**, **Data (Depósito)**, **Tipo**, **Classe**.
- Badge de situação com texto **sempre** visível (não depender só de cor).
- Badge/ícone de tipo derivado do texto (`Nominativa→N`, `Mista→M`, `Figurativa→F`,
  `Tridimensional→T`, `Marca de posição→P`).
- Detalhe (drawer já existente): ampliar para exibir tipo/natureza, titulares (todos),
  classes (Nice + Nacional + Viena), datas. **Sem** abas vazias.
- Responsividade: tabela no desktop; **cards** no mobile (mesma informação).
- **Sem** ações fictícias: manter apenas "Ver detalhes" (funcional hoje). Favoritar/
  monitorar/cliente **não** têm backend → não exibir "fake".
- **Sem** botão "Ver no INPI" (§11: URL não confiável).

---

## 8. Titular (múltiplos) — decisão

Dados: cada processo tem ≥1 depositante; alguns têm 2+ (ex.: `4482935` = 2).
Estratégia: exibir `titular_principal` + `+N` outros, com **expansão** no detalhe para
ver todos. **Não** concatenar de forma confusa.

---

## 9. Classe — formatos reais encontrados

Formatos originais preservados (não normalizar cegamente):
`33 : 10`, `35 : 10`, `07 : 99` (nacional: `classe : subclasse`), `NCL(8) 20`
(Nice: `edicao_nice` + `classe_nice`). Plano: **preservar a string original** e, quando
estruturado (Nice), oferecer leitura auxiliar `Classe N (Nice, NCL X)`.

---

## 10. Campos NÃO disponíveis → limitações documentadas (§25)

1. **Prioridade de marcas** — inexistente no dataset de marcas (só patentes). Usar
   "Depósito". **Não** reimportar.
2. **Histórico/Movimentações** — `MARCAS_DESPACHOS.csv` **importado** (§17.8) na
   tabela `marcas_despachos` e exposto em `MarcaDetail.despachos`.
3. **Documentos (petições/anexos)** — inexistentes nos dados abertos. **Não** inventar.
4. **URL oficial da BuscaWeb** — não há `CodPedido`. **Não** montar URL fabricada.

---

## 11. URL / detalhe do INPI (§16)

Não há, na base local, o identificador sequencial usado pelo INPI
(`...&CodPedido=21747`). Montar o link a partir de outro campo produziria URL
**incorreta**. Decisão: **prioridade = detalhe local** (já existe `/api/marcas/{id}`).
Sem link externo. Documentado como limitação.

---

## 12. Impacto de performance (§18)

- Base = 6,6M de marcas. Proibido N+1.
- Proposta: **2 consultas agregadas fixas por página** (titulares e classes), restritas
  aos `codigo_interno` da página (`IN (≤100 ids)`), com índices existentes
  (`ix_marcas_dep_codigo_interno`, `ix_marcas_nice_codigo_interno`,
  `ix_marcas_cn_codigo_interno`). Custo adicional **constante**, independente do total.
- `match_mode`/índice `fold` intocados → busca exact segue ~0,1 ms.
- Paginação (`page`, `page_size≤100`, `total`) preservada.

---

## 13. Testes necessários (§26)

- `MAGU exact=11`, `prefix=385`, `contains=606` — **inalterados** (regressão).
- Novos: `/search` retorna `titular_principal`/`titulares`/`num_titulares`/`classificacoes`
  para os 11 processos; caso com 2 titulares (`4482935` → `num_titulares=2`).
- Campos já cobertos: número, marca, situação, data, apresentação.
- RBAC/paginação/ordenação — regressão.

---

## 14. Riscos

| Risco | Mitigação |
|---|---|
| Joins degradarem a busca | Restringir por `IN (page_ids)`; medir com EXPLAIN. |
| Quebrar consumidores de `MarcaOut` | Campos novos **opcionais** com default. |
| Chamar depósito de "prioridade" | Rotular "Depósito"; prioridade = limitação. |
| Exibir ações sem backend | Só "Ver detalhes" (real). |
| Normalizar classes e perder informação | Preservar string original. |

---

## 15. Plano de implementação (§31)

```text
1. Backend response  (schemas/search.py + routers/marcas.py, join agregado)
2. Testes            (tests/test_marcas_search.py: novos campos + regressão 11/385/606)
3. Hook/frontend model (types.ts + hooks.ts)
4. Tabela            (page.tsx: colunas Marca/Situação/Titular + secundárias)
5. Status/apresentação (badges MarcaStatusBadge / MarcaTipoBadge)
6. Detalhes          (drawer ampliado: titulares, classes, tipo, datas)
7. Responsividade    (cards no mobile)
8. Validação         (pytest, tsc --noEmit, next build; 11/385/606)
```

---

## 16. Confirmações desta etapa (auditoria)

```text
Dados alterados:     NÃO
Migration criada:    NÃO
Reimportação:        NÃO
Código alterado:     NÃO (apenas este relatório .md criado)
Commit / Push:       NÃO
```

> Aguarda-se aprovação do mapeamento e da estratégia técnica acima antes de
> iniciar a implementação (§2, §24, §31, §34).

---

## 17. Implementação — RESULTADO (aprovada e concluída)

Implementação executada na ordem aprovada (§31). Nenhuma migration, reimportação,
alteração de dados, mudança de `match_mode`, filtros, ordenação ou paginação.

### 17.1 Arquivos alterados
```text
backend/app/schemas/search.py     (+ MarcaClassificacao; + campos titulares/titular_principal/num_titulares/classificacoes em MarcaOut)
backend/app/routers/marcas.py     (+ _load_titulares, _load_classificacoes; /search enriquecido; get_marca enriquecido)
backend/tests/test_marcas_enrich.py (NOVO — 11 testes)
frontend/src/lib/types.ts         (+ MarcaClassificacao; + campos em Marca)
frontend/src/lib/marcas.ts        (NOVO — helpers de badge/formatação)
frontend/src/components/MarcaBadges.tsx (NOVO — SituacaoBadge, ApresentacaoBadge)
frontend/src/app/marcas/page.tsx  (tabela enriquecida + cards mobile + drawer)
reports/RELATORIO_RESULTADO_INPI.md (este relatório)
```

### 17.2 Contrato final `GET /api/marcas/search`
```json
{
  "pagination": { "page": 1, "page_size": 20, "total": 11 },
  "items": [{
    "id": "…", "codigo_interno": "4482935", "numero_inpi": "922437041",
    "data_deposito": "2021-03-23", "data_concessao": "2022-01-11",
    "descricao_apresentacao": "Mista", "descricao_natureza": "Produtos e/ou Serviço",
    "elemento_nominativo": "MAGU", "codigo_situacao": "IPAS023",
    "descricao_situacao": "Registro de marca em vigor",
    "titulares": ["BIANCA MARTINS DE PAULA", "ISABELA LIMA BRAZ GUEDES"],
    "titular_principal": "BIANCA MARTINS DE PAULA", "num_titulares": 2,
    "classificacoes": [
      { "tipo": "nice",  "codigo": "NCL(11) 45", "descricao": "Assessoria …" },
      { "tipo": "viena", "codigo": "13.1.17",   "descricao": "Lâmpadas …" }
    ]
  }]
}
```

### 17.3 Estratégia e evidências
- **Titulares:** 1 query agregada por página (`codigo_interno IN (ids)`); `titulares[]`
  é a fonte; `titular_principal`/`num_titulares` derivados. Real: `4482935` → 2.
- **Classes:** 3 queries agregadas por página (nice/nacional/viena); `descricao`
  só quando existir no dado real.
- **Cardinalidade:** 1 processo = 1 resultado (relations carregadas em mapas por
  `codigo_interno`, nunca via join que multiplica linhas).
- **Sem N+1:** teste `test_no_n_plus_one_fixed_query_count` mede nº de queries fixo.
- **Regressão (banco real):** `exact=11`, `prefix=385`, `contains=606`.

### 17.4 Validação
```text
pytest (suite completa) : 51 passed, 0 failed
npx tsc --noEmit        : OK (sem erros)
npx next build          : OK (compiled successfully; rota /marcas 5.11 kB)
```

### 17.5 Confirmações finais
```text
Migration criada:        NÃO
Reimportação:            NÃO
Alteração de dados:      NÃO
Alteração de match_mode: NÃO
Commit / Push:           NÃO (workspace não é repositório git)
```

### 17.6 Ajuste pós-entrega — coluna/badge de classe
Solicitado: a **Classe** deve mostrar **apenas o número/código**, sem o texto
completo da especificação (ex.: `NCL(12) 25` — não `NCL(12) 25 — Agasalhos …`).

- `frontend/src/lib/marcas.ts` → `classificacaoLabel()` agora retorna **só `c.codigo`**.
- `frontend/src/app/marcas/page.tsx`:
  - tabela desktop: célula "Classe" passa a listar **todos os códigos** unidos por
    vírgula (`NCL(11) 25, NCL(11) 35`), sem descrição;
  - card mobile (`Field label="Classe"`) idem (usa `classificacaoLabel`);
  - drawer de detalhe: lista tipo + código, **sem** o texto `descricao`.
- Contrato do backend **inalterado** (`descricao` continua disponível na API para
  uso futuro; apenas a UI deixa de exibi-la em linha).
- Validação: `npx tsc --noEmit` OK; `npx next build` OK (rota `/marcas` = 5.08 kB).


### 17.7 Ajuste pós-entrega — detalhe da marca no layout do relatório INPI

Solicitado: reestruturar o **detalhe da marca** (drawer) para se aproximar do
relatório oficial do INPI, com: imagem/logotipo, representante legal/procurador,
petições e histórico de publicações (RPI/despachos).

**Auditoria de disponibilidade (banco real + relatório §3/§10):**

| Seção pedida | Fonte local | Disponível? | Decisão |
|---|---|---|---|
| Logotipo/imagem | — | **NÃO** | Placeholder rotulado (sem asset importado; tipo derivado de `descricao_apresentacao`). |
| Representante legal/procurador | `marcas_depositantes.nome_representante_legal` + `cnpj_cpf_representante_legal` | **SIM** (~5,05M/6,71M ≈ 75%) | **Nova seção real** (deduplicada por nome+CNPJ/CPF). |
| Titulares/depositantes | `marcas_depositantes` | **SIM** | Lista com nome + CPF/CNPJ + país/UF. |
| Petições | — | **NÃO** | Nota "não disponível" (dataset inexistente). |
| Histórico RPI/despachos | `marcas_despachos` | **SIM** | **Nova seção real** (§17.8) — `MARCAS_DESPACHOS.csv` importado. |

**Backend** (`backend/app/schemas/search.py`, `backend/app/routers/marcas.py`):
- `MarcaDetail` ganha `representantes_legais: list[dict] = []` (`nome`, `cnpj_cpf`,
  `tipo_pfpj`), montado a partir dos depositantes, **deduplicado** (um mesmo
  procurador compartilhado por vários titulares aparece uma vez). Sem migration —
  os dados já existem em `marcas_depositantes`.
- `search` (lista) **não** foi alterado; apenas o `GET /api/marcas/{codigo}`.

**Frontend** (`frontend/src/lib/types.ts`, `frontend/src/app/marcas/page.tsx`):
- `MarcaDetailView` reescrito em blocos no estilo INPI: cabeçalho
  (imagem + nome + badges), **Identificação do processo** (INPI, código interno,
  depósito, publicação, concessão, vigência, apresentação, natureza, tradução,
  apostila), **Titulares/Depositantes**, **Representante legal/procurador**,
  **Classes/classificações**, **Especificações de classificação** (Nice/Nacional/
  Viena), **Petições** e **Histórico (RPI)/despachos** (estas duas como nota
  “não disponível localmente”).
- Helpers `SectionBlock`, `MarcaImagem`, `ClassList`, `NotImportedNote`
  substituem o antigo `Section`.

**Validação:** `npx tsc --noEmit` OK; `npx next build` OK (rota `/marcas` = 6.06 kB);
backend `pytest` = **52 passed** (novo teste
`test_detail_representantes_legais_empty_when_absent` + asserção de deduplicação no
teste de detalhe). Sem alteração em `match_mode`, dados ou migrações.

### 17.8 Importação do dataset `MARCAS_DESPACHOS.csv` (histórico RPI/despachos)

Solicitado: importar o dataset de despachos/publicações (RPI) das marcas — antes
apenas existente na origem e não carregado (ver §10/§17.7).

**Fonte real (header do CSV):**
`codigo_interno, numero_inpi, numero_rpi, data_rpi, codigo_despacho, descricao_despacho, complemento_despacho`
(7 colunas; inclui `descricao_despacho`, ausente em `PATENTES_DESPACHOS.csv`).

**Ingestão (`ingestion/datasets.py`):** novo `DatasetSpec` `marcas_despachos`
(`/download/marcas/MARCAS_DESPACHOS.csv`, CSV → tabela `marcas_despachos`), o 6º
CSV de marcas a entrar no carregador DuckDB→PostgreSQL existente (sem código novo).

**Modelo/migração:**
- `backend/app/models/marcas.py` — `MarcaDespacho` (espelha `PatenteDespacho` +
  `descricao_despacho`); índices em `codigo_interno` e `codigo_despacho`.
- `models/__init__.py` — registrado.
- Alembic `b2c3d4e5f6a7_add_marcas_despachos` (revises `a1b2c3d4e5f6`).

**Backend:** `schemas/search.py` (`MarcaDetail.despachos: list[dict]`) e
`routers/marcas.py` (query por `codigo_interno`, ordenada por `data_rpi DESC
NULLS LAST`; exposta em `GET /api/marcas/{codigo}`).

**Frontend:** `types.ts` (`MarcaDetail.despachos`) e `page.tsx` — a antiga nota
“não disponível” da seção **Histórico de publicações (RPI) / despachos** foi
substituída por uma lista real (data, nº RPI, código + descrição do despacho e
complemento); quando não há registros, mostra uma nota informativa (dataset
importado, sem despachos para aquele processo).

**Operação:** tabela criada via `alembic upgrade head`; carga executada com
`python -m ingestion.load --dataset marcas_despachos` (CSV de ~5,6 GB).

**Resultado da carga:** `24.760.571` linhas (`rows_read=24.760.693`,
`rows_inserted=24.760.571`; 122 duplicatas removidas pelo carregador). Dataset
marcado `IMPORTED`.

**Observação (codificação de origem):** o texto de `descricao_despacho`/
`complemento_despacho` apresenta *mojibake* (`PublicaþÒo`, `OPOSIÃ├O`) — é a
**mesma característica já presente** nos demais datasets de marcas (`QMC GEST├O`
em `marcas.elemento_nominativo`): a origem INPI exporta texto Latin-1 como
UTF-8. O carregador preserva os bytes da fonte **fielmente** (sem “correção”
silenciosa), consistente com as tabelas já carregadas. Correção de codificação,
se desejada, deve ser um passe específico sobre a origem — fora do escopo desta
importação.

**Testes:** +2 em `backend/tests/test_marcas_enrich.py`
(`test_detail_carries_despachos_ordered_by_date`,
`test_detail_despachos_empty_when_absent`).

### 17.9 Logotipos das marcas (imagens do pePI) — novo worker + endpoint + UI

Solicitado: baixar as imagens (logotipos) de cada processo de marca a partir do
link `busca.inpi.gov.br/pePI/servlet/LogoMarcasServletController?...&codProcesso=<codigo_interno>`,
salvá-las localmente e expor no detalhe da marca.

**Descoberta (verificada no endpoint real):** a URL **redireciona para a tela de
login** do pePI. Porém o próprio pePI oferece um **login anônimo**:
`GET {pepi}/servlet/LoginController?action=login` seta os cookies
(`JSESSIONID`/`BUSCAID`) e, na mesma sessão, o `LogoMarcasServletController`
passa a devolver o **JPEG real** (ex.: `6248375` → 14.781 bytes, `ffd8ffe0`).
Sem credenciais. Comportamentos observados:
- **sem imagem** → GIF *placeholder* fixo (9.246 bytes) **disfarçado** de
  `Content-Type: image/jpg`;
- **código inválido** → página HTML de erro.

**Ingestão (`ingestion/logos.py`, novo):**
- Sessão anônima por thread (`LogoClient`), com **re-login** automático quando
  a resposta vem HTML (sessão expirada).
- Detecta imagem real por *magic bytes* (JPEG/PNG/GIF); GIF/inválido →
  `SEM_IMAGEM` (nunca grava o placeholder).
- Escrita **atômica** (`.part` → rename) em
  `data/raw/marcas/logos/<2 primeiros dígitos>/<codigo>.jpg` (sharding).
- Worker concorrente (`ThreadPoolExecutor`), com *delay* educado e *backoff*.
- **Resumível**: pula códigos já em status terminal (`OK`/`SEM_IMAGEM`).
- CLI: `python -m ingestion.logos --apresentacao Mista [--limite N]
  [--concorrencia K] [--delay S] [--codigos C] [--todos]`.
- Config: `INPI_PEPI_BASE_URL`, `INPI_LOGO_CONCURRENCY`, `INPI_LOGO_DELAY`.

**Banco:** tabela `marcas_logos` (Alembic `c3d4e5f6a7b8`, revises `b2c3d4e5f6a7`):
`codigo_interno` (unique), `arquivo`, `mime`, `bytes`, `sha256`,
`status` (`OK`/`SEM_IMAGEM`/`ERROR`), `tentativas`, `erro`, `baixado_em`,
timestamps. Não faz parte dos CSVs de dados abertos — é ativo adicional do pePI.

**Backend:** `MarcaLogo` (modelo) + `MarcaDetail.tem_logo`/`logo_status`
(`schemas/search.py`) e novo `GET /api/marcas/{codigo}/logo` (`routers/marcas.py`)
que faz *stream* do arquivo (`FileResponse`), 404 quando não há imagem. Protegido
por `MARCAS_VIEW`.

**Frontend:** `types.ts` (`tem_logo`/`logo_status`), helper `fetchBlobUrl`
(`api.ts`, com Bearer + refresh) e hook `useMarcaLogo` (`hooks.ts`); o componente
`MarcaImagem` (`marcas/page.tsx`) passa a exibir a imagem real (via *object URL*,
revogado no unmount) e mantém o *placeholder* textual quando não há logotipo.

**Resultado da carga:** tabela criada via `alembic upgrade head`.
Teste ponta-a-ponta real (`--codigos 6248375 860177 1 999999999999`):
`ok=2`, `sem_imagem=1`, `erro=1` — exatamente o comportamento esperado. Obs.: a
carga em massa (~4,3M imagens estimadas entre “Mista”/“Figurativa” de um total de
6.645.491 marcas) é **voluntariamente incremental** (`--limite`), por volume
(dezenas de GB) e cortesia com a origem.

**Testes:** +4 em `backend/tests/test_marcas_enrich.py`
(`test_detail_defaults_no_logo_when_unprocessed`, `test_detail_reports_logo_status`,
`test_logo_endpoint_404_when_absent`, `test_logo_endpoint_streams_stored_file`).

**Validação:** backend `pytest` = **58 passed**; `tsc --noEmit` OK;
`next build` OK (rota `/marcas` = 6.47 kB).

## 18. Arquitetura multi-tenant, RBAC e CRM (Company/Customer/Person)

Solicitado: reaproveitar a tabela `users` existente, garantir isolamento por
`tenant_id`, criar `Company`/`Customer`/`Person`, consolidar o RBAC por
modulos/papeis e garantir que o admin existente nao perca acesso.

**Diagnostico (o que ja existia).** Ao auditar o banco real e o codigo,
verificou-se que a fundacao multi-tenant/RBAC **ja estava implementada**:
`tenants`, `users` (com `tenant_id`, `is_master_admin`), `modules`, `roles`,
`permissions`, `role_modules`, `role_permissions`, `user_roles`,
`tenant_modules`; resolucao em `app/rbac.py` (`build_access_context` -- uniao de
permissoes, modulo do papel tem de estar habilitado no tenant, master admin com
acesso total); isolamento derivado **exclusivamente do token** (`app/deps.py`);
APIs em `/api/admin/{tenants,users,modules,roles,permissions}`; seed em
`app/seed.py`; testes `test_rbac.py`/`test_tenant_isolation.py`. A tabela `users`
**nao foi alterada** (colunas identicas as existentes).

**Entidades novas (`app/models/company.py`):**
- `Person` (`people`) -- pessoa fisica por tenant; FK opcional `user_id` liga ao
  login sem sobrecarregar `users`.
- `Company` (`companies`) -- `razao_social`, `nome_fantasia`, `cnpj`,
  `inscricao_estadual`, contato e endereco; unico por `(tenant_id, cnpj)`.
- `Customer` (`customers`) -- cliente do tenant; FKs opcionais `company_id` e
  `person_id`; unico por `(tenant_id, code)`.
Todas com `UUIDPrimaryKeyMixin`/`TimestampMixin`/`SoftDeleteMixin` e `tenant_id`
(FK `tenants`, `ON DELETE CASCADE`) -- mesmo padrao de isolamento do resto.

**RBAC -- ajustes em `app/constants.py`:** novo modulo `CLIENTES`; 6 novas
permissoes (`COMPANY_VIEW/MANAGE`, `CUSTOMER_VIEW/MANAGE`, `PERSON_VIEW/MANAGE`);
novo papel de sistema **`SUPER_ADMIN`** com **todas** as permissoes (mantido em
sincronia com `ALL_PERMISSION_CODES`). Total: **10 modulos, 41 permissoes,
8 papeis**.

**Migration/seed (Alembic `d4e5f6a7b8c9`, revises `c3d4e5f6a7b8`):**
- cria `companies`, `customers`, `people` (+ indices e constraints);
- **data migration idempotente**: garante um **tenant padrao**
  (`DEFAULT_TENANT_NAME`, default `Matriz`); vincula a ele **todos os usuarios
  sem tenant** (inclusive o **master admin** pre-existente, que estava com
  `tenant_id = NULL`); habilita **todos os modulos ativos** nesse tenant; garante
  o papel `SUPER_ADMIN` com todas as permissoes e o concede aos master admins.
  O `is_master_admin=True` e preservado (alcance cross-tenant mantido).
- `app/seed.py` ganhou `seed_default_tenant()` e `seed_default_admin_access()`,
  idempotentes, integrados ao `run_seed()` (o re-seed mantem a consistencia).
- Config: `DEFAULT_TENANT_NAME` (`app/config.py`).

**Resultado (banco de dev):** `alembic upgrade head` -> `d4e5f6a7b8c9`; seed ->
10 modulos, 41 permissoes, `Matriz` com 10 modulos habilitados, `SUPER_ADMIN` com
41 permissoes concedidas ao admin (`user_roles` = `SUPER_ADMIN`).

**Testes:** +7 em `backend/tests/test_company_customer.py` (persistencia e
relacoes de `Company`/`Customer`/`Person`, isolamento por tenant, soft delete,
seed do tenant padrao + acesso total do admin, idempotencia). Novo fixture
`seeded_full` em `conftest.py`.

**Validacao:** backend `pytest` = **65 passed** (58 anteriores + 7 novos).

---

## 19. Finalizacao do sistema (Front-end + Back-end)

Entrega de finalizacao: modulos de Clientes (CRM), Analises IA com DeepSeek,
Monitoramento, Relatorios, painel de Administracao completo e novo design
system (sidebar azul-escuro, primaria `#2563EB`, cards `rounded-xl` /
`border-gray-100` / sombras leves, badges semanticos).

### 19.1 Back-end
- **CRM (`/api/clientes`)** -- `app/routers/clientes.py` + `app/schemas/company.py`:
  CRUD paginado e filtravel de `companies`, `customers` e `people`, sempre
  isolado por `tenant_id` (master admin pode filtrar por tenant). Permissoes
  `COMPANY_*`, `CUSTOMER_*`, `PERSON_*`; auditoria em toda escrita; soft delete.
- **Analises IA (`/api/analises`)** -- `app/routers/analises.py` +
  `app/schemas/analise.py` + servico real `app/services/deepseek.py`: o wizard
  envia nome/classe NCL/titular/apresentacao/natureza; o endpoint cruza a base
  local do INPI (marcas por nome+classe Nice, patentes por palavra-chave) e
  chama a API do DeepSeek (`chat/completions`, JSON) para o selo de risco,
  score, conflitos e recomendacoes. Sem `DEEPSEEK_API_KEY` retorna HTTP 503
  (nunca fabrica resultado). Cliente sem dependencias novas (apenas `urllib`).
  Config: `DEEPSEEK_API_KEY/BASE_URL/MODEL/TEMPERATURE/MAX_TOKENS/TIMEOUT`.
- **Dashboard enriquecido** -- `app/routers/dashboard.py`: series de evolucao do
  portfolio (Marcas vs Patentes por ano), distribuicao de situacao (donut),
  ultimos eventos do INPI, proximos prazos e contagens de empresas/clientes.
- **Docs**: `.env.example` documenta `DEFAULT_TENANT_NAME` e as variaveis DeepSeek.

### 19.2 Front-end (Next.js 15 / React 19)
- **Design system** -- `tailwind.config.js` (escala `brand` = `#2563EB`, paleta
  `sidebar` azul-escura, `shadow-card/soft`), `globals.css`; primitivos
  reutilizaveis em `src/components/ui` (Card, Badge, Button, Input, Select,
  Textarea, Toggle, Modal, Table, Pagination, Tabs, EmptyState, Spinner).
- **Graficos** -- `src/components/charts` (DonutChart, LineChart, GaugeChart),
  SVG puro sem dependencia externa (dados reais apenas).
- **Sidebar** -- `src/components/AppShell.tsx`: navegacao azul-escura com todos
  os itens (Visao Geral, Clientes, Marcas, Patentes, Monitoramento, Analises IA,
  Relatorios, Administracao com subitens colapsaveis), responsiva, filtrada por
  permissao.
- **Telas** -- `dashboard` (metricas + graficos + eventos + prazos), `clientes`
  (Empresas/Clientes/Pessoas com modais e paginacao), `analises` (wizard NCL com
  tags + opcoes toggles; relatorio com selo de risco, gauge, abas Resumo/
  Conflitos/Marcas Similares/Patentes/Recomendacoes e exportacao PDF/Word),
  `monitoramento`, `relatorios`, `admin` (datasets + barra de progresso + sync)
  com subpaginas `admin/usuarios`, `admin/tenants`, `admin/modulos`.

### 19.3 Validacao
- Backend: `pytest` = **73 passed** (65 anteriores + 8 novos em
  `tests/test_clientes_api.py` e `tests/test_analises.py`).
- Frontend: `tsc --noEmit` OK e `next build` OK (16 rotas compiladas).
- Observacao: os "layouts de referencia" nao estavam presentes no repositorio;
  o visual foi implementado conforme a especificacao textual (cores, componentes
  e estrutura descritos) e nao por pixel-matching de imagens nao fornecidas.





