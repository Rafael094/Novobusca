# Matriz de Aderência Funcional — Domínios de NIT

**Data:** 2026-10-09
**Natureza:** Auditoria somente leitura.

Estados: **Implementado e verificado** · **Implementado parcialmente** · **Existente, mas não verificado** · **Ausente** · **Dependente de decisão de negócio** · **Não aplicável (justificativa)**.

---

## Visão geral por domínio

| Domínio | Estado geral | Fundamento |
|---|---|---|
| A — Comunicação de invenção | **Ausente** | Nenhum modelo de comunicação/protocolo |
| B — Triagem e avaliação | **Ausente** | Nenhum workflow, parecer ou comitê |
| C — Portfólio institucional | **Ausente** (dados públicos existem) | Sem ativo interno |
| D — P&D (projetos/pesquisadores) | **Ausente** | Sem projeto, financiador, laboratório |
| E — Transferência tecnológica | **Ausente** | Sem catálogo/licença/negociação |
| F — Contratos e obrigações | **Ausente** | Sem contrato, marco, royalty |
| G — Empreendedorismo | **Ausente** | Sem startup/spin-off |
| H — Indicadores e relatórios | **Parcial** | Dashboard só conta PI + CRM |
| I — Portal do pesquisador | **Ausente** | Sem portal externo |
| J — Portal de empresas | **Ausente** | Sem catálogo público/parceiro |
| K — Governança | **Parcial** | Auditoria e RBAC existem |

---

## Domínio A — Comunicação de invenção

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| Cadastro de comunicação | **Ausente** | — | Entidade `InventionDisclosure` | P1 |
| Protocolo/número interno | **Ausente** | — | Geração de protocolo | P1 |
| Inventores vinculados | **Implementado parcialmente** | `people`, `PatenteInventor` | Vínculo interno | P1 |
| Anexos/documentos | **Ausente** | — | Modelo de documentos | **P0** |
| Confidencialidade | **Ausente** | — | Campo + ACL | **P0** |
| Divulgação anterior | **Ausente** | — | Campos + prazo | P1 |
| Projetos de origem | **Ausente** | — | Vínculo (Domínio D) | P2 |
| Parceiros/coautoria | **Implementado parcialmente** | `companies`, `customers` | Vínculo específico | P2 |
| Acompanhamento/status | **Ausente** | — | Máquina de estados | P1 |

---

## Domínio B — Triagem e avaliação

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| Workflow de triagem | **Ausente** | — | Estados + transições | P1 |
| Pareceres (téc./jur./com.) | **Ausente** | — | Entidade de parecer | P1 |
| Busca de anterioridade | **Implementado parcialmente** | `marcas.py`, `patentes.py`, `analises.py` | Vinculação à comunicação | P2 |
| Potencial comercial | **Ausente** | — | Avaliação estruturada | P2 |
| Maturidade tecnológica (TRL) | **Ausente** | — | Campo + escala | P2 |
| Comitês e decisões | **Implementado parcialmente** | `Group`/`GroupPolicy` | Entidade comitê/decisão | P1 |
| Justificativas | **Ausente** | — | Campo de decisão | P1 |
| Conflito de interesse | **Implementado parcialmente** | `DENIED` em políticas | Declaração formal | P2 |

---

## Domínio C — Portfólio institucional

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| Ativo interno (IP Asset) | **Ausente** | — | Entidade central | **P1** |
| Marcas institucionais | **Implementado parcialmente** | `marcas` (público) | Vínculo ativo↔registro | P1 |
| Patentes institucionais | **Implementado parcialmente** | `patentes` (público) | Vínculo ativo↔registro | P1 |
| Software / prog. computador | **Ausente** | dataset só catalogado | Modelo | P2 |
| Desenho industrial | **Ausente** | dataset só catalogado | Modelo | P2 |
| Know-how / segredo | **Ausente** | — | Modelo confidencial | P2 |
| Titularidade | **Implementado parcialmente** | `*_depositantes` | Percentuais internos | P1 |
| Família de patentes | **Implementado parcialmente** | `patentes_prioridades`, `patentes_vinculos` | Agrupamento interno | P2 |
| Prazos e manutenção | **Parcial** | `data_vigencia` no dashboard | Alertas/manutenção | P1 |
| Custos de manutenção | **Ausente** | — | Entidade de custo | P2 |

---

## Domínio D — Pesquisa e desenvolvimento

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| Projetos | **Ausente** | — | Entidade `Project` | P2 |
| Pesquisadores | **Implementado parcialmente** | `people` | Papel/lotação de pesquisa | P2 |
| Departamentos/laboratórios | **Implementado parcialmente** | `Department`, `Unity` | Estrutura de pesquisa | P2 |
| Financiadores | **Ausente** | — | Entidade | P3 |
| Entregas/marcos de projeto | **Ausente** | — | Milestones | P3 |
| Parcerias | **Ausente** | — | Vínculo institucional | P3 |
| Vínculo com ativos resultantes | **Ausente** | — | N:N projeto↔ativo | P2 |

