# Registro de Decisões Pendentes de Produto — NIT

**Data:** 2026-10-09 · **Natureza:** Planejamento. **Nenhuma decisão foi tomada em nome do product owner.**
**Fonte:** `QUESTIONARIO_DECISOES_PRODUTO_NIT.md` (auditoria preservada), convertido em registro com recomendação, impacto e bloqueio.

> As recomendações abaixo são **provisórias** e claramente identificadas. Somente as marcadas como bloqueadoras impedem o início de uma fase; as demais podem ser decididas durante a execução.

---

## 1. Registro de decisões

| ID | Pergunta | Recomendação provisória | Alternativas | Impacto técnico | Impacto comercial | Se adiar | Fase | Bloqueia? |
|---|---|---|---|---|---|---|---|---|
| **P1** | Uma ICT ou várias instituições? | Multi-tenant (já suportado) | Single-tenant | Define o modelo de isolamento e seed | Define modelo comercial | Só no início de F1 | F1 | **Sim** |
| **P2** | Vários campi/deptos/labs com autonomia? | Unity = campus/depto | Tenant por campus | Define uso de Company/Unity e escopo | Segmentação de clientes | F1 | F1 | **Sim** |
| **P4** | Unidades compartilham ou separam portfólio? | Portfólio do tenant com escopo por unidade | Portfólio isolado por unidade | Define filtros e autorização de ativos | Percepção de isolamento | F1 | F1 | **Sim** |
| **P3** | Pesquisadores de instituições parceiras? | Permitir `Person` sem usuário | Bloquear externos | Campos externos em `DisclosureInventor` | Coautoria interinstitucional | F1 | F1 | Parcial |
| **D1** | Níveis de sigilo | 4 níveis (público/interno/restrito/confidencial) | 2 níveis | Enum + ACL | Requisito de confiança | F1 | F1 | **Sim** |
| **D2** | Onde armazenar arquivos | Object storage privado (S3/MinIO) | Disco local | Infra + serviço de storage | Custo/infra | F1 | F1 | **Sim** |
| **D5** | Auditoria de acesso a sigilosos | Registrar todo download | Sem auditoria | `record_audit` em download | Conformidade | F1 | F1 | **Sim** |
| **D3** | Antivírus no upload | Sim (ClamAV) | Adiar | Pipeline de upload | Segurança | Não bloqueia MVP | F1 | Parcial |
| **D4** | Retenção de sigilosos | Configurável | Fixa | Job + política | LGPD | F1 | Piloto | Parcial |
| **E1** | Etapas do workflow | Proposta→Triagem→Parecer→Decisão | Outra sequência | Máquina de estados | Aderência ao processo | F1 | F1 | **Sim** |
| **E4** | Quem decide (alçadas) | Comitê com alçada configurável | Decisor único | `WorkflowTransition.required_permission/role` | Governança | F1 | F1 | **Sim** |
| **E2** | Workflow igual para todos? | Configurável por tenant | Fixo | Seed de workflow por tenant | Flexibilidade | F1 | F1 | Parcial |
| **E3** | Quais pareceres | Técnico, jurídico, comercial | Só técnico | Entidade `Evaluation` | Completude | F1 | F1/F2 | Parcial |
| **A1** | Quem pode submeter | Pesquisador e NIT | Só NIT | Permissões/portal | Adoção | F1 | F1 | **Sim** |
| **A3** | Protocolo automático | Auto `NIT-AAAA-NNNN` | Manual | Serviço de protocolo | Rastreabilidade | F1 | F1 | Parcial |
| **A5** | Anexos obrigatórios/formato/tamanho | Opcional; PDF/DOCX/img; ~25MB | Outro | Validação de upload | Usabilidade | F1 | F1 | Parcial |
| **I1/I3** | Tipos de ativo e vínculo público | Ativo interno com vínculo **opcional** | Vínculo obrigatório | Modelo `IPAsset`+`IPAssetPublicLink` | Proposta de valor | F1 | F1 | **Sim** |
| **S1** | Alvo de infraestrutura | Suportar Docker; definir alvo | Cloud/on-prem | Backup/logging/segredos | Custo/operação | F0 | F0 | **Sim (F0)** |
| **S4** | Exigências LGPD formais | RIPD antes de docs confidenciais | Sem formalização | Governança | Risco legal | F1 | F1 | **Sim** |
| **C1** | SaaS ou implantação | Suportar ambos | Só um | Admin SaaS vs. local | Vendas | F1 | F1 | Parcial |
| **S3** | Backup/RTO/RPO | Dump diário, RPO 24h | Outro | Operação | Continuidade | F0 | F0 | Parcial |
| **R1** | FORMICT obrigatório? | Confirmar com MCTI/instituição | — | Export oficial | Conformidade | F4 | F4 | Não |
| **X1/X2** | Portais externos | Mesmo sistema, perfis restritos | Portal separado | Auth/identidade | Escopo | F5 | F5 | Não |
| **N1/N2/N3** | Integrações (SIGA/SEI/BuscaWeb/e-mail) | Avaliar após MVP | — | APIs externas | Diferencial | F5 | F5 | Não |
| **C2/C3/C4** | Módulos/quotas/i18n | `TenantModule` como entitlements; cotas depois; pt-BR | — | Feature flags | Monetização | Pós-MVP | Pós-MVP | Não |

