# Runbook — Backup e Restauração (PostgreSQL)

**Data:** 2026-10-09 · **Fase:** F0 · **Natureza:** Procedimento operacional documentado.
**Status:** scripts criados e verificáveis por sintaxe; **execução real de restore pendente de ambiente isolado confirmado** (bloqueio S1/S3).

> Este documento **não declara** que backup/restore está ativo em produção. Ele descreve o procedimento reproduzível; a ativação depende do provisionamento do ambiente-alvo (decisão S1) e de destino protegido para os dumps.

---

## 1. Pré-requisitos

- `pg_dump` / `pg_restore` / `psql` no PATH (cliente PostgreSQL, mesma major version ou superior à do servidor).
- Variável `DATABASE_URL` disponível (ou `PG*` padrão).
- Destino de dump **fora** do servidor de banco, criptografado, com retenção definida.

## 2. RPO / RTO propostos (recomendação provisória — decisão S3)

| Item | Valor proposto | Observação |
|---|---|---|
| Periodicidade | 1 dump completo/dia (off-peak) | Ajustável após decidir S1 |
| Retenção | 7 diários + 4 semanais + 12 mensais | Definir com a instituição |
| RPO | ≤ 24 h | Dump diário |
| RTO | ≤ 4 h | Restore completo em ambiente provisionado |
| Criptografia | Obrigatória (at-rest no destino) | Nunca em bucket público |

## 3. Script de backup

`backend/scripts/backup_db.ps1` (PowerShell) cria um dump custom-format comprimido por padrão. Não contém segredos embutidos: usa `DATABASE_URL` do ambiente.

```powershell
# Exemplo (destino local, apenas para teste):
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/intelliinpi_app"
.\backend\scripts\backup_db.ps1 -OutDir "D:\backups\intelliinpi"
```

O script:
1. Converte o `DATABASE_URL` (driver `+psycopg`) para parâmetros do `pg_dump`.
2. Gera `intelliinpi_YYYYMMDD_HHMMSS.dump` em formato custom (`-Fc`).
3. Nunca exibe a senha; falha com código de saída ≠ 0 se o dump não for criado.

## 4. Script de restauração

`backend/scripts/restore_db.ps1`. **Exige `-Confirm`** e um banco de destino **diferente** do atual; nunca sobrescreve o banco de produção.

```powershell
.\backend\scripts\restore_db.ps1 `
  -DumpFile "D:\backups\intelliinpi\intelliinpi_20260101_030000.dump" `
  -TargetDatabase "intelliinpi_restore_test" -Confirm
```

## 5. Teste de restauração (procedimento, em ambiente isolado)

1. Provisionar uma instância PostgreSQL **isolada** (container/Docker) — nunca a de produção.
2. Restaurar o dump mais recente no banco de destino (`-Confirm`).
3. Validar integridade:
   - contagem de tabelas principais (`tenants`, `users`, `roles`, `permissions`, `marcas`, `patentes`);
   - existência do usuário master admin;
   - integridade referencial amostral (`UserRole` → `Role`/`User`).
4. Registrar data, dump usado, tempo de restore (RTO medido) e divergências.
5. Descartar o ambiente isolado após o teste.

> **Bloqueio:** sem ambiente isolado confirmado e destino protegido aprovado (S1), o passo 5 **não foi executado**. Não declarar backup validado até sua conclusão.

## 6. Restauração de desastre (visão geral)

- Recriar a instância PostgreSQL; criar banco vazio `intelliinpi_app`.
- `pg_restore --clean --if-exists --no-owner -d <url> <dump>` (o script faz isso para um destino explícito).
- Reaplicar variáveis de ambiente/segredos (fora deste documento).
- Subir a API (`uvicorn app.main:app`), conferir `/api/health`.
- Validar login master admin e uma rota de dados.

## 7. Volumes e persistência atuais

- O projeto **não define** volumes de produção neste repositório; a persistência depende do ambiente-alvo (decisão **S1** ainda pendente).
- Banco padrão local: `intelliinpi_app` (ver `config.py`); testes usam `intelliinpi_test` (dedicado).
- Não há bucket de documentos configurado (depende das decisões **D2/D5**).
