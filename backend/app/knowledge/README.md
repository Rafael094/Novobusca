# Base de conhecimento do assistente

Esta pasta é a **fonte de verdade** que o assistente de IA (chat) lê para responder
perguntas sobre o sistema (módulos, telas, caminhos e fluxos).

## Como funciona

- `backend/app/services/knowledge.py` carrega todos os arquivos `.md` desta pasta,
  os divide em seções (por cabeçalhos) e realiza busca textual (FTS nativo, sem
  dependências externas) para recuperar os trechos mais relevantes à pergunta.
- Os trechos recuperados são enviados como contexto ao modelo (DeepSeek), que
  responde em português **somente com base no conteúdo recuperado**.

## Arquivos

| Arquivo | Conteúdo |
|---------|----------|
| `00_visao_geral.md` | O que é o sistema, blocos do menu, arquitetura. |
| `01_navegacao_e_telas.md` | Todas as telas, rotas e permissões. |
| `02_fluxo_crm.md` | Fluxo comercial (oportunidades, propostas, atividades). |
| `03_fluxo_inpi.md` | Marcas, patentes, busca, monitoramento, análises de IA. |
| `04_nit_f1_comunicacoes.md` | F1: comunicações, documentos, workflow, ativos. |
| `05_nit_f2_comites.md` | F2: comitês, avaliações e decisões. |
| `06_nit_f3_transferencia_contratos.md` | F3: ofertas, negociações, contratos, royalties. |
| `07_nit_f4_projetos_startups.md` | F4: projetos de P&D, startups, incubação. |
| `08_nit_f5_indicadores_integracoes.md` | F5: indicadores, FORMICT, BI, portais, integrações. |
| `09_rbac_admin_multitenant.md` | RBAC, multi-tenancy, administração, auditoria. |
| `10_referencia_api.md` | Endpoints por módulo. |
| `11_faq.md` | Perguntas frequentes e respostas rápidas. |

## Como atualizar

Edite ou adicione arquivos `.md` aqui. O índice é recarregado automaticamente (há
cache com verificação de alteração por tempo de modificação). Mantenha uma seção
por assunto, com títulos claros — eles viram as referências ("fontes") mostradas
nas respostas do assistente.