---

## Domínio E — Transferência tecnológica

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| Catálogo de tecnologias | **Ausente** | — | Vitrine interna/externa | P1 |
| Prospecção de empresas | **Implementado parcialmente** | `companies`, `customers` | Pipeline de prospecção | P2 |
| Manifestações de interesse | **Ausente** | — | Entidade | P2 |
| Negociações | **Ausente** | — | Estados de negociação | P2 |
| Licenças | **Ausente** | — | Entidade | P1 |
| Cessões | **Ausente** | — | Entidade | P2 |
| Exclusividade | **Ausente** | — | Campo | P2 |
| Resultados comerciais | **Ausente** | — | Receita/royalty | P2 |

---

## Domínio F — Contratos e obrigações

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| NDA / confidencialidade | **Ausente** | — | Entidade | P1 |
| Acordos de cooperação | **Ausente** | — | Entidade | P2 |
| Contratos de pesquisa | **Ausente** | — | Entidade | P2 |
| Licenciamento | **Ausente** | — | Entidade | P1 |
| Vigências | **Ausente** | — | Períodos + alertas | P1 |
| Documentos contratuais | **Ausente** | — | Vínculo documental | P1 |
| Marcos/obrigações | **Ausente** | — | Milestones contratuais | P2 |
| Pagamentos/royalties | **Ausente** | — | Entidade financeira | P2 |

---

## Domínio G — Empreendedorismo

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| Startups/spin-offs | **Ausente** | — | Entidade | P3 |
| Incubação/aceleração | **Ausente** | — | Programa | P3 |
| Vínculo com ativos | **Ausente** | — | N:N | P3 |
| Acompanhamento de resultados | **Ausente** | — | Indicadores | P3 |

---

## Domínio H — Indicadores e relatórios

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| Dashboard operacional | **Implementado e verificado** | `routers/dashboard.py` | Só PI + CRM | — |
| Métricas de PI pública | **Implementado e verificado** | contagens, evolução | — | — |
| Indicadores de NIT | **Ausente** | — | KPIs de invenção/licença | P1 |
| Relatório de gestão | **Parcial** | `relatorios/page.tsx` | Relatórios institucionais | P2 |
| FORMICT | **Ausente** | — | Export oficial | P2 (negócio) |
| BI customizável | **Ausente** | — | Construtor de relatórios | P3 |

---

## Domínio I — Portal do pesquisador

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| Submissão de comunicação | **Ausente** | — | Portal + fluxo | P2 |
| Acompanhamento | **Ausente** | — | Status ao inventor | P2 |
| Notificações | **Ausente** | — | E-mail/in-app | P2 |
| Solicitação de ajustes | **Ausente** | — | Comentários | P2 |
| Consulta a docs autorizados | **Ausente** | — | ACL documental | **P0** (base) |
| Histórico | **Parcial** | `audit_logs` | Visão ao pesquisador | P3 |

---

## Domínio J — Portal de empresas

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| Catálogo público | **Ausente** | — | Vitrine + SEO | P3 |
| Autenticação de parceiros | **Implementado parcialmente** | auth (usuários internos) | Perfil de parceiro | P2 |
| Manifestação de interesse | **Ausente** | — | Formulário/entidade | P2 |
| Confidencialidade | **Ausente** | — | NDA digital | P1 |
| Pipeline de negociação | **Ausente** | — | CRM de TT | P2 |

---

## Domínio K — Governança

| Requisito | Estado | Evidência | Lacuna | Prioridade |
|---|---|---|---|---|
| Aprovação e alçadas | **Ausente** | — | Workflow de aprovação | P1 |
| Políticas institucionais | **Ausente** | — | Config. por instituição | P2 |
| Auditoria | **Implementado e verificado** | `audit_logs` | Retenção/imutabilidade | P1 |
| Controle documental | **Ausente** | — | Versionamento de doc | P1 |
| Conflito de interesse | **Implementado parcialmente** | `DENIED` em RBAC | Declaração formal | P2 |
| Gestão de acessos | **Implementado e verificado** | `admin/access_control.py` | Recertificação | P2 |
| Retenção e descarte | **Ausente** | — | Política + job | P2 |

---

## Resumo de prioridades

- **P0 (bloqueiam o desenho seguro):** modelo de documentos + confidencialidade/ACL.
- **P1 (MVP comercial):** comunicação de invenção, workflow, ativo interno, licença, indicadores de NIT, alçadas.
- **P2 (pós-fundação):** pareceres avançados, TRL, custos, P&D, portais, NDA digital.
- **P3 (evolutivo):** startups, BI customizável, integrações.