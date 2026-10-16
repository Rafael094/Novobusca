# Arquitetura Alvo — Evolução Incremental para NIT

**Data:** 2026-10-09 · **Natureza:** Planejamento. Nenhum modelo/migração criado.
**Complementa:** `AUDITORIA_TECNICA_INTELLIINPI.md` e `MODELO_DOMINIO_NIT.md` (auditorias preservadas).

---

## 1. Princípios de organização

A stack atual **permanece**: FastAPI, SQLAlchemy 2.x, PostgreSQL, Alembic, Next.js 15/React 19/Tailwind/TanStack Query.

**Não reorganizar diretórios existentes.** Os domínios abaixo são **referências conceituais**; o mapeamento para pastas só ocorre quando o código novo o exigir. Sugestão de baixo risco, alinhada ao padrão atual (`routers/<x>.py`, `models/<x>.py`):

```
backend/app/
  models/nit/<dominio>.py      # novas tabelas (aditivas)
  routers/nit/<dominio>.py     # novos endpoints sob /api/nit/*
  schemas/nit/<dominio>.py     # Pydantic
  services/                    # só onde há regra de negócio reutilizável
```

Alternativa mínima (recomendada para F1): `models/nit.py`, `schemas/nit.py`, `routers/nit/__init__.py` — menos arquivos, mesmo isolamento por prefixo.

---

## 2. Domínios, responsabilidades e artefatos

| Domínio | Responsabilidade | Modelos principais | Endpoints | Autorização | Testes |
|---|---|---|---|---|---|
| **Identity & Access** (existente) | Auth, tenant, RBAC | `User`, `Role`, `Resource`, `*Policy`, `Group` | `/api/auth/*`, `/api/admin/*` | já existe | manter 94 |
| **Tenant & Organization** (existente) | Instituições, unidades | `Tenant`, `Company`, `Unity`, `Department` | `/api/clientes/*` | `require_permission` | manter |
| **Public IP** (existente) | PI pública INPI | `marcas`, `patentes` + filhas | `/api/marcas`, `/api/patentes` | `MARCAS_*`/`PATENTES_*` | manter |
| **Invention Disclosure** (novo) | Comunicação de invenção | `InventionDisclosure`, `DisclosureInventor`, `InventionDocument` | `/api/nit/disclosures/*` | `NIT_DISCLOSURE_*` + escopo unidade | isolamento tenant+unidade, transições |
| **Institutional IP Assets** (novo) | Portfólio interno | `IPAsset`, `IPAssetPublicLink` | `/api/nit/assets/*` | `NIT_ASSET_*` + escopo | vínculo público, escopo |
| **Workflow & Evaluation** (novo) | Estados, transições, pareceres | `WorkflowState`, `WorkflowTransition`, `WorkflowInstance`, `Evaluation` | `/api/nit/workflow/*` | `NIT_EVAL_*` | transições inválidas, alçadas |
| **Document Management** (novo) | Storage privado, confidencialidade | `InventionDocument`, `DocumentAcl` | `/api/nit/documents/*` | ACL + RBAC | acesso cruzado, MIME, download |
| **Committees** (novo) | Comitês e decisões | `Committee`, `CommitteeMember`, `CommitteeDecision` | `/api/nit/committees/*` | `NIT_COMMITTEE_*` | quórum, conflito |
| **Technology Transfer** (F3) | Oferta, negociação, licença | `TechnologyOffer`, `ExpressionOfInterest`, `Negotiation`, `License`, `Assignment` | `/api/nit/tt/*` | `NIT_TT_*` | pipeline, NDA |
| **Contracts** (F3) | Contratos, obrigações, royalties | `Contract`, `ContractObligation`, `Royalty` | `/api/nit/contracts/*` | `NIT_CONTRACT_*` | vigência, alertas |
| **Research Projects** (F4) | Projetos de P&D | `Project`, `ProjectMember`, `Funder`, `ProjectMilestone`, `ProjectAssetLink` | `/api/nit/projects/*` | `NIT_PROJECT_*` | vínculos |
| **Reporting & Audit** (evolutivo) | KPIs, trilha | reuso `AuditLog` + views | `/api/nit/reports/*` | `NIT_REPORT_*`, `AUDIT_VIEW` | consistência de indicadores |