> Demais itens (O1–O3, A2, A4, E5, F1–F4, R2, R3, S2, S5) não bloqueiam e podem ser decididos durante a fase — ver o questionário original.

---

## 2. Decisões que realmente bloqueiam a arquitetura

Estas alteram **modelo de domínio**, **isolamento multi-tenant** ou **segurança** e por isso precedem a implementação:

1. **D1 + D2 + D5** — confidencialidade e storage de documentos.
2. **E1 + E4** — workflow e alçadas.
3. **I1 + I3** — tipos de ativo e vínculo com registro público.
4. **P1 + P2 + P4** — estrutura institucional e escopo de portfólio.
5. **S1 + S4** — alvo de infraestrutura e requisitos LGPD.

**Podem ser adiadas** (com defaults): todas as de prioridade "Parcial"/"Não" que não estejam na lista acima.

---

## 3. Decisões indispensáveis para aprovar o início de F0 e F1

### Para iniciar **F0** (fundação)
- **S1 — Alvo de infraestrutura** (cloud/on-prem/híbrido): define *onde* rodar backup, logging e segredos.
- Recomendações provisórias (não bloqueantes): S3 backup diário/RPO 24h; git com remote privado + branch protegida.

> Se S1 não for respondida, F0 pode avançar apenas nos itens agnósticos de infra (segredos, git remote, handler de erro), deixando backup/observabilidade pendentes.

### Para iniciar **F1** (MVP)
1. **D1/D2/D5** — níveis de sigilo, storage (S3/MinIO), auditoria de download.
2. **E1/E4** — sequência de estados e alçadas de decisão.
3. **I1/I3** — tipos de ativo do MVP e política de vínculo com registro público.
4. **P1/P2/P4** — uma ou várias instituições; campi/unidades; escopo de portfólio.
5. **S4** — exigências LGPD (RIPD) antes de documentos confidenciais.

---

## 4. Perguntas objetivas para o product owner (somente as indispensáveis)

1. **S1:** O produto rodará em nuvem, on-premise ou híbrido no primeiro piloto?
2. **D2:** Podemos assumir object storage privado (S3/MinIO) para documentos, ou há restrição de armazenamento local?
3. **D1:** Confirmamos 4 níveis de sigilo (público/interno/restrito/confidencial)?
4. **E1/E4:** O fluxo `Proposta → Triagem → Parecer → Decisão` com decisão por comitê está correto para o piloto?
5. **P1/P2/P4:** A instituição-alvo é uma única ICT com múltiplos campi, e o portfólio é do tenant com escopo por unidade?
6. **I1/I3:** O MVP deve permitir ativo sem vínculo obrigatório com registro público?
7. **S4:** Há exigência formal de RIPD/DPO antes de armazenar documentos confidenciais?

> As demais decisões (modelo comercial, FORMICT, portais, integrações) podem ser tratadas como recomendações provisórias e revisadas ao final de cada fase.

---

## 5. Consequência de adiar cada decisão bloqueadora

| Decisão | Consequência de adiar |
|---|---|
| D1/D2/D5 | Documentos não podem ser criados com segurança → retrabalho e risco LGPD |
| E1/E4 | Workflow desenhado "no escuro" → modelo de dados e alçadas errados |
| I1/I3 | Portfólio mal modelado → migração dolorosa de dados de ativos |
| P1/P2/P4 | Escopo de isolamento indefinido → vazamento intra-tenant ou over-engineering |
| S1/S4 | Sem alvo, backup/logging/segredos ficam no ar; sem LGPD, risco legal |
