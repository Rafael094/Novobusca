# SPIKE — Busca de Marcas: INPI Oficial vs IntelliINPI

**Projeto:** IntelliINPI
**Data:** 2026-10-07
**Tipo:** Investigação técnica (somente leitura — nenhum código, dado, índice ou migração foi alterado)
**Caso investigado:** busca `MAGU` → IntelliINPI **606** vs INPI oficial **11**

---

## 1. Objetivo

Determinar, com evidências, **por que** a busca `MAGU` no IntelliINPI retorna **606** resultados
enquanto a Busca de Marcas oficial do INPI retorna **11**, identificando a causa raiz, o impacto
e a correção recomendada. Esta etapa é **apenas diagnóstica**: nenhuma correção foi implementada.

---

## 2. Contexto

- PostgreSQL 16 local; banco `intelliinpi_app`.
- 17 datasets do INPI importados (`inpi_dataset.status = IMPORTED` para todos).
- `marcas`: **6.645.491** linhas; `patentes`: **1.018.792** linhas.
- Extensões: `pg_trgm`, `unaccent`. Há FTS (`tsvector` gerado) e índices.

---

## 3. Arquitetura atual da busca (fluxo real)

```text
Frontend (Next.js)                       Backend (FastAPI)                       PostgreSQL
-------------------                      -----------------                       ----------
src/app/marcas/page.tsx
  input q="MAGU" (debounce-free,
  dispara a cada tecla)
        │
        ▼
src/lib/hooks.ts
  useMarcas({ q, situacao, page,
              page_size:20 })
  GET /api/marcas/search?q=MAGU
      &page=1&page_size=20
        │
        ▼
app/routers/marcas.py
  search_marcas() -> _base_query()
        │
        ▼
SQLAlchemy Core (select)
        │
        ▼
SELECT * FROM marcas
 WHERE elemento_nominativo ILIKE '%MAGU%'
    OR descricao_apresentacao ILIKE '%MAGU%'
    OR numero_inpi          ILIKE '%MAGU%'
 ORDER BY data_deposito DESC NULLS LAST
 LIMIT 20 OFFSET 0;
COUNT(*) sobre o mesmo WHERE
```

**Ponto central:** o único campo "de marca" (`elemento_nominativo`) é filtrado com
`ILIKE '%MAGU%'` → **substring/contém**, combinado por `OR` com apresentação e número do processo.

---

## 4. Endpoint analisado

| Item | Valor |
|---|---|
| URL | `/api/marcas/search` |
| Método | `GET` |
| Query params | `q`, `numero_inpi`, `situacao`, `data_deposito_from`, `data_deposito_to`, `page` (default 1), `page_size` (default 20, max 100) |
| Auth | `require_permission("MARCAS_SEARCH")` (JWT Bearer) |
| Ordenação fixa | `data_deposito DESC NULLS LAST` |
| Paginação | `LIMIT/OFFSET` + `COUNT(*)` da subquery |
| Frontend | `GET /api/marcas/search?q=MAGU&page=1&page_size=20` |

Observação de UX: o input do frontend reexecuta a query a cada tecla (React Query), sem
botão obrigatório, o que produz buscas parciais vivas (visíveis no log: `q=C`, `q=Co`, `q=Con`…).

---

## 5. SQL atual (reconstruída)

```sql
-- _base_query(q='MAGU')
SELECT *
FROM marcas
WHERE elemento_nominativo     ILIKE '%MAGU%'
   OR descricao_apresentacao  ILIKE '%MAGU%'
   OR numero_inpi             ILIKE '%MAGU%'
ORDER BY data_deposito DESC NULLS LAST
LIMIT 20 OFFSET 0;

SELECT count(*) FROM ( <mesmo WHERE acima> ) AS anon_1;
```

Sem `unaccent`, sem `fold`, sem FTS, sem trigram explícito (o `pg_trgm` entra apenas via
plano, não pela intenção), sem `=`, sem prefixo.

---

## 6. Tabelas envolvidas

| Tabela | Papel | Granularidade |
|---|---|---|
| `marcas` | registro principal (dados bibliográficos) | 1 linha por `codigo_interno` (processo) |
| `marcas_depositantes` | titulares/depositantes | N por `codigo_interno` |
| `marcas_classificacoes_nice` | classes Nice | N por `codigo_interno` |
| `marcas_classificacoes_nacionais` | classes nacionais | N por `codigo_interno` |
| `marcas_classificacoes_viena` | classificação Viena | N por `codigo_interno` |

