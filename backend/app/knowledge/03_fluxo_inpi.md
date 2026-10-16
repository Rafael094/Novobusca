# Fluxo — INPI (Marcas, Patentes, Busca, Monitoramento, Análises de IA)

## Objetivo

Pesquisar e monitorar marcas e patentes a partir das bases de dados abertos do
INPI, cruzando dados locais com análise de risco assistida por IA. API em
`backend/app/routers/marcas.py`, `patentes.py`, `search.py`, `analises.py`.

## Marcas

- **Pesquisa:** `GET /api/marcas/search` — filtros por nome, classe NICE,
  situação, titular; paginação e exportação CSV.
- **Detalhe:** `GET /api/marcas/{id}`.
- **Monitoramento:** `GET /api/marcas/monitoramento` — acompanhamento de marcas de
  interesse.
- Tela: `/marcas` e `/monitoramento`.

## Patentes

- **Pesquisa:** `GET /api/patentes/search` — por título, resumo, depositante, IPC.
- **Detalhe:** `GET /api/patentes/{id}`.
- Tela: `/patentes`.

## Busca global

- `GET /api/search` — busca unificada por marcas e patentes (módulo `BUSCA`).

## Análises de IA (análise de risco de registro de marca)

Fluxo (`backend/app/routers/analises.py`):

1. **Recuperação:** busca na base local marcas por similaridade de nome (+ classe
   NICE quando `strict_nice`) e patentes relacionadas por palavra-chave.
2. **Consulta ao modelo:** envia o contexto ao serviço `deepseek` pedindo um JSON
   em português: `overall_risk`, `score` (0–100), `summary`, `conflicts`,
   `recommendations`.
3. **Montagem do laudo:** o resultado é mesclado com os candidatos determinísticos
   localizados, gerando o `AnalysisReport`.
4. **Sem chave de API:** retorna **HTTP 503** com mensagem clara — nunca inventa
   análise.

- **Status:** `GET /api/analises/status` informa se a IA está configurada e o modelo.
- **Execução:** `POST /api/analises`.
- Tela: `/analises`.

## Relatórios

- **Relatórios:** `GET /api/relatorios` (módulo `RELATORIOS`). Tela: `/relatorios`.

## Perguntas típicas

- **"Como pesquiso uma marca?"** → menu **INPI → Marcas**, digite o nome e filtre
  por classe NICE.
- **"Como pesquiso uma patente?"** → menu **INPI → Patentes**.
- **"Por que a análise de IA deu erro 503?"** → o servidor não tem a chave
  `DEEPSEEK_API_KEY` configurada; o sistema prefere falhar a inventar resultado.
