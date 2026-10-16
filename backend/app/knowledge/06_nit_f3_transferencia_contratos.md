# Fluxo NIT — F3: Transferência de Tecnologia, Negociações, Contratos e Ofertas

## Objetivo

Levar um ativo de PI ao mercado: publicá-lo como oferta no catálogo, negociar com
interessados, formalizar contrato e acompanhar royalties e obrigações contratuais.

## F3.1 Catálogo de tecnologias (Ofertas)

- Um ativo pode ser publicado no **catálogo** como uma **oferta** (`NIT_OFFER_*`).
- Endpoints: `GET/POST /api/nit/offers`; telas `/nit/catalogo` e
  `/nit/catalogo/[id]`. Permissão: `NIT_OFFER_VIEW`.

## F3.2 Interesses e Negociações

- Interessados registram **interesse** por uma oferta; o interesse evolui para uma
  **negociação** (`NIT_NEGOTIATION_*`).
- Endpoints: `GET/POST /api/nit/interests`, `GET/POST /api/nit/negotiations`,
  `GET /api/nit/negotiations/{id}` (detalhe). Telas: `/nit/negociacoes`.
- Permissão: `NIT_NEGOTIATION_VIEW`.

## F3.3 Contratos

- Fechada a negociação, formaliza-se um **contrato** (`NIT_CONTRACT_*`) com prazos,
  valores, vigência e obrigações.
- Endpoints: `GET/POST /api/nit/contracts`, `GET /api/nit/contracts/{id}`.
- Telas: `/nit/contratos` e `/nit/contratos/[id]`. Permissão: `NIT_CONTRACT_VIEW`.

## F3.4 Obrigações e Alertas

- Contratos podem gerar **obrigações** (entregas, pagamentos, relatórios) com
  **alertas de vencimento** para não perder prazos.

## F3.5 Royalties

- **Royalties** são registrados contra os contratos, com **resumo agregado**
  (`NIT_ROYALTY_*`).

## Fluxo resumido (F3)

1. Ativo aprovado (F1) é publicado como **oferta** no catálogo.
2. Interessado manifesta **interesse** → abre-se uma **negociação**.
3. Negociação aceita → **contrato** formalizado.
4. O contrato gera **obrigações** (com alertas) e **royalties**.
5. Indicadores consolidam os resultados (ver F5).

## Perguntas típicas

- **"Onde publico uma tecnologia?"** → menu **NIT → Catálogo de Tecnologias**.
- **"Onde acompanho uma negociação?"** → menu **NIT → Negociações**.
- **"Onde vejo os contratos?"** → menu **NIT → Contratos**.
- **"Como não perder um prazo de contrato?"** → acompanhe as **obrigações** e seus
  **alertas de vencimento**.