---

## 7. Índices envolvidos (schema real)

```
marcas_pkey                            btree   (id)
uq_marcas_codigo_interno               UNIQUE  btree (codigo_interno)
ix_marcas_codigo_interno               btree   (codigo_interno)
ix_marcas_codigo_situacao              btree   (codigo_situacao)
ix_marcas_numero_inpi                  btree   (numero_inpi)
ix_marcas_elemento_nominativo_fold     btree   (fold(elemento_nominativo))   <-- chave p/ busca exata
ix_marcas_elemento_nominativo_trgm     gin     (elemento_nominativo gin_trgm_ops)
ix_marcas_numero_inpi_trgm             gin     (numero_inpi gin_trgm_ops)
ix_marcas_elemento_nominativo_fts      gin     (elemento_nominativo_tsv)  -- tsvector pt
```

Existe **índice btree funcional pronto** para busca exata acento-insensível
(`fold(elemento_nominativo)`), mas a API **não o utiliza** hoje.

---

## 8. Estrutura dos dados (semântica)

- `codigo_interno` = chave do **processo** de marca. `marcas` tem **6.645.491** linhas e
  **6.645.491** `codigo_interno` distintos ⇒ **1 linha = 1 processo**, sem duplicação de linhas.
- `numero_inpi` = número do processo (pode repetir entre linhas se houver variação de
  `codigo_interno`, mas no universo testado foi 1:1 com `codigo_interno`).
- `elemento_nominativo` = **nome da marca** (a coluna correta para a busca).
- `descricao_situacao` / `codigo_situacao` = situação **atual** (snapshot).
- Não há tabela de eventos/despachos de marcas importada (o dataset `MARCAS_DESPACHOS.csv`
  existe no zip de origem, mas **não** foi carregado — ver §21/§22).

---

## 9. Resultado `MAGU` (evidência comparativa)

Todas as consultas executadas em `elemento_nominativo` (coluna da marca), read-only:

| Regra de busca | Resultado | Observação |
|---|---:|---|
| `elemento_nominativo = 'MAGU'` (exato, case-sensitive) | **8** | perde "magu", "Magu" |
| `lower(elemento_nominativo) = lower('MAGU')` | **11** | **= INPI oficial** |
| `fold(elemento_nominativo) = fold('MAGU')` | **11** | igual, + acento-insensível, **usa índice** |
| `elemento_nominativo ILIKE 'MAGU%'` (prefixo) | **377** | |
| `fold(...) LIKE fold('MAGU')||'%'` (prefixo) | **385** | |
| `elemento_nominativo ILIKE '%MAGU%'` (**contém**) | **606** | **= IntelliINPI atual** |
| `' '||campo||' ' ILIKE '% MAGU %'` (palavra inteira) | **37** | |
| FTS `to_tsvector('portuguese',...) @@ plainto_tsquery('portuguese','MAGU')` | **60** | |
| `similarity(campo,'MAGU') > 0.5` (trigram) | **61** | |
| **API atual** (`ILIKE '%MAGU%'` OR apresentação OR número) | **606** | idêntico a "contém" |

**Conclusão numérica:** apenas **`lower/fold = 'magu'`** produz **11**, batendo 1:1 com o
INPI oficial. Nenhuma variação de prefixo (377/385), substring (606), palavra (37), FTS (60)
ou trigram (61) chega a 11.

---

## 10. Análise dos 606 resultados (IntelliINPI)

Composição real dos 606 (`elemento_nominativo ILIKE '%MAGU%'`):

```
total                        = 606
processos distintos          = 606   (numero_inpi distintos)
codigos_interno distintos    = 606
marcas normalizadas distintas= 360   (vários processos reutilizam o mesmo nome)
```

Distribuição por radical (Top):

| Marca | Ocorrências | Classe |
|---|---:|---|
| MAGUARY | 32 | contém |
| MAGUS | 25 | contém |
| MAGUILA | 14 | contém |
| MAGU | 8 | **exato (case-sensitive)** |
| MAGUARY AMÊNDOA | 8 | contém |
| MAGUINHO | 8 | contém |
| MAGUARY 100% | 7 | contém |
| MAGUARY SEGREDOS DO BRASIL | 7 | contém |
| MAGUARY VITAKIDS | 7 | contém |
| MAGUH | 7 | contém |
| YYY YAMAGUCHI | 7 | contém (meio de palavra) |
| … | … | … |

