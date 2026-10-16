# Fluxo NIT — F1: Comunicações, Documentos, Workflow e Ativos

## Objetivo

Registrar uma **comunicação de invenção** (disclosure) e conduzi-la pelo fluxo de
triagem → avaliação → decisão até virar (ou não) um **ativo de propriedade
intelectual**. Routers em `backend/app/routers/nit/`; máquina de estados em
`backend/app/services/workflow.py` e estados semente em `backend/app/seed_nit.py`.

## F1.1 Comunicação de invenção (Disclosure)

Estados do workflow (`backend/app/models/nit.py`):

`PROPOSAL` (Proposta) → `TRIAGE` (Triagem) → `EVALUATION` (Avaliação) →
`DECISION` (Decisão) → `CLOSED` (Encerrado) / `REJECTED` (Rejeitado).

- **Estado inicial:** `PROPOSAL` — "Comunicação registrada, aguardando triagem".
- **Estados terminais:** `CLOSED` e `REJECTED`.

## F1.2 Workflow (transições e autoridades)

As transições são **dados** (por tenant), não código, e cada aresta exige uma
permissão. Transições padrão (`_DEFAULT_TRANSITIONS` em `seed_nit.py`):

| De → Para | Ação | Permissão exigida | Justificativa? |
|-----------|------|-------------------|----------------|
| PROPOSAL → TRIAGE | Iniciar triagem | `NIT_WORKFLOW_TRIAGE` | Não |
| TRIAGE → EVALUATION | Enviar para avaliação | `NIT_WORKFLOW_TRIAGE` | Não |
| TRIAGE → PROPOSAL | Devolver ao proponente | `NIT_WORKFLOW_TRIAGE` | Sim |
| EVALUATION → DECISION | Encaminhar para decisão | `NIT_EVALUATION_CREATE` | Não |
| EVALUATION → TRIAGE | Devolver à triagem | `NIT_EVALUATION_CREATE` | Sim |
| DECISION → CLOSED | Aprovar e encerrar | `NIT_DECISION` | Sim |
| DECISION → REJECTED | Rejeitar | `NIT_DECISION` | Sim |
| PROPOSAL → REJECTED | Rejeitar na triagem | `NIT_WORKFLOW_TRIAGE` | Sim |
| TRIAGE → REJECTED | Rejeitar na triagem | `NIT_WORKFLOW_TRIAGE` | Sim |
| EVALUATION → REJECTED | Rejeitar após avaliação | `NIT_EVALUATION_CREATE` | Sim |

> Regra: rejeitar exige a mesma autoridade do estágio que está sendo deixado; e as
> transições de rejeição/retorno exigem **justificativa**.

## F1.3 Documentos e ACL

- **Upload (recomendado, pela UI):** na tela de detalhe da comunicação
  `/nit/comunicacoes/[id]`, o painel `DocumentsPanel` envia o arquivo com o nível de
  sigilo. O upload dispara automaticamente ao escolher o arquivo.
- **Upload (API):** `POST /api/nit/documents` (multipart/form-data):
  - `file` (obrigatório);
  - `disclosure_id` **ou** `asset_id` (um é obrigatório);
  - `confidentiality_level` (padrão `INTERNAL`);
  - `title`, `description` (opcionais).
  - Requer permissão `NIT_DOCUMENT_UPLOAD`. O `tenant_id` é derivado do usuário.
- **Validações do servidor:** verificação por *magic bytes* (PDF, DOCX, XLSX, PNG,
  JPEG, GIF), limite de tamanho (`DOCUMENT_MAX_SIZE_MB`, padrão 25 MB) e chave de
  armazenamento opaca `documents/{tenant}/{document_id}` (nunca servida como
  estático). Leitura exige `NIT_DOCUMENT_VIEW` + (documento público ou ACL explícita).

Níveis de sigilo: `PUBLIC`, `INTERNAL`, `RESTRICTED`, `CONFIDENTIAL`.

- **Tela somente leitura:** `/nit/documentos` apenas lista e baixa (sem botão de
  upload).

## F1.4 Ativos de PI (Asset)

- Uma invenção aprovada torna-se um **ativo de PI** (`NIT_ASSET_*`).
- **Painel:** `GET /api/nit/assets`. Telas: `/nit/ativos` e `/nit/ativos/[id]`.
- **Portfólio avançado:** `/nit/portfolio` (visões agregadas do portfólio).

## Fluxo resumido (F1)

1. Proponente registra comunicação → estado `PROPOSAL`.
2. Triagem (`NIT_WORKFLOW_TRIAGE`) → `TRIAGE`, anexando documentos.
3. Pareceres técnico/jurídico/comercial → `EVALUATION`.
4. Instância competente decide (`NIT_DECISION`) → `CLOSED` (aprovado) ou `REJECTED`.
5. Se aprovado, cria-se o **ativo de PI**, base para transferência de tecnologia.

## Perguntas típicas

- **"Como registro uma invenção?"** → menu **NIT → Comunicações** e crie uma nova
  comunicação; ela inicia em **Proposta**.
- **"Como anexo um documento?"** → abra a comunicação em
  `/nit/comunicacoes/[id]` e use o painel de documentos (escolher sigilo + arquivo).
- **"Como vejo os ativos de PI?"** → menu **NIT → Portfólio de Ativos**.