**Sem CQRS/event sourcing/mensageria.** Eventos são, no máximo, gatilhos de log/notificação simples. Integrações externas só na F5.

---

## 3. Camada de serviços

A auditoria técnica apontou ausência de `services/` de domínio (lógica em routers). Para o NIT:
- **Introduzir `services/` apenas nos domínios novos** — não refatorar routers existentes.
- Serviços-alvo de F1: `services/storage.py` (object storage/ACL), `services/workflow.py` (validação de transições), `services/protocol.py` (geração de protocolo).
- Regra: o router valida entrada/permissão e delega a regra ao serviço.

---

## 4. Multi-tenancy e autorização (política verificável)

1. **Isolamento por instituição:** `tenant_id` de toda entidade interna vem do usuário autenticado; nunca do request (`deps.get_current_user`).
2. **Escopo por unidade:** entidades internas (ativos, comunicações) carregam `unity_id`/`company_id` opcional; consultas aplicam `scoped_resources` do `AccessContext`.
3. **Toda query de dados internos** filtra por `tenant_id` **e** pelo escopo aplicável; escrita valida o escopo do alvo (não só o de entrada).
4. **Exceções administrativas:** master admin opera cross-tenant (já comprovado por teste) e deve ser auditado de forma explícita.
5. **Acesso de pesquisadores:** papel restrito, escopo às próprias comunicações/ativos.
6. **Acesso de usuários externos:** na F5, perfil de parceiro com dados mínimos.
7. **Compartilhamento controlado de documentos:** `DocumentAcl` explode o acesso explícito além do RBAC.
8. **Auditoria de consultas/downloads sensíveis:** todo download de documento não-público gera `record_audit`.

> **Invariante testável:** “nenhuma resposta contém dado de tenant/unidade não autorizada”. Deve ser coberto por teste em cada domínio novo.

---

## 5. Modelo de dados proposto (conceitual, sem migration)

### 5.1 Entidades indispensáveis ao MVP (F1)

| Entidade | Papel | Campos-chave | Origem |
|---|---|---|---|
| `InventionDisclosure` | Comunicação de invenção | `tenant_id`, `protocol`, `title`, `summary`, `origin_unity_id`, `prior_disclosure_date`, `status`, `created_by` | nova |
| `DisclosureInventor` | Vínculo inventor↔comunicação | `disclosure_id`, `person_id` (nullable), `external_name/email` (inventor sem conta), `share_pct`, `is_primary` | nova |
| `InventionDocument` | Documento do dossiê | `disclosure_id`/`asset_id`, `storage_key`, `mime`, `size`, `sha256`, `confidentiality_level` (obrigatório), `version` | nova |
| `DocumentAcl` | Concessão explícita | `document_id`, `user_id`/`group_id`, `permission` (`VIEW`/`DOWNLOAD`/`MANAGE`) | nova |
| `WorkflowState` | Estado do processo | `tenant_id`, `code`, `name`, `order`, `is_terminal` | nova |
| `WorkflowTransition` | Transição válida + alçada | `from_state`, `to_state`, `required_permission`, `required_role` | nova |
| `WorkflowInstance` | Instância por comunicação | `disclosure_id`, `current_state_id` | nova |
| `Evaluation` | Parecer | `disclosure_id`, `kind` (téc/jur/com), `evaluator_id`, `decision`, `notes`, `trl` (F2) | nova |
| `IPAsset` | Ativo institucional | `tenant_id`, `unity_id`, `asset_type`, `title`, `status`, `disclosure_id` (origem opcional) | nova |
| `IPAssetPublicLink` | Vínculo a registro público | `asset_id`, `source` (`INPI_MARCA`/`INPI_PATENTE`), `external_ref` (`codigo_interno`), `synced_at` | nova |