Classificação dos 606:

| Classe semântica | Qtd |
|---|---:|
| `MAGU` exatamente (case-sensitive) | 8 |
| `MAGU` exatamente (case-insensitive) | 11 |
| Começa com `MAGU` (prefixo) | 377 |
| Contém `MAGU` (prefixo + meio de palavra) | 606 |
| Nome normalizado reutilizado (processos diferentes) | 360 distintos |
| Duplicidades por processo | **0** |
| Processos históricos / eventos | **0** (sem tabela de eventos) |

**Não há duplicidade.** Os 606 são **606 processos legítimos** cujo nome *contém* "MAGU".
O excesso vem **exclusivamente da semântica de substring**.

---

## 11. Análise dos 11 resultados oficiais (INPI)

Os 11 processos oficiais, localizados via `lower(elemento_nominativo)='magu'`:

| # | numero_inpi | nome | codigo_interno | Situação | cod. |
|---|---|---|---|---|---|
| 1 | 814317448 | MAGU | 431822 | Pedido Definitivamente Arquivado | 50 |
| 2 | 903782294 | MAGU | 2501967 | Pedido definitivamente arquivado | IPAS085 |
| 3 | 903782367 | MAGU | 2503092 | Pedido definitivamente arquivado | IPAS085 |
| 4 | 913502928 | MAGU | 3615312 | Pedido de registro de marca indeferido (sem interposição de recurso) | IPAS105 |
| 5 | 919268080 | magu | 4151488 | Aguardando apresentação ou exame de recurso contra o indeferimento | IPAS019 |
| 6 | 921233175 | MAGU | 4362154 | Aguardando apresentação ou exame de recurso contra o indeferimento | IPAS019 |
| 7 | 922437041 | MAGU | 4482935 | Registro de marca em vigor | IPAS023 |
| 8 | 928509699 | Magu | 5112835 | Pedido definitivamente arquivado | IPAS085 |
| 9 | 928817423 | MAGU | 5139416 | Registro de marca em vigor | IPAS023 |
| 10 | 937780863 | MAGU | 6067815 | Registro de marca em vigor | IPAS023 |
| 11 | 939393107 | Magu | 6248375 | Aguardando prazo de apresentação de oposição | IPAS006 |

**Todos os 11 existem no banco local**, com situação e `codigo_interno`. Titulares: 11/11
em `marcas_depositantes`. Classes Nice: 10 de 11.

---

## 12. Comparação INPI × IntelliINPI

| Critério | INPI Oficial | IntelliINPI atual | Evidência |
|---|---|---|---|
| `MAGU` | **11** | **606** | §9 |
| Busca exata | **SIM** (`lower/fold =`) | não | `lower=`=11 vs API=606 |
| Busca "contém" | não | **SIM** (`ILIKE '%..%'`) | 606 |
| Busca prefixo | não (não é o critério) | não (subconjunto) | prefixo=377 |
| Normalização acento/caixa | SIM (`magu`,`Magu`) | parcial (ILIKE, não exato) | 11 com 3 grafias |
| Campo pesquisado | nome da marca | nome + **apresentação** + **número** (OR) | `_base_query` |
| Situação | exibida (sem filtro na busca simples) | não filtra | §14 |
| Processo | 1 linha = 1 processo | 1 linha = 1 processo (OK) | 606=606=606 |
| Titular | exibido | só no detalhe | §16 |
| Classe | exibida | só no detalhe | §15 |
| Duplicidade | sem | sem | §13 |
| Ordenação | relevância/processo | `data_deposito DESC` | §5 |
| Paginação | sim | `LIMIT/OFFSET` + `COUNT(*)` | §4 |

---

## 13. Duplicidades

- `marcas`: 6.645.491 linhas / 6.645.491 `codigo_interno` distintos → **sem duplicidade**.
- Universo `MAGU`: 606 linhas / 606 processos / 606 códigos → **sem duplicidade**.
- 360 nomes normalizados distintos para 606 processos: **reutilização legítima**, não duplicidade.
- **Nenhum** registro duplicado por `(processo, marca)`.

Conclusão: o volume extra **não** vem de linhas repetidas nem de eventos históricos, e sim
da **correspondência parcial (substring)**.

---

## 14. Situações

