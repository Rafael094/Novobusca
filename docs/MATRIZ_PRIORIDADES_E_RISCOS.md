# Matriz de Prioridades e Riscos — Evolução NIT

**Data:** 2026-10-09 · **Natureza:** Planejamento (somente leitura sobre o código).
**Consolida:** riscos R1–R8 (executiva), T1–T8 (técnica) e S1–S12 (segurança) em uma matriz única, sem duplicidade.
**Legenda:** P0 = bloqueia desenho seguro · P1 = necessário para piloto/MVP · P2 = produção comercial · P3 = melhoria adiável.

> **Nota de atualização:** o risco "sem git" (R1/S2/T1) foi **verificado como corrigido** nesta etapa — existe repositório git com commit `7a32c4b` e `.gitignore` adequado. Reclassificado para risco residual **R-02**.

---

## 1. Matriz de riscos

| ID | Risco | Evidência | Prob. | Impacto | Sev. | Prior. | Depende de | Consequência | Ação recomendada | Critério de aceite | Fase |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **R-01** | Escopo Company/Unity resolvido no RBAC mas **não imposto** a dados internos | `rbac.py::_collect_policies` produz `scoped_resources`; nenhum router NIT consome | Média | Alto | Alta | **P0** | Modelo de domínio | Membro de um lab vê/edita ativo de outro lab do mesmo tenant | Aplicar `scoped_resources` em toda query/escrita de entidade interna | Usuário da Unidade A recebe 403 em ativo da Unidade B | F1 |
| **R-02** | Governança git incompleta (sem *remote*, sem proteção de branch) | Repo existe (`7a32c4b`), 130 arquivos versionados; sem remote; `docs/` não rastreado | Média | Médio | Média | **P1** (era P0) | — | Trabalho apenas local; sem histórico remoto/revisão | Criar remote privado, proteger `main`, versionar `docs/` | `git remote -v` não vazio; branch protegida; `docs/` commitado | F0 |
| **R-03** | Modelo de documentos confidenciais inexistente | Nenhum modelo de anexo/confidencialidade | Alta (ao criar) | Alto | Alta | **P0** | Decisões D1/D2/D5 | Vazamento de dossiê/LGPD; retrabalho | Storage privado + níveis + ACL + auditoria de download antes de F1 | Acesso cruzado a doc restrito → 403; log de download | F1 |
| **R-04** | Segredos com defaults fracos | `config.py`: `jwt_secret="dev-secret-change-me"`, refresh, master password | Média | Alto | Alta | **P1** | — | Comprometimento total se subir sem `.env` | Falhar o boot quando segredo = default | Boot sem `.env` levanta erro; teste de config | F0 |
| **R-05** | Token em `localStorage` (XSS) | `frontend/src/lib/api.ts` (`ACCESS_KEY`/`REFRESH_KEY`) | Média | Alto | Alta | **P1** | — | Roubo de sessão via XSS | Refresh em cookie httpOnly + CSP; reduzir TTL do access | Cookie httpOnly + CSP ativos | Piloto |
| **R-06** | Rate limiting só no login e in-memory | `rate_limit.py`; sem throttling em busca/export/IA | Média | Médio | Média | **P1** | Infra (Redis?) | DoS e abuso de custo de IA | Limites por usuário/tenant em endpoints caros; store compartilhado | Endpoint caro retorna 429 sob abuso | Piloto |
| **R-07** | Busca "contains" sem trigram explícito | `routers/marcas.py::_base_query` usa `ILIKE '%x%'` sobre 6,6M linhas | Alta | Médio | Média | **P1** | — | Latência alta/full scan | Índice GIN `pg_trgm`/`unaccent` ou FTS; medir com `EXPLAIN ANALYZE` | Plano sem Seq Scan; p95 dentro do alvo | F1 |
| **R-08** | Papel de outro tenant atribuível | `routers/admin/users.py` (`_set_roles`) | Baixa | Alto | Média | **P1** | — | Elevação de privilégio entre tenants | Validar que o papel pertence ao tenant do usuário | Atribuir papel de outro tenant → 400/403 | F0/F1 |
| **R-09** | Sem backup/restore documentado | Docker usa volume `pgdata`; sem rotina de dump | Média | Alto | Alta | **P1** | Infra (R-14) | Perda de dados irreversível | `pg_dump` agendado, retenção, teste de restore, RTO/RPO | Restore validado em ambiente limpo | F0 |
| **R-10** | Sem logging estruturado / handler 500 engole exceção | `main.py::_unhandled` retorna 500 sem log | Alta | Médio | Média | **P2** | — | Sem rastro forense | Logging JSON + correlação de request | Log de erro com stack e request-id | F0 |
| **R-11** | Sem política de retenção/LGPD operacional | retenção ausente; sem RIPD/base legal | Média | Alto | Alta | **P2** | Decisão S4 | Não conformidade LGPD | Definir base legal, retenção, descarte; RIPD antes de docs sigilosos | Política aprovada + job de retenção | Piloto/Prod |
| **R-12** | `IntegrityError` não tratado | `routers/clientes.py` faz `add`+`commit` sem catch | Média | Baixo | Baixa | **P2** | — | HTTP 500 em duplicidade | Catch → 409 | Criação duplicada → 409 | F1 |
| **R-13** | `count(*)` por request e export CSV em memória | `routers/*`, `app/export.py` | Média | Médio | Média | **P2** | R-07 | Latência/esgotamento de memória | Contagem aproximada; streaming por chunks | Export não carrega tudo em memória | F2 |
| **R-14** | Sem definição de alvo de infraestrutura | `docker-compose.yml` local; sem alvo cloud/on-prem | Alta | Alto | Alta | **P1** | Decisão S1 | Backup/logging/segredos sem lugar definido | Decidir alvo e provisionar base | Ambiente-alvo documentado e provisionado | F0 |
| **R-15** | Sem MFA para perfis sensíveis | `User.mfa` existe, não exigido | Média | Médio | Média | **P2** | — | Conta admin vulnerável | MFA obrigatório para master/admin/jurídico | Login de admin exige 2º fator | Prod |
| **R-16** | Sync INPI síncrono no worker da API | `routers/admin/inpi_sync.py` | Média | Médio | Média | **P2** | — | Bloqueio do worker; timeout | Worker/processo dedicado | Sync não bloqueia a API | F2 |
| **R-17** | Sem validação de schema da fonte INPI | `ingestion/*` | Baixa | Médio | Baixa | **P3** | — | Carga silenciosamente incorreta | Validar colunas esperadas antes do load | Carga falha se schema mudar | F4 |
| **R-18** | Tipos TS manuais (drift com backend) | `frontend/src/lib/types.ts` | Média | Baixo | Baixa | **P3** | — | Bugs de contrato silenciosos | Gerar tipos de OpenAPI | Tipos gerados no build | F5 |
| **R-19** | Sem testes de concorrência/carga/migração | suíte atual (94 testes) | Média | Médio | Média | **P2** | — | Regressões não detectadas | Ver `PLANO_TESTES_E_CRITERIOS_ACEITE.md` | Suíte cobre os cenários listados | Por fase |
| **R-20** | Sem plano de recuperação de desastre | ausência | Média | Alto | Alta | **P2** | R-09 | Indisponibilidade prolongada | Documentar RTO/RPO e runbook | Runbook testado | Prod |

