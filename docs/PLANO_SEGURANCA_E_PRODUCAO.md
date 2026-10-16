# Plano de Segurança e Produção — Evolução NIT

**Data:** 2026-10-09 · **Natureza:** Planejamento. Nenhum controle foi implementado ou validado em execução.
**Base:** `AUDITORIA_SEGURANCA_MULTITENANT.md` (preservada) + verificação desta etapa.

> **Aviso:** este documento **não declara conformidade LGPD**. Conformidade depende de processos, base legal e políticas institucionais, não apenas de controles técnicos.

Cada requisito tem **critério de aceite verificável**. Os grupos são: **B1** bloqueios para iniciar funcionalidades confidenciais · **B2** bloqueios para piloto institucional · **B3** requisitos para produção comercial · **B4** melhorias adiáveis.

---

## B1 — Bloqueios para iniciar funcionalidades confidenciais (antes de F1)

| ID | Requisito | Ação | Critério de aceite | Risco |
|---|---|---|---|---|
| B1-1 | Modelo de confidencialidade + storage privado | Implementar níveis + S3/MinIO privado | Documento restrito inacessível a quem não tem ACL (403) | R-03 |
| B1-2 | ACL documental + auditoria de download | `DocumentAcl` + `record_audit` em cada download | Teste de acesso cruzado e log persistido | R-03 |
| B1-3 | Escopo intra-tenant aplicado | Impor `scoped_resources` em entidades internas | Usuário da Unidade A → 403 em ativo da Unidade B | R-01 |
| B1-4 | Segredos reais obrigatórios | Falhar boot se segredo = default | Boot sem `.env` levanta erro; teste dedicado | R-04 |
| B1-5 | Backup/restore testado | `pg_dump` + restore | Restore reproduzido em ambiente limpo | R-09 |

---

## B2 — Bloqueios para piloto institucional

| ID | Requisito | Ação | Critério de aceite | Risco |
|---|---|---|---|---|
| B2-1 | Sessão mais segura (anti-XSS) | Refresh em cookie httpOnly + CSP | Cookie httpOnly setado; CSP ativa; revisão sem `localStorage` para refresh | R-05 |
| B2-2 | Rate limiting ampliado | Limites por usuário/tenant em busca/export/IA + store compartilhado | Endpoint caro retorna 429 sob abuso | R-06 |
| B2-3 | Validação de papel por tenant | Papel do usuário pertence ao seu tenant | Atribuir papel externo → 400/403 | R-08 |
| B2-4 | Logging estruturado | Log JSON + request-id; handler 500 loga stack | Erro gera log com stack e correlação | R-10 |
| B2-5 | LGPD operacional | Base legal, retenção, descarte; RIPD antes de docs sigilosos | Política aprovada + job de retenção ativo | R-11 |
| B2-6 | Alvo de infraestrutura definido | Decidir cloud/on-prem/híbrido e provisionar | Ambiente-alvo documentado e disponível | R-14 |

---

## B3 — Requisitos para produção comercial

| ID | Requisito | Critério de aceite |
|---|---|---|
| B3-1 | Contas de serviço/segredos em cofre | Nenhum segredo em arquivo versionado ou imagem |
| B3-2 | MFA para perfis sensíveis | Login de admin/jurídico exige 2º fator |
| B3-3 | Backup agendado + retenção + RTO/RPO | Rotina ativa; runbook de restore testado |
| B3-4 | Monitoramento e alertas | Alerta para erro 5xx, dataset INPI `FAILED`, backup falho |
| B3-5 | Desempenho medido | `EXPLAIN ANALYZE` sem Seq Scan nas buscas; p95 dentro do alvo |
| B3-6 | Sync INPI fora do worker da API | Sync não bloqueia request da API |
| B3-7 | Tratamento de erro consistente | Duplicidade → 409; validação → 422; interno → 500 logado |
| B3-8 | Plano de recuperação de desastre | DR runbook documentado e exercitado |

---

## B4 — Melhorias adiáveis

- Geração de tipos TS a partir do OpenAPI (R-18).
- Validação de schema da fonte INPI (R-17).
- Contagem aproximada / streaming real de export (R-13).
- Recertificação periódica de acessos, i18n, SSO institucional.

---

## Checklist por área

- **Gestão de segredos:** sem defaults válidos em produção; rotação; `.env` nunca versionado (confirmado no `.gitignore`).
- **Git/proteção do código:** remote privado, branch protegida, revisão obrigatória (R-02).
- **Autenticação/sessões:** Argon2id (ok), refresh rotativo com hash (ok), TTL curto, cookie httpOnly no piloto.
- **RBAC/isolamento:** 3 caminhos com DENY-wins (ok); aplicar escopo a dados internos (B1-3).
- **Rate limiting:** hoje só login/in-memory → distribuir (B2-2).
- **Logs/auditoria:** `AuditLog` existe; falta logging estruturado de aplicação (B2-4).
- **Uploads:** MIME + magic bytes + limite + URL assinada + auditoria + malware (B1-1/2, D3).
- **Backup/restore:** implementar e testar (B1-5).
- **Monitoramento:** métricas/alerta (B3-4).
- **Desempenho:** trigram/FTS + paginação (R-07, R-13).
- **Testes:** ver `PLANO_TESTES_E_CRITERIOS_ACEITE.md` (R-19).
- **Retenção/LGPD:** política + job (B2-5); **não declarar conformidade sem validação jurídica.**