Os 11 processos oficiais cobrem 6 situações (Arquivado, Indeferido, Em vigor, Recurso,
Oposição). O IntelliINPI **já possui o snapshot de situação atual** por processo
(`descricao_situacao`, `codigo_situacao`) e **não** filtra por situação na busca simples —
o que é coerente com o INPI. Melhoria futura: filtro opcional de situação.

---

## 15. Classes

- Nice: `marcas_classificacoes_nice` (`edicao_nice`, `classe_nice`, `especificacao`), N por `codigo_interno`.
- Nacional: `marcas_classificacoes_nacionais`. Viena: `marcas_classificacoes_viena`.
- Para os 11 "MAGU": **10** têm classe Nice (8 classes distintas).
- Formato oficial `NCL(11) 30` = `edicao_nice` + `classe_nice`.

---

## 16. Titulares

- Titulares em `marcas_depositantes` (`nome`, `cnpj_cpf_titular`, `tipo_pfpj_titular`, `pais`, `estado`), N por `codigo_interno`.
- **11/11** dos processos "MAGU" têm depositante localizado.
- A API atual **não** retorna titular na listagem (`MarcaOut`), só no detalhe (`MarcaDetail.depositantes`).

---

## 17. Regra oficial encontrada

> **ATENÇÃO — limitação de fonte:** não foi possível acessar a documentação oficial nem a
> BuscaWeb do INPI durante esta investigação (sem conectividade HTTP para `gov.br`).
> A regra abaixo é **deduzida por evidência observável** (os 11 do enunciado vs. 10 estratégias
> testadas localmente), **não** por documentação citada.

Evidência: somente `lower(elemento_nominativo) = 'magu'` retorna **exatamente 11**, e os 11
incluem 3 grafias de caixa ("MAGU","Magu","magu"). Comportamento compatível:

- **Correspondência exata do nome da marca**, case-insensitive (provavelmente acento-insensível).
- **Não** é prefixo, **não** é substring.
- Dimensões separadas: classe, titular, situação, número.

**Pendência para a próxima etapa:** confirmar a regra junto à documentação oficial do INPI
antes de fixar a semântica (ex.: validar `MAGÚ`, `MAGU'S`, `NIKE`, `PETROBRAS` na BuscaWeb real).

---

## 18. Causa raiz

**CRÍTICO (única):** o endpoint `/api/marcas/search` usa **substring**
(`elemento_nominativo ILIKE '%q%'`) enquanto o INPI usa **correspondência exata
case-insensitive** do nome da marca.

| Fonte | `lower='magu'` | `ILIKE '%magu%'` |
|---|---:|---:|
| Banco local (`marcas`) | **11** | **606** |
| CSV original INPI | **11** | **606** |
| INPI oficial (enunciado) | **11** | — |

O 606 é bit-a-bit `ILIKE '%MAGU%'`; o 11 é bit-a-bit `lower/fold = 'magu'`.
**A causa não é dado — é regra de busca.**

### Problemas secundários

| # | Severidade | Problema |
|---|---|---|
| S1 | ALTO | O `OR` mistura `elemento_nominativo` × `descricao_apresentacao` × `numero_inpi` numa única caixa de busca. |
| S2 | MÉDIO | ILIKE não normaliza acento; `fold` (indexado) não é usado. |
| S3 | MÉDIO | Sem modo de busca (exato/prefixo/contém). |
| S4 | MÉDIO | Titular fora da listagem; classe só no detalhe. |
| S5 | BAIXO | Ordenação fixa; sem relevância. |
| S6 | BAIXO | `COUNT(*)`+`OFFSET` em 6.6M (aceitável; candidato a keyset). |
| S7 | BAIXO | Frontend busca a cada tecla (sem debounce). |

---

## 19. Impacto

- **Funcional (ALTO):** até ~55× mais resultados que o esperado → baixa usabilidade e
  credibilidade no módulo Marcas e no global search.
- **Dados (BAIXO):** os dados estão corretos; é problema de **regra**, não de integridade.
- **Performance (BAIXO hoje):** atual = 3.2 ms (trgm). Exata via `lower()` sem índice = 1.34 s,
  **mas** o índice `fold()` já existe e resolve a exata em **0.79 ms**.

---

## 20. Solução recomendada

Tornar a busca de marcas **semanticamente equivalente ao INPI**: correspondência **exata
case+acento-insensível** do nome, usando o `fold()` já indexado, e **separar as dimensões**.

### 20.1 Estratégia (backend)

