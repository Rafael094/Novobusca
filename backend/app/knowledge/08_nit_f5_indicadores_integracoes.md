# Fluxo NIT — F5: Indicadores, FORMICT, BI, Notificações, Portais e Integrações

## Objetivo

Consolidar dados do NIT em indicadores e relatórios oficiais, distribuir
notificações e integrar-se a portais externos.

## F5.1 Indicadores e FORMICT

- **Indicadores** do NIT com apoio ao preenchimento do **FORMICT** (formulário anual
  de política de propriedade intelectual).
- Endpoints: `GET /api/nit/indicators` (`NIT_INDICATOR_VIEW`).
- Tela: `/nit/indicadores`.

## F5.2 BI & Relatórios

- Painéis analíticos e relatórios agregados do NIT.
- Endpoint/tela: `NIT_BI_VIEW`, tela `/nit/bi`.

## F5.3 Notificações

- **Notificações** para o usuário (prazos, mudanças de estado, alertas).
- Endpoint: `GET /api/nit/notifications` (`NIT_NOTIFICATION_VIEW`).
- Tela: `/nit/notificacoes`.

## F5.4 Portais externos

- Publicação/vitrine em **portais externos**. Permissão `NIT_PORTAL_VIEW`.
- Tela: `/nit/portais`.

## F5.5 Integrações

- **Integrações** com sistemas externos (ex.: sistemas acadêmicos/institucionais).
- Permissão `NIT_INTEGRATION_VIEW`.
- Tela: `/nit/integracoes`.

## F5.6 Painel do NIT (dashboard)

- Visão consolidada do NIT: `NIT_REPORT_VIEW`, tela `/nit`.

## Fluxo resumido (F5)

1. Todos os módulos (F1–F4) geram dados operacionais.
2. Os indicadores agregram esses dados para o FORMICT e para gestão interna.
3. Notificações mantêm as equipes avisadas de prazos e mudanças.
4. Portais e integrações estendem o alcance do NIT para fora do sistema.

## Perguntas típicas

- **"Onde vejo os indicadores do NIT?"** → menu **NIT → Indicadores & FORMICT**.
- **"Onde vejo minhas notificações?"** → menu **NIT → Notificações**.
- **"Onde configuro integrações?"** → menu **NIT → Integrações**.
