# Relatório de Importação INPI

**Projeto:** IntelliINPI
**Data da execução:** 2026-10-07
**Base:** PostgreSQL 16 local — banco `intelliinpi_app`
**Fonte:** Datasets abertos oficiais do INPI (marcas + patentes)

---

## 1. Resumo

| Métrica | Valor |
|---|---|
| Datasets registrados | 17 |
| Datasets importados | 17 |
| Datasets com falha | 0 |
| Tabelas de dados populadas | 15 |
| Linhas físicas inseridas (marcas) | 23.102.756 |
| Linhas físicas inseridas (patentes) | 30.702.148 |

> O pipeline roda `discover → download → extract → analyze → load`. O `load`
> utiliza DuckDB com a extensão `postgres` e `INSERT INTO pg.<tabela> SELECT ...
> FROM read_csv(...)`, com deduplicação na origem e projeção de `gen_random_uuid()`
> para a PK `id`.

---

## 2. Marcas

| Dataset | Tabela | Linhas lidas | Linhas inseridas | Status |
|---|---|---:|---:|---|
| marcas_dados_bibliograficos | `marcas` | 13.290.982 | 6.645.491 | IMPORTED |
| marcas_depositantes | `marcas_depositantes` | 6.710.537 | 6.710.537 | IMPORTED |
| marcas_classificacoes_nice | `marcas_classificacoes_nice` | 5.331.074 | 5.331.074 | IMPORTED |
| marcas_classificacoes_viena | `marcas_classificacoes_viena` | 9.978.524 | 9.978.524 | IMPORTED |
| marcas_classificacoes_nacionais | `marcas_classificacoes_nacionais` | 1.084.129 | 1.084.129 | IMPORTED |
| **Subtotal** | | **36.395.246** | **29.749.755** | |

## 3. Patentes

| Dataset | Tabela | Linhas lidas | Linhas inseridas | Status |
|---|---|---:|---:|---|
| patentes_dados_bibliograficos | `patentes` | 1.516.703 | 1.018.792 | IMPORTED |
| patentes_inventores | `patentes_inventores` | 9.312.921 | 9.312.921 | IMPORTED |
| patentes_classificacao_ipc | `patentes_classificacao_ipc` | 6.792.009 | 6.792.009 | IMPORTED |
| patentes_despachos | `patentes_despachos` | 5.338.100 | 5.338.100 | IMPORTED |
| patentes_depositantes | `patentes_depositantes` | 4.640.520 | 4.640.520 | IMPORTED |
| patentes_procuradores | `patentes_procuradores` | 2.991.110 | 2.991.110 | IMPORTED |
| patentes_prioridades | `patentes_prioridades` | 1.535.028 | 1.535.028 | IMPORTED |
| patentes_conteudo | `patentes_conteudo` | 906.548 | 906.548 | IMPORTED |
| patentes_vinculos | `patentes_vinculos` | 44.498 | 22.249 | IMPORTED |
| patentes_renumeracoes | `patentes_renumeracoes` | 9.760 | 4.872 | IMPORTED |
| **Subtotal** | | **33.087.197** | **32.562.149** | |

---

## 4. Problemas encontrados e correções

### 4.1 Chave duplicada na origem (`marcas` / `patentes`)
Os arquivos `MARCAS_DADOS_BIBLIOGRAFICOS.csv` e `PATENTES_DADOS_BIBLIOGRAFICOS.csv`
contêm **linhas integralmente repetidas** para o mesmo `codigo_interno`, o que violava
as restrições `uq_marcas_codigo_interno` / `uq_patentes_codigo_interno`.

**Correção:** o loader passou a deduplicar na origem. Quando a tabela de destino possui
uma UNIQUE de coluna única, mantém-se uma linha por chave
(`QUALIFY row_number() OVER (PARTITION BY <chave>) = 1`); caso contrário aplica-se
`SELECT DISTINCT` sobre as colunas projetadas. Ex.: `marcas` 13,29M → 6,64M linhas.

### 4.2 Estouro de tamanho (`marcas_classificacoes_viena`)
A coluna `classificacao_viena` (originalmente `varchar(32)`) recebia textos descritivos
de até ~187 caracteres; `revisao_viena` (`varchar(16)`) recebia valores com espaços à
direita excedendo o limite.

**Correção:** migração Alembic `a1b2c3d4e5f6` — `classificacao_viena` → `TEXT`,
`revisao_viena` → `varchar(32)`; modelos atualizados em `app/models/marcas.py`.

### 4.3 Idempotência / reimportação
Reexecuções usam `force=True`, que executa `DELETE` da tabela alvo antes do insert,
evitando duplicação entre execuções (ex.: `patentes_vinculos` e
`patentes_renumeracoes` recarregados sem multiplicar linhas).

---

## 5. Pós-carga

- `database/01_extensions.sql`: extensões `pg_trgm`, `unaccent` e helpers `fold()`.
- `database/02_indexes.sql`: índices GIN trigram e índices funcionais de busca.
- `database/03_fts_search.sql`: colunas geradas `tsvector` (português) + índices GIN e
  `ANALYZE` das tabelas.

---

## 6. Ambiente

| Item | Valor |
|---|---|
| Gerenciador de migração | Alembic — head `a1b2c3d4e5f6` |
| Banco | PostgreSQL 16 (nativo) |
| ETL | Python 3 + DuckDB + extensão `postgres` |
| Data dir | `data/raw/{marcas,patentes}` |
| Log da execução | `reports/import_run.log` |