### 5.2 Entidades de fases posteriores
F2: `Committee`, `CommitteeMember`, `CommitteeDecision`, campos de TRL/custo. F3: `TechnologyOffer`, `ExpressionOfInterest`, `Negotiation`, `License`, `Assignment`, `Contract`, `ContractObligation`, `Royalty`. F4: `Project`, `ProjectMember`, `Funder`, `ProjectMilestone`, `ProjectAssetLink`, `Startup`, `IncubationProgram`. Transversais: `Notification`.

### 5.3 Invariantes
- Todo novo modelo: `UUIDPrimaryKeyMixin` + `TimestampMixin` + `SoftDeleteMixin` + `tenant_id` (exceto tabelas de catálogo global).
- `InventionDocument.confidentiality_level` **NOT NULL**; acesso exige ACL **e** RBAC.
- Transições só pelas arestas declaradas em `WorkflowTransition` (não campo livre).
- `IPAssetPublicLink` **não usa FK dura** para `marcas`/`patentes` (globais) — guarda `source` + `external_ref` + `synced_at`.
- Unicidade: `(tenant_id, protocol)` em `InventionDisclosure`; `(asset_id, source, external_ref)` em `IPAssetPublicLink`.

---

## 6. Separação entre PI pública e interna (crítica)

Cinco conceitos **distintos**, jamais fundidos em uma tabela:

1. **Registro público INPI** — `marcas`/`patentes`, global, read-only, importado.
2. **Ativo institucional** — `IPAsset`, do tenant, editável.
3. **Comunicação de invenção** — `InventionDisclosure`, pré-depósito.
4. **Processo interno** — `WorkflowInstance`/`Evaluation` (tramitação).
5. **Instrumento de transferência** — `License`/`Contract` (F3).

O vínculo 1↔2 é **referencial** (`IPAssetPublicLink`), preservando procedência e histórico de sincronização, sem criar dependência indevida com a base pública (que pode ser reimportada).

---

## 7. Gestão documental (requisitos)

- **Storage:** object storage privado (S3/MinIO) — decisão D2. Nunca servir direto do disco público.
- **Níveis de confidencialidade:** público/interno/restrito/confidencial (decisão D1).
- **ACL por documento e por dossiê** (`DocumentAcl`).
- **Validação de MIME + assinatura do arquivo** (magic bytes), não só extensão.
- **Limites de tamanho** por tipo; rejeitar acima do teto.
- **Download por URL temporária** (presigned) e curta.
- **Registro de acesso** (auditoria de cada download de item não-público).
- **Retenção e descarte** configuráveis (LGPD).
- **Backup e recuperação** do bucket.
- **Malware:** varredura (ClamAV) — decisão D3, pode ser PARCIAL no MVP.
- **LGPD:** classificação de dados e base legal — decisão S4.

> Salvar em bucket privado **não** basta: sem ACL+auditoria+URL assinada, o controle não existe.

---

## 8. Migrações e compatibilidade

- Migrações **pequenas e revisáveis**; uma preocupação por revisão.
- **Aditivas por padrão** (novas tabelas/colunas/nullable). Tabelas existentes não são reestruturadas sem necessidade + plano de dados.
- Verificar **índices e constraints** novos (FKs com `ondelete` explícito, unicidades).
- **Rollback** testado (`alembic downgrade`) para cada migração de F1.
- **Backup antes** de mudanças críticas (R-09).
- **Testes de upgrade/downgrade** (ver `PLANO_TESTES_E_CRITERIOS_ACEITE.md`).
- **Implantação por ambiente:** aplicar em ambiente de teste, depois piloto, depois produção.
- Convenção de nomes de revisão alinhada às existentes (`<hash>_<descricao>.py`).
