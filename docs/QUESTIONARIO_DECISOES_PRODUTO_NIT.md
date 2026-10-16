# Questionário de Decisões de Produto — NIT

**Data:** 2026-10-09
**Instrução:** Responder **antes** de iniciar a implementação. Cada item indica por que importa, o que depende dela, a recomendação técnica provisória, se bloqueia o desenvolvimento e se é configurável por instituição.

Legenda de bloqueio: **BLOQUEIA** = impede iniciar a fase dependente; **PARCIAL** = permite iniciar com valor default; **NÃO** = pode ser definido durante a fase.

---

## 1. Público-alvo e tipo de instituição

| ID | Pergunta | Por que importa / o que depende | Recomendação provisória | Bloqueia? | Configurável? |
|---|---|---|---|---|---|
| P1 | Serve uma ICT única ou várias instituições? | Define multi-tenancy e modelo comercial | Multi-tenant (já suportado) | **BLOQUEIA** (F1) | Não |
| P2 | Uma instituição tem vários campi/deptos/labs com autonomia? | Define uso de Company/Unity e escopo | Unity para campus/departamento | **BLOQUEIA** (F1) | Sim |
| P3 | Há pesquisadores de instituições parceiras coautores? | Define se `Person` pode ser externa | Permitir `Person` sem usuário | PARCIAL | Sim |
| P4 | Unidades compartilham portfólio ou têm portfólios separados? | Define escopo do ativo | Portfólio do tenant com escopo por unidade | **BLOQUEIA** (F1) | Sim |

---

## 2. Modelo comercial

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| C1 | SaaS por assinatura ou implantação institucional? | Define Admin SaaS vs. local | Suportar ambos | PARCIAL |
| C2 | Módulos vendidos separadamente? | `TenantModule` como feature flag | Usar `TenantModule` como entitlements | NÃO |
| C3 | Limites/quotas por plano (usuários, exports, IA)? | Define rate limiting por plano | Introduzir cotas por tenant | NÃO |
| C4 | Multi-idioma? | Define i18n | pt-BR agora; preparar i18n | NÃO |

---

## 3. Estrutura organizacional

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| O1 | Hierarquia oficial (Reitoria → NIT → Labs)? | Define modelo de unidades | Company=instituição, Unity=unidade | PARCIAL |
| O2 | Pesquisador pertence a múltiplas unidades? | Define cardinalidade | N:N | NÃO |
| O3 | Comitês são formais ou informais? | Define modelagem | `Group` + `Committee` | NÃO |

---

## 4. Comunicação de invenção

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| A1 | Quem pode submeter? (pesquisador, NIT, ambos) | Define permissões e portal | Ambos | **BLOQUEIA** (F1) |
| A2 | Formulário fixo ou configurável? | Define schema dinâmico | Campos fixos + customizados | PARCIAL |
| A3 | Protocolo automático? Qual formato? | Define geração | Auto `NIT-AAAA-NNNN` | PARCIAL |
| A4 | Prazo legal/divulgação anterior? | Define validações | Registrar data + alerta | NÃO |
| A5 | Anexos obrigatórios? Formatos/tamanho? | Define storage | Opcional; PDF/DOCX/img; ~25MB | PARCIAL |

---

## 5. Avaliação e aprovação

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| E1 | Quais etapas do workflow? | Define máquina de estados | Proposta → Triagem → Parecer → Decisão | **BLOQUEIA** (F1) |
| E2 | Workflow igual para todas as instituições? | Define config. | Configurável por tenant | PARCIAL |
| E3 | Quais pareceres são exigidos? | Define entidades | Técnico, jurídico, comercial | PARCIAL |
| E4 | Quem decide (alçadas)? | Define RBAC/workflow | Comitê com alçada configurável | **BLOQUEIA** (F1) |
| E5 | Conflito de interesse declarado formalmente? | Define campo + bloqueio | Declaração obrigatória | NÃO |

---

## 6. Propriedade intelectual

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| I1 | Tipos de ativo (marca, patente, software, desenho, know-how)? | Define enum/modelos | Todos os 5 | **BLOQUEIA** (F1) |
| I2 | Titularidade compartilhada com percentuais? | Define modelagem | Sim, N:N com percentual | PARCIAL |
| I3 | Vincular ativo a registro público do INPI? | Liga com base importada | Sim, tabela de referência | **BLOQUEIA** (F1) |
| I4 | Gerir custos e manutenção (anuidades)? | Define modelo financeiro | Sim | NÃO |
| I5 | Software exige registro (programa de computador)? | Catálogo prevê dataset | Incluir quando disponível | NÃO |

