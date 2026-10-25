#!/usr/bin/env bash
# Backfill da RPI para Desenhos Industriais e Programas de Computador.
#
# Pré-requisitos:
#   - stack no ar (api/peticoes/rpi) e banco já com a carga dos dados abertos;
#   - executar da raiz do repositório (ou via scripts/backfill_rpi_di_software.sh).
#
# Uso:
#   ./scripts/backfill_rpi_di_software.sh
#
# As figuras de DI NÃO vêm do XML semanal da RPI: o XML só traz
# <complemento-figura-rosto/> e o INPI não serve as imagens individuais.
# Para figuras, use os bundles oficiais DI_FIGURAS_*.ZIP com
# `python -m ingestion.figuras`.
#
# O script para o worker `rpi` durante a carga e o religa no final. Se for
# interrompido, os ZIPs e os metadados já gravados são reaproveitados.

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
  echo "AVISO: figuras de DI NÃO são servidas pelo XML da RPI."
  echo "O pipeline de RPI não encontra as imagens (os endpoints retornam 404)."
  echo "Use os bundles oficiais DI_FIGURAS_*.ZIP com:"
  echo "  python -m ingestion.figuras --dry-run"
  echo "  python -m ingestion.figuras"
  echo "Ignorando BAIXAR_IMAGENS=1 nesta execução."
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