Substituir, em `_base_query`, o `OR` de ILIKE por uma busca parametrizada por `match_mode`:

- `exact` (default, compatível com INPI): `fold(marcas.elemento_nominativo) = fold(:q)`
- `prefix`: `fold(marcas.elemento_nominativo) LIKE fold(:q) || '%'`
- `contains`: `marcas.elemento_nominativo ILIKE '%' || :q || '%'` (mantido para quem quiser amplo)

Regras:
- `numero_inpi`: comparar **separadamente** (igualdade/prefixo), nunca no `OR` do nome.
- `descricao_apresentacao`: **não** fazer parte da busca por nome (dimensão distinta).
- Manter auth/RBAC, paginação e ordenação atuais.

### 20.2 Banco

- **Índice já existe:** `ix_marcas_elemento_nominativo_fold btree (fold(elemento_nominativo))`
  → atende `exact` a 0.79 ms. **Nenhum índice novo é obrigatório** para a correção.
- Opcional (prefixo performático): `... (fold(elemento_nominativo) text_pattern_ops)`
  para acelerar `LIKE 'q%'` acento-insensível (hoje cai no trgm, ~9.5 ms — já aceitável).
- Opcional (acento em `contains`): usar `unaccent`, ou manter trigram.

### 20.3 API (contrato proposto)

```
GET /api/marcas/search
  ?q=MAGU
  &match_mode=exact|prefix|contains   # default: exact
  &numero_inpi=...
  &situacao=...
  &page=1&page_size=20
```

Resposta inalterada (`pagination` + `items`). Sugestão: incluir `titular` (1º depositante)
e `classe_nice` resumida em `MarcaOut` para paridade com a tabela oficial.

### 20.4 Frontend

Em `src/app/marcas/page.tsx`:
- Seletor de modo (Exato / Prefixo / Contém), default **Exato**.
- Debounce (ex.: 300 ms) para evitar busca a cada tecla.
- Enviar `match_mode` no `useMarcas`; exibir Titular/Classe se `MarcaOut` evoluir.

### 20.5 Arquivos a alterar (próxima etapa)

| Arquivo | Mudança |
|---|---|
| `backend/app/routers/marcas.py` | `_base_query`: `fold` + `match_mode`; remover OR apresentação/número |
| `backend/app/schemas/search.py` | (opcional) `titular`/`classe` em `MarcaOut` |
| `frontend/src/lib/hooks.ts` | `MarcaFilters.match_mode` + envio do param |
| `frontend/src/app/marcas/page.tsx` | seletor de modo + debounce |
| `backend/tests/` | testes de semântica exact/prefix/contains |

---

## 21. Impacto de performance

Medições reais (EXPLAIN ANALYZE) no banco de 6.645.491 linhas:

| Estratégia | Plano | Índice | Execução |
|---|---|---|---|
| `ILIKE '%MAGU%'` (atual) | Bitmap Heap Scan | `ix_marcas_elemento_nominativo_trgm` | **3.2 ms** |
| `lower()='magu'` (sem índice) | **Parallel Seq Scan** | — | **1.340 ms** |
| **`fold()=fold('MAGU')`** (recomendado) | Bitmap Index Scan | `ix_marcas_elemento_nominativo_fold` | **0.79 ms** |
| `ILIKE 'MAGU%'` (prefixo) | Bitmap Index Scan | `ix_marcas_elemento_nominativo_trgm` | **9.5 ms** |

Conclusão: a correção é **mais rápida** que o comportamento atual (0.79 ms vs 3.2 ms) para o
caso comum de busca exata. `COUNT(*)` e `OFFSET` seguem aceitáveis; keyset pagination
fica como melhoria futura.

---

## 22. Estratégia de testes

1. **Semântica:** `q=MAGU&match_mode=exact` → `total == 11`; `contains` → 606; `prefix` → 377.
2. **Caixa/acento:** `magu`, `Magu`, `MAGU` → mesmo conjunto; `MAGÚ` (se aplicável) ≤ 11.
3. **Processo:** `q=814317448&match_mode=exact` não deve casar por nome.
4. **Regressão:** login/RBAC, paginação, ordenação por `data_deposito DESC`.
5. **Performance:** EXPLAIN confirmando uso do índice `fold`.
6. **Paridade:** cada um dos 11 `numero_inpi` retornável e com detalhe (titular+classe).

---

## 23. Critérios de aceite