---

## 7. Transferência tecnológica

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| T1 | Catálogo é público (site) ou interno? | Define portal externo | Interno primeiro; publicar depois | PARCIAL |
| T2 | Empresas se cadastram online? | Define portal de empresas | Sim, com aprovação | NÃO |
| T3 | Tipos de instrumento (licença, cessão, cooperação)? | Define entidades | Todos | NÃO |
| T4 | Exclusividade e território controlados? | Define campos | Sim, estruturados | NÃO |

---

## 8. Contratos e finanças

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| F1 | Contratos vinculam-se a ativo, projeto ou ambos? | Define cardinalidade | Ambos | NÃO |
| F2 | Royalties/pagamentos controlados na plataforma? | Define módulo financeiro | Registrar (não contabilizar) | NÃO |
| F3 | Integração com sistema financeiro institucional? | Define integrações | Fora do MVP | NÃO |
| F4 | Alertas de vencimento e obrigações? | Define notificações | Sim, e-mail + in-app | NÃO |

---

## 9. Confidencialidade e documentos

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| D1 | Níveis de sigilo (público/interno/restrito/confidencial)? | Define ACL documental | 4 níveis | **BLOQUEIA** (F1) |
| D2 | Onde armazenar arquivos (object storage vs. disco)? | Define infraestrutura | Object storage privado (S3/MinIO) | **BLOQUEIA** (F1) |
| D3 | Exigência de antivírus/varredura? | Define pipeline de upload | Sim (ClamAV) | PARCIAL |
| D4 | Retenção de documentos sigilosos? | Define política LGPD | Retenção configurável | PARCIAL |
| D5 | Auditoria de acesso a documentos sigilosos? | Define log detalhado | Registrar todo download | **BLOQUEIA** (F1) |

---

## 10. Portais externos

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| X1 | Pesquisador usa o mesmo sistema ou portal separado? | Define autenticação | Mesmo sistema, perfil restrito | PARCIAL |
| X2 | Empresa externa é usuário do sistema? | Define identidade | Sim, perfil de parceiro | NÃO |
| X3 | Portais exigem SSO institucional (SAML/Google/MS)? | Define integração de auth | Avaliar após MVP | NÃO |

---

## 11. Relatórios e indicadores

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| R1 | FORMICT é obrigatório? Qual formato/versão? | Define export | Confirmar com MCTI/instituição | PARCIAL |
| R2 | Quais KPIs de direção? | Define dashboard | Invenções, contratos, receita | NÃO |
| R3 | Relatórios exportáveis em PDF/Excel? | Define geração | CSV agora; PDF depois | NÃO |

---

## 12. Integrações

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| N1 | Integrar com SIGA/SEI/sistema de pesquisa? | Define APIs externas | Avaliar após MVP | NÃO |
| N2 | Sincronizar com BuscaWeb do INPI em tempo real? | SPIKE documenta ausência | Manter base local | NÃO |
| N3 | Notificações via e-mail institucional? | Define SMTP/provider | SMTP configurável | NÃO |

---

## 13. Segurança, infraestrutura e operação

| ID | Pergunta | Por que importa | Recomendação | Bloqueia? |
|---|---|---|---|---|
| S1 | Deploy: cloud, on-premise ou híbrido? | Define arquitetura | Suportar Docker; definir alvo | **BLOQUEIA** (F0) |
| S2 | MFA obrigatório para perfis sensíveis? | Define auth | Sim, para admin/jurídico | NÃO |
| S3 | Política de backup/RTO/RPO? | Define operação | Dump diário, RPO 24h | PARCIAL |
| S4 | Exigências LGPD formais (DPO, RIPD)? | Define governança | RIPD antes de docs confidenciais | **BLOQUEIA** (F1) |
| S5 | Suporte e SLA esperados? | Define operação SaaS | Definir por contrato | NÃO |

---

## 14. As 5 decisões mais críticas (bloqueiam o início seguro)

1. **D1/D2/D5** — modelo de confidencialidade e storage de documentos.
2. **E1/E4** — workflow e alçadas.
3. **I1/I3** — tipos de ativo e vínculo com registro público.
4. **P1/P2/P4** — estrutura institucional e escopo de portfólio.
5. **S1/S4** — alvo de infraestrutura e requisitos LGPD.

Todas alteram o **modelo de domínio**, o **isolamento multi-tenant** ou a **segurança** — por isso devem preceder a implementação.