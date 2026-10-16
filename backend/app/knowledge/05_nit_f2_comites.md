# Fluxo NIT — F2: Comitês, Avaliações e Decisões

## Objetivo

Formalizar a avaliação colegiada e a decisão sobre as comunicações de invenção, e
registrar os pareceres e deliberações. Modelos em `backend/app/models/nit.py`;
API em `backend/app/routers/nit/`.

## F2.1 Comitês

- **Comitês** reúnem os avaliadores e registram reuniões e membros.
- Endpoints: `GET/POST /api/nit/committees`, `GET /api/nit/committees/{id}`
  (detalhe), gestão de **membros** (`members`).
- Telas: `/nit/comites` e `/nit/comites/[id]`.
- Permissão: `NIT_COMMITTEE_VIEW`.

## F2.2 Avaliações (pareceres)

- Um parecer (`NIT_EVALUATION_*`) é registrado sobre uma comunicação, tipicamente
  técnico, jurídico e/ou comercial.
- Criar parecer exige `NIT_EVALUATION_CREATE`.
- O conjunto de pareceres alimenta a etapa `EVALUATION` do workflow.

## F2.3 Decisões

- A decisão (`NIT_DECISION`) encerra a análise: aprovar e encerrar (`CLOSED`) ou
  rejeitar (`REJECTED`); ambas exigem **justificativa**.
- Registrada por quem tem a permissão `NIT_DECISION`.

## F2.4 Reuniões e agenda

- **Reuniões** de comitê e **itens de agenda** são registrados para rastrear o que
  foi deliberado.

## Fluxo resumido (F2)

1. A comunicação chega à etapa `EVALUATION`.
2. Avaliadores registram pareceres (técnico/jurídico/comercial).
3. O comitê se reúne (reunião + agenda) e delibera.
4. É registrada a **decisão**: aprovar/encerrar ou rejeitar (com justificativa).
5. A comunicação segue para `CLOSED`/`REJECTED`.

## Perguntas típicas

- **"Onde ficam os comitês?"** → menu **NIT → Comitês** (`/nit/comites`).
- **"Quem pode dar o parecer?"** → usuários com `NIT_EVALUATION_CREATE`.
- **"Quem pode decidir?"** → usuários com `NIT_DECISION`.