- [ ] `q=MAGU` (default `exact`) retorna **11**, com `total=11`.
- [ ] `q=magu` / `q=Magu` retornam os mesmos 11 (case-insensitive).
- [ ] `match_mode=contains` retorna 606 (compatibilidade/opt-in).
- [ ] Ordenação e paginação preservadas; RBAC intacto.
- [ ] EXPLAIN usa `ix_marcas_elemento_nominativo_fold` no modo exato.
- [ ] 11/11 processos com detalhe contendo titular e classe.

---

## 24. Comandos de prova (read-only, reproduzíveis)

```sql
-- 606 (IntelliINPI atual)
SELECT count(*) FROM marcas WHERE elemento_nominativo ILIKE '%MAGU%';

-- 11 (INPI oficial)
SELECT count(*) FROM marcas WHERE lower(elemento_nominativo) = lower('MAGU');

-- 11 + uso do índice fold (recomendado)
SELECT count(*) FROM marcas WHERE fold(elemento_nominativo) = fold('MAGU');
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM marcas WHERE fold(elemento_nominativo) = fold('MAGU');

-- Sem duplicidade
SELECT count(*), count(DISTINCT codigo_interno) FROM marcas;
```

---

## 25. Conclusão

A divergência **não é de dados** — o banco e o CSV oficial do INPI produzem os mesmos
números (11 exato / 606 substring). A causa é **exclusivamente a semântica de busca**:
o IntelliINPI usa `ILIKE '%q%'` (substring, em 3 campos com OR), enquanto o INPI usa
**correspondência exata case-insensitive** do nome da marca. Os 11 processos oficiais
**existem** na base local, com situação, titular e classe. A correção é pequena, localizada
em `routers/marcas.py`, e **melhora** a performance (o índice `fold` já existe).

---

## 26. Resumo executivo

```
CAUSA RAIZ:
  /api/marcas/search usa substring (elemento_nominativo ILIKE '%q%')
  em vez de correspondência EXATA case-insensitive (lower/fold =).

POR QUE INPI RETORNA 11:
  11 = count(lower(elemento_nominativo) = 'magu') — busca exata do nome.

POR QUE INTELLIINPI RETORNA 606:
  606 = count(elemento_nominativo ILIKE '%MAGU%') — busca por substring,
  capturando MAGUARY(32), MAGUS(25), MAGUILA(14), YYY YAMAGUCHI, etc.

OS 11 PROCESSOS EXISTEM NO NOSSO BANCO:  SIM (11/11 localizados)

OS DADOS FORAM IMPORTADOS CORRETAMENTE:  SIM
  (CSV original: lower='magu'->11 e ILIKE '%MAGU%'->606; idêntico ao banco;
   sem duplicidade: 6.645.491 linhas = 6.645.491 códigos)

O PROBLEMA É DADO OU REGRA DE BUSCA:  REGRA DE BUSCA (100%)

CORREÇÃO RECOMENDADA:
  Usar fold(marcas.elemento_nominativo) = fold(:q) no modo exato (default),
  parametrizado por match_mode (exact|prefix|contains); remover apresentação/número do OR.

ARQUIVOS QUE PRECISARÃO SER ALTERADOS:
  - backend/app/routers/marcas.py     (núcleo da correção)
  - frontend/src/lib/hooks.ts         (param match_mode)
  - frontend/src/app/marcas/page.tsx  (seletor de modo + debounce)
  - backend/app/schemas/search.py     (opcional: titular/classe)
  - backend/tests/                     (testes de semântica)

BANCO PRECISA SER ALTERADO:  NÃO (índice fold já existe; novos são opcionais)

REIMPORTAÇÃO É NECESSÁRIA:  NÃO

RISCO DA CORREÇÃO:  BAIXO (mudança localizada no WHERE; dados intactos)

PERFORMANCE ESPERADA:  MELHORA no modo exato (0.79 ms vs 3.2 ms atuais)

PRÓXIMO PASSO:
  Confirmar a regra exata do INPI na BuscaWeb real (MAGÚ, MAGU'S, NIKE, PETROBRAS)
  e então implementar match_mode=exact com fold() em routers/marcas.py.
```

---

*Investigacão conduzida apenas com consultas read-only (SELECT/EXPLAIN). Nenhum código,
tabela, índice, dado ou migração foi modificado. Documentação oficial do INPI não pôde ser
acessada (sem conectividade HTTP), portanto a regra foi deduzida por evidência observável.*
