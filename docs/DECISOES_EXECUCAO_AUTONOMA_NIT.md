# Decisões da Execução Autônoma — NIT

**Data:** 2026-10-09 · **Natureza:** premissas provisórias adotadas para permitir avanço sem
inventar decisões de negócio. **Todas reversíveis** e registradas para revisão do product owner.

> Regra aplicada: quando uma decisão de produto não está confirmada, adota-se a opção
> **conservadora, configurável e aditiva**, que **não reduz segurança** e **não altera
> irreversivelmente** o domínio. Nenhuma decisão legal/institucional foi tomada por conta própria.

---

## 1. Premissas adotadas

### P-01 · Confidencialidade documental (D1/D5)
- **Adotado:** enum `ConfidentialityLevel` = `PUBLIC | INTERNAL | RESTRICTED | CONFIDENTIAL`.
- **Defaults seguros:** documento sem nível explícito = `INTERNAL` (nunca `PUBLIC`).
- **Auditoria:** todo download de documento com nível ≠ `PUBLIC` gera `AuditLog` (`DOCUMENT_DOWNLOAD`).
- **Reversível:** níveis são um enum de string; ampliar/reduzir = nova migração aditiva.

### P-02 · Storage (D2)
- **Adotado:** interface `StorageBackend` + adaptador `LocalPrivateStorage` gravando **fora** do
  diretório público (`settings.document_storage_path`, default `backend/var/documents`).
- **Chaves físicas:** `documents/{tenant_id}/{document_id}` (sem nome original no path → sem traversal).
- **Não declarado pronto para produção:** S3/MinIO é plugável via `STORAGE_BACKEND=s3` (stub que
  falha explicitamente se não configurado — nunca finge sucesso).
- **Reversível:** troca de backend por configuração.

### P-03 · Workflow e alçadas (E1/E4)
- **Adotado:** estados `PROPOSAL → TRIAGE → EVALUATION → DECISION → CLOSED`, com `REJECTED`
  como destino alternativo. Transições declaradas em tabela (`workflow_transitions`), **seed por
  tenant**, editável.
- **Alçadas:** transição com `required_permission` (default: quem não tiver a permissão recebe 403).
  Não existe transição "livre".
- **Reversível:** transições são dados, não código.

### P-04 · Ativos e vínculo público (I1/I3)
- **Adotado:** `IPAsset` interno; `IPAssetPublicLink` **opcional**, sem FK dura para
  `marcas`/`patentes` (guarda `source`, `external_ref`, `synced_at`).
- **Reversível:** vínculo é tabela separada; tornar obrigatório = validação, não migração destrutiva.

### P-05 · Estrutura institucional (P1/P2/P4)
- **Adotado:** 1 tenant = 1 instituição (ICT); `Unity` = campus/unidade; portfólio é **do tenant**
  com `unity_id` **opcional** de escopo.
- **Escopo por unidade:** aplicado quando `unity_id` estiver preenchido E o contexto do usuário
  declarar escopo por unidade. Sem escopo declarado → acesso tenant-wide (equivalente ao atual).

### P-06 · Igualdade intra-tenant (R-01)
- **Adotado:** validação de que toda entidade referenciada (unity, disclosure, asset, avaliador)
  pertence ao **mesmo tenant**. Testes negativos explícitos.
- **Nota:** `scoped_resources` (escopo fino company/unity do RBAC) **não** é reaplicado nesta fase
  porque nenhuma entidade NIT exige; fica registrado como evolução (F2+) para não introduzir
  regressão na resolução de políticas existente.

### P-07 · Protocolo (A3)
- **Adotado:** formato `NIT-{ANO}-{SEQ:4d}` único por tenant, gerado **na mesma transação** do
  INSERT, com `UniqueConstraint(tenant_id, protocol)` como garantia final e retry no conflito.

---

## 2. Decisões que permanecem EXCLUSIVAS do product owner

| ID | Motivo |
|---|---|
| **S1** | Alvo de infraestrutura (cloud/on-prem/híbrido) — define backup/observabilidade/segredos |
| **S4** | Exigência formal de RIPD/DPO antes de documentos confidenciais (não declaramos conformidade LGPD) |
| **R1** | Obrigatoriedade do FORMICT e formato oficial (F4) |
| **D2-prod** | Provisionamento real de bucket S3/MinIO (F1 usa adaptador local privado) |
| **D3** | Antivírus/ClamAV em produção |
| **E-mail/SSO** | Credenciais de provedor SMTP e IdP institucional (F5) |

> Nenhuma dessas foi simulada. O código correspondente está preparado atrás de interface/configuração
> e **falha explicitamente** (ou fica desabilitado) quando a configuração está ausente.
