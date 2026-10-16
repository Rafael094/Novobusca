# Fluxo NIT — F4: Projetos de P&D, Startups e Incubação

## Objetivo

Gerenciar projetos de pesquisa e desenvolvimento, o acompanhamento de startups e o
ciclo de incubação, conectando-os aos ativos e contratos (F1/F3).

## F4.1 Projetos de P&D

- Um **projeto** agrupa atividades, marcos, equipe e resultados de pesquisa.
- Endpoints: `GET/POST /api/nit/projects`, `GET /api/nit/projects/{id}`.
- Telas: `/nit/projetos` e `/nit/projetos/[id]`. Permissão: `NIT_PROJECT_VIEW`.

## F4.2 Startups

- **Startups** vinculadas ao NIT são cadastradas e acompanhadas.
- Endpoints: `GET/POST /api/nit/startups`, `GET /api/nit/startups/{id}`.
- Telas: `/nit/startups` e `/nit/startups/[id]`. Permissão: `NIT_STARTUP_VIEW`.

## F4.3 Incubação

- O ciclo de **incubação** acompanha a evolução das startups (etapas, marcos,
  graduação).
- Tela: `/nit/incubacao` (mesma permissão `NIT_STARTUP_VIEW`).

## Fluxo resumido (F4)

1. Uma ideia/laboratório dá origem a um **projeto de P&D**.
2. O projeto pode gerar novas comunicações de invenção (F1).
3. Startups ligadas ao NIT entram no programa de **incubação** e são acompanhadas.
4. Resultados alimentam o portfólio (F1), a transferência (F3) e os indicadores (F5).

## Perguntas típicas

- **"Onde vejo os projetos de P&D?"** → menu **NIT → Projetos de P&D**.
- **"Onde acompanho as startups?"** → menu **NIT → Startups** ou **Incubação**.
