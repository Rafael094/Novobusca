# Pendências de Infraestrutura e Observabilidade — F0

**Data:** 2026-10-09 · **Fase:** F0 · **Natureza:** Registro objetivo de bloqueios externos.
**Regra:** nada aqui é declarado "ativo/provisionado". São itens que dependem de decisão (**S1**) ou acesso.

---

## 1. O que já pode rodar independentemente do provedor

| Item | Status | Evidência |
|---|---|---|
| Backend FastAPI (uvicorn) | Executável localmente | `app.main:app`; 109 testes verdes |
| PostgreSQL local dedicado | Executável localmente | `intelliinpi_app` (dev), `intelliinpi_test` (testes) |
| Migrações Alembic | Executáveis localmente | 6 revisões presentes |
| Configuração por ambiente | **Implementado em F0** | `ENVIRONMENT` + recusa de segredos default |
| Logging estruturado JSON + request-id | **Implementado em F0** | `app/logging_config.py`; header `X-Request-ID` |
| Tratamento de erro (500 safe / 409 integridade) | **Implementado em F0** | `app/main.py` |
| Scripts de backup/restore | **Criados (sintaxe validada)** | `backend/scripts/*.ps1` |
| Health check | Existente | `GET /api/health` |

## 2. Itens que dependem da decisão S1 (ambiente-alvo)

| # | Pendência | Por que depende de S1 |
|---|---|---|
| I-1 | Destino e retenção dos dumps | Depende de storage/object storage e política |
| I-2 | Execução do teste de restore em ambiente isolado | Requer instância separada provisionada |
| I-3 | Backup/restore do bucket de documentos | Depende de D2 (não decidido) |
| I-4 | Coleta de logs centralizada | Depende do provedor (CloudWatch/Log Analytics/ELK/...) |
| I-5 | Métricas e alertas (5xx, `FAILED`, backup falho) | Depende do provedor de observabilidade |
| I-6 | TLS/terminação, domínio, DNS | Depende do alvo |
| I-7 | Rate limiting com store compartilhado (Redis/Valkey) | Necessário só ao escalar horizontalmente |
| I-8 | Segredos em cofre (Vault/Secrets Manager) | Depende do provedor |
| I-9 | MFA para perfis sensíveis | Requer provedor/segredo de TOTP |
| I-10 | Execução de sync INPI fora do worker da API | Requer worker/fila no alvo |

## 3. Informações de infraestrutura que faltam (checklist para o product owner)

Responder objetivamente:

1. **Onde** rodará o primeiro piloto: nuvem (qual provedor/região), on-premise ou híbrido? (**S1**)
2. Há PostgreSQL gerenciado ou será instância própria? Versão e política de backup do provedor?
3. Onde ficarão os dumps (bucket privado? qual? criptografia? retenção?)?
4. Haverá object storage S3-compatível/MinIO para documentos? (**D2**)
5. Há domínio/DNS e certificado TLS definidos para o piloto?
6. Há restrição institucional (rede, firewall, homologação) para expor a API?
7. Quem operará backup/restore e qual o RPO/RTO aceitos?
8. Há exigência de SSO institucional no piloto?

## 4. Observabilidade — o que foi preparado vs. pendente

- **Preparado (F0):** logs JSON com `request_id` (correlação), log de exceção interna com stack trace, `X-Request-ID` ecoado.
- **Pendente:** envio dos logs a destino externo, definição de métricas, alertas e dashboards.
- **Não declarar monitoramento "ativo"** antes de I-4/I-5 implementados e validados.

## 5. Ferramentas verificadas neste ambiente

- `pg_dump` / `pg_restore`: **NÃO** encontrados no PATH desta máquina → execução real de backup/restore local **bloqueada** por ausência de cliente PostgreSQL.
- Nenhum provedor de nuvem foi presumido (sem evidência de AWS/Azure/Render/Vercel/MinIO).
