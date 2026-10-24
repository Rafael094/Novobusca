#!/usr/bin/env bash
# Backfill da RPI para Desenhos Industriais e Programas de Computador.
#
# Pré-requisitos:
#   - stack no ar (api/peticoes/rpi) e banco já com a carga dos dados abertos;
#   - executar da raiz do repositório (ou via scripts/backfill_rpi_di_software.sh).
#
# Uso:
#   ./scripts/backfill_rpi_di_software.sh
#   BAIXAR_IMAGENS=1 ./scripts/backfill_rpi_di_software.sh
#
# Variáveis opcionais para as figuras:
#   DI_IMG_INICIO=2500 DI_IMG_FIM=2754
#   LIMITE_POR_EDICAO=500 CONCORRENCIA=4 DELAY=0.25
#   LIMITE_PENDENTES=2000
#
# O script para o worker `rpi` durante a carga e o religa no final. Se for
# interrompido, os ZIPs e as linhas de imagem já gravadas são reaproveitados.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.prod.yml)
PSQL=(docker exec inpi-postgres psql -U postgres -d intelliinpi_app -tAc)
LOG_DIR="$ROOT/reports"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/backfill_rpi_di_software_$(date +%Y%m%d_%H%M%S).log"

exec > >(tee -a "$LOG") 2>&1

echo "== Backfill RPI DI/software =="
echo "Início: $(date)"
echo "Log: $LOG"

read_count() {
  "${PSQL[@]}" "SELECT count(*) FROM $1;"
}

desenhos="$(read_count desenhos)"
softwares="$(read_count softwares)"
echo "Base atual: desenhos=$desenhos softwares=$softwares"
if [ "${desenhos:-0}" -eq 0 ] || [ "${softwares:-0}" -eq 0 ]; then
  echo "ERRO: a base de dados abertos está vazia; carregue desenhos/softwares antes." >&2
  exit 1
fi

echo "== Parando o worker e reconstruindo a imagem =="
"${COMPOSE[@]}" stop rpi || true
"${COMPOSE[@]}" build rpi

run_rpi() {
  "${COMPOSE[@]}" run --rm --no-deps rpi "$@"
}

echo "== Smoke test: software 2911 =="
run_rpi python -m ingestion.rpi \
  --secao software --rpi-inicio 2911 --rpi-fim 2911 --force

status="$("${PSQL[@]}" "SELECT coalesce(metadata->'sections'->'software'->>'status','') FROM inpi_rpi WHERE number='2911';" | tr -d '[:space:]')"
casados="$("${PSQL[@]}" "SELECT coalesce(metadata->'sections'->'software'->>'casados','0') FROM inpi_rpi WHERE number='2911';" | tr -d '[:space:]')"
echo "Software 2911: status=$status casados=$casados"
if [ "$status" != "PROCESSED" ] || [ "${casados:-0}" -le 0 ]; then
  echo "ERRO: o smoke test de software falhou; abortando antes do backfill longo." >&2
  exit 1
fi

echo "== Backfill de software: 2500–2911 =="
run_rpi python -m ingestion.rpi \
  --secao software --rpi-inicio 2500 --rpi-fim 2911 --force

echo "== Smoke test: DI 2500 =="
run_rpi python -m ingestion.rpi \
  --secao desenho_industrial --rpi-inicio 2500 --rpi-fim 2500 \
  --sem-imagens --force

status_di="$("${PSQL[@]}" "SELECT coalesce(metadata->'sections'->'desenho_industrial'->>'status','') FROM inpi_rpi WHERE number='2500';" | tr -d '[:space:]')"
casados_di="$("${PSQL[@]}" "SELECT coalesce(metadata->'sections'->'desenho_industrial'->>'casados','0') FROM inpi_rpi WHERE number='2500';" | tr -d '[:space:]')"
echo "DI 2500: status=$status_di casados=$casados_di"
if [ "$status_di" != "PROCESSED" ] || [ "${casados_di:-0}" -le 0 ]; then
  echo "ERRO: o smoke test de DI falhou; abortando antes do backfill longo." >&2
  exit 1
fi

echo "== Backfill de metadados de DI: 2500–2754 (sem imagens) =="
run_rpi python -m ingestion.rpi \
  --secao desenho_industrial --rpi-inicio 2500 --rpi-fim 2754 \
  --sem-imagens --force

if [ "${BAIXAR_IMAGENS:-0}" = "1" ]; then
  echo "== Figuras de DI: ${DI_IMG_FIM:-2754} até ${DI_IMG_INICIO:-2500} =="
  echo "Isso pode levar horas e consumir vários GB; é resumível."
  for n in $(seq "${DI_IMG_FIM:-2754}" -1 "${DI_IMG_INICIO:-2500}"); do
    echo "--- DI $n ---"
    args=(--secao desenho_industrial --rpi "$n")
    if [ -n "${LIMITE_POR_EDICAO:-}" ]; then
      args+=(--limite "$LIMITE_POR_EDICAO")
    fi
    if [ -n "${CONCORRENCIA:-}" ]; then
      args+=(--concorrencia "$CONCORRENCIA")
    fi
    if [ -n "${DELAY:-}" ]; then
      args+=(--delay "$DELAY")
    fi

    if ! run_rpi python -m ingestion.rpi_images "${args[@]}"; then
      echo "AVISO: falha nas figuras de DI $n; continuando." >&2
    fi
  done

  echo "== Retomando figuras pendentes =="
  if [ -n "${LIMITE_PENDENTES:-}" ]; then
    run_rpi python -m ingestion.rpi_images \
      --secao desenho_industrial --pendentes --limite "$LIMITE_PENDENTES" || true
  else
    run_rpi python -m ingestion.rpi_images \
      --secao desenho_industrial --pendentes || true
  fi
fi

echo "== Resumo =="
"${PSQL[@]}" "SELECT 'desenhos=' || count(*) FROM desenhos;" || true
"${PSQL[@]}" "SELECT 'softwares=' || count(*) FROM softwares;" || true
"${PSQL[@]}" "SELECT 'desenhos_despachos=' || count(*) FROM desenhos_despachos;" || true
"${PSQL[@]}" "SELECT 'softwares_despachos=' || count(*) FROM softwares_despachos;" || true
"${PSQL[@]}" "SELECT 'figuras_rpi=' || count(*) FROM desenhos_rpi_figuras;" || true

echo "== Religando o worker =="
"${COMPOSE[@]}" up -d --no-deps rpi
echo "Fim: $(date)"