---

## 2. Ordem de tratamento recomendada

1. **F0 (imediato):** R-02, R-04, R-09, R-10, R-14, R-08.
2. **F1 (docs confidenciais/MVP):** R-03, R-01, R-07, R-12 (+ R-19).
3. **Piloto:** R-05, R-06, R-11.
4. **Produção:** R-13, R-15, R-16, R-20.
5. **Adiável:** R-17, R-18.

---

## 3. Matriz funcional consolidada (domínios × situação × fase)

| Domínio | Situação atual | Necessário | Dependência técnica | Dependência de produto | Risco | Prior. | Fase |
|---|---|---|---|---|---|---|---|
| Pesquisa marcas/patentes | **Implementado** | Manter + desempenho | — | — | R-07 | P1 | F0/F1 |
| Monitoramento | **Implementado** (por usuário) | Alertas de NIT por prazo | Padrão existente | Notificações | — | P2 | F2 |
| CRM / relacionamento | **Implementado** | Papéis de parceiro | Reuso direto | Modelo comercial | R-01 | P2 | F1/F3 |
| Comunicação de invenção | **Ausente** | Entidade + protocolo + inventores | Workflow, docs | A1/A3 | R-03 | P1 | F1 |
| Inventores/pesquisadores | **Parcial** (`Person`) | Vínculo à comunicação, externos sem conta | `Person` existe | P3 | — | P1 | F1 |
| Avaliação técnica/jur./com. | **Ausente** | Pareceres + TRL | Workflow | E3 | — | P1 | F1/F2 |
| Comitês e decisões | **Parcial** (`Group`) | `Committee`+decisões | RBAC | E4 | — | P1 | F2 |
| Portfólio de ativos | **Ausente** | `IPAsset`+vínculo público | Vínculo sem FK dura | I1/I3 | R-01 | P1 | F1 |
| Documentos e confidencialidade | **Ausente** | Storage privado+ACL | Decisão D2 | D1/D5 | R-03 | **P0** | F1 |
| Transferência de tecnologia | **Ausente** | Oferta/negociação/licença | Ativos | Modelo TT | — | P2 | F3 |
| Contratos/obrigações/royalties | **Ausente** | Contrato+obrigação | Licença | F1/F2 | — | P2 | F3 |
| Projetos de P&D | **Ausente** | Projeto+equipe+financiador | Ativos | Escopo P&D | — | P3 | F4 |
| Startups/incubação | **Ausente** | Startup+programa | Ativos | Estratégia | — | P3 | F4 |
| Indicadores/BI | **Parcial** (dashboard PI+CRM) | KPIs de NIT | Dados NIT | R2 | — | P2 | F2/F4 |
| Portal do pesquisador | **Ausente** | Submissão/acompanhamento | Auth | X1 | R-05 | P2 | F5 |
| Portal da empresa | **Ausente** | Catálogo/interesse/NDA | Auth parceiro | X2 | — | P3 | F5 |
| Administração/governança | **Parcial** (RBAC+auditoria) | Alçadas, retenção, recertificação | RBAC | K | R-11 | P2 | F1/F2 |

> Detalhamento por requisito em `MATRIZ_ADERENCIA_FUNCIONAL_NIT.md` (auditoria original, preservada).
