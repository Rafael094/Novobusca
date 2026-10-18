"""Atualização semanal de **marcas e patentes** a partir da RPI do INPI.

A RPI (Revista da Propriedade Industrial) sai toda **terça-feira** e traz, por
seção, as publicações daquela semana — os *despachos* (deferimento,
indeferimento, concessão, arquivamento, exigências, ...). Os CSVs de dados
abertos são *snapshots* periódicos: reprocessá-los toda semana significaria
baixar ~11 GB e recarregar as tabelas inteiras. Este worker faz só o **delta
semanal**, direto na fonte oficial das revistas.

Fluxo (por seção):

1. **descobre** a edição mais recente via JSON —
   ``GET {base}/rpi/busca/data?revista.tipoRevista.id=<id>``;
2. **baixa** o ZIP de texto — ``GET {base}/txt/<nomeArquivoEscritorio>`` — e o
   guarda em ``data/raw/rpi`` (resume/auditoria);
3. **parseia** (:mod:`ingestion.rpi_parse`): XML para Marcas, TXT INID para
   Patentes;
4. **casa** o número do processo com o ``codigo_interno`` que já temos
   (``marcas``/``patentes``) — o que não está no banco é ignorado (entra pelo
   dump mensal);
5. **grava** os despachos novos em ``marcas_despachos``/``patentes_despachos``
   (idempotente por anti-join) e registra o estado em ``inpi_rpi``.

A idempotência vem em duas camadas: a edição já ``PROCESSED`` é pulada (nada é
baixado de novo) e o ``INSERT`` ignora despachos já presentes — então rodar de
novo no mesmo dia não duplica nada.

Uso (da raiz do monorepo, com o python do venv do backend)::

    python -m ingestion.rpi --diagnostico
    python -m ingestion.rpi                       # últimas edições de marcas+patentes
    python -m ingestion.rpi --secao marcas --ultimas 4
    python -m ingestion.rpi --secao patentes --force
"""

from __future__ import annotations

import argparse
import hashlib
import io
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from ingestion import db
from ingestion.config import CONFIG
from ingestion.rpi_parse import (
    ProcessoMarcas,
    ProcessoPatente,
    only_digits,
    parse_date_br,
    parse_marcas_xml,
    parse_patentes_txt,
)
from ingestion.util import build_session, ensure_dirs, get_logger

logger = get_logger(__name__)

# ``revista.tipoRevista.id`` do portal (o mesmo mapa que os leitores públicos da
# RPI usam): 3=Desenhos Industriais, 5=Marcas, 6=Patentes, 7=Programas.
SECOES: dict[str, int] = {"marcas": 5, "patentes": 6}

# Estado de cada seção dentro do ``metadata`` de ``inpi_rpi``.
PROCESSING = "PROCESSING"
PROCESSED = "PROCESSED"
FAILED = "FAILED"

# Tamanho do lote do INSERT (uma transação por lote).
_CHUNK = 5000


@dataclass
class Edition:
    """Uma edição de uma seção da RPI, como devolvida pelo JSON do portal."""

    section: str
    numero: str
    data: date | None
    nome_arquivo_escritorio: str | None
    nome_arquivo: str | None = None
    raw: dict = field(default_factory=dict)


# --- Descoberta / download --------------------------------------------------
def _busca_url() -> str:
    return f"{CONFIG.rpi_base_url}/rpi/busca/data"


def check_connectivity() -> tuple[bool, str]:
    """Testa o portal das Revistas (o host volta e meia entra em manutenção)."""
    try:
        session = build_session()
        resp = session.get(
            _busca_url(),
            params=_busca_params(SECOES["marcas"], 7),
            timeout=30,
        )
        if resp.status_code == 200:
            return True, "ok"
        return False, f"HTTP {resp.status_code}"
    except requests.RequestException as exc:
        return False, str(exc)


def _busca_params(section_id: int, dias: int) -> dict[str, str]:
    hoje = datetime.now()
    inicio = (hoje - timedelta(days=dias)).strftime("%d/%m/%Y")
    return {
        "revista.dataInicial": inicio,
        "revista.dataFinal": hoje.strftime("%d/%m/%Y"),
        "revista.tipoRevista.id": str(section_id),
    }


def discover(session: requests.Session, section: str, *, dias: int = 30) -> list[Edition]:
    """Lista as edições recentes de uma seção, da mais nova para a mais antiga."""
    resp = session.get(
        _busca_url(),
        params=_busca_params(SECOES[section], dias),
        timeout=CONFIG.http_timeout_seconds,
    )
    resp.raise_for_status()
    try:
        items = resp.json()
    except ValueError:
        items = []
    if not isinstance(items, list):
        items = []

    editions: list[Edition] = []
    for item in items:
        if not isinstance(item, dict) or item.get("numero") is None:
            continue
        editions.append(
            Edition(
                section=section,
                numero=str(item["numero"]),
                data=parse_date_br(item.get("dataPublicacao")),
                nome_arquivo_escritorio=item.get("nomeArquivoEscritorio"),
                nome_arquivo=item.get("nomeArquivo"),
                raw=item,
            )
        )
    editions.sort(
        key=lambda e: int(e.numero) if e.numero.isdigit() else 0, reverse=True
    )
    return editions


def _download(session: requests.Session, url: str, dest: Path) -> None:
    """Baixa ``url`` para ``dest`` (streaming), pulando se já existe e não é 0 B."""
    if dest.exists() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    with session.get(url, timeout=CONFIG.http_timeout_seconds, stream=True) as resp:
        resp.raise_for_status()
        ensure_dirs(dest.parent)
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    fh.write(chunk)
    tmp.replace(dest)


def download_edition(session: requests.Session, edition: Edition) -> Path:
    """Baixa o ZIP da edição (``/txt/<nomeArquivoEscritorio>``) e devolve o caminho."""
    if not edition.nome_arquivo_escritorio:
        raise ValueError(f"RPI {edition.numero} ({edition.section}) sem arquivo de texto")
    url = f"{CONFIG.rpi_base_url}/txt/{edition.nome_arquivo_escritorio}"
    dest = CONFIG.rpi_dir / edition.nome_arquivo_escritorio
    _download(session, url, dest)
    return dest


def _first_member(zf: zipfile.ZipFile, ext: str) -> str:
    for name in zf.namelist():
        if name.lower().endswith(ext.lower()):
            return name
    raise ValueError(f"{zf.filename}: nenhum arquivo {ext}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


# --- Montagem das linhas ----------------------------------------------------
def marcas_rows(
    processos: Iterable[ProcessoMarcas], codigos: dict[str, list[str]]
) -> list[dict]:
    """Expande os processos do XML em linhas de ``marcas_despachos``."""
    rows: list[dict] = []
    for proc in processos:
        codigos_internos = codigos.get(proc.numero)
        if not codigos_internos:
            continue
        for despacho in proc.despachos:
            for codigo_interno in codigos_internos:
                rows.append(
                    {
                        "codigo_interno": codigo_interno,
                        "numero_inpi": proc.numero,
                        "codigo_despacho": despacho.codigo,
                        "descricao_despacho": despacho.nome,
                        "complemento_despacho": despacho.complemento,
                    }
                )
    return rows


def patentes_rows(
    registros: Iterable[ProcessoPatente], digitos: dict[str, tuple[str, str]]
) -> list[dict]:
    """Expande os registros do TXT em linhas de ``patentes_despachos``."""
    rows: list[dict] = []
    for reg in registros:
        match = digitos.get(only_digits(reg.numero))
        if not match:
            continue
        codigo_interno, numero_inpi = match
        rows.append(
            {
                "codigo_interno": codigo_interno,
                "numero_inpi": numero_inpi,
                "codigo_despacho": reg.despacho_codigo,
                "complemento_despacho": reg.complemento,
            }
        )
    return rows


def _insert_in_chunks(
    section: str, *, numero_rpi: str, data_rpi: date | None, rows: list[dict]
) -> int:
    insert = (
        db.insert_marcas_despachos
        if section == "marcas"
        else db.insert_patentes_despachos
    )
    total = 0
    for start in range(0, len(rows), _CHUNK):
        chunk = rows[start : start + _CHUNK]
        total += insert(numero_rpi=numero_rpi, data_rpi=data_rpi, rows=chunk)
    return total


# --- Estado da edição em inpi_rpi -------------------------------------------
def _section_state(number: str, section: str) -> dict:
    row = db.get_rpi(number)
    if not row:
        return {}
    meta = row.get("metadata") or {}
    return (meta.get("sections") or {}).get(section) or {}


def _save_state(
    edition: Edition,
    *,
    status: str,
    state: dict,
    raw_path: Path | None = None,
    row_status: str = "PROCESSING",
) -> None:
    """Faz merge do estado da seção no ``metadata`` de ``inpi_rpi``."""
    existing = db.get_rpi(edition.numero) or {}
    meta = dict(existing.get("metadata") or {})
    sections = dict(meta.get("sections") or {})
    sections[edition.section] = state
    meta["sections"] = sections

    db.upsert_rpi(
        number=edition.numero,
        edition_date=(
            datetime.combine(edition.data, datetime.min.time(), tzinfo=timezone.utc)
            if edition.data
            else None
        ),
        file_name=edition.nome_arquivo_escritorio,
        file_size=(raw_path.stat().st_size if raw_path and raw_path.exists() else None),
        sha256=(_sha256(raw_path) if raw_path and raw_path.exists() else None),
        source_url=(
            f"{CONFIG.rpi_base_url}/txt/{edition.nome_arquivo_escritorio}"
            if edition.nome_arquivo_escritorio
            else None
        ),
        status=row_status,
        raw_path=(str(raw_path) if raw_path else None),
        meta=meta,
    )


# --- Processamento de uma edição --------------------------------------------
def process_edition(
    session: requests.Session, edition: Edition, *, force: bool = False
) -> dict:
    """Baixa, parseia e grava uma edição; devolve um resumo (stats)."""
    state = _section_state(edition.numero, edition.section)
    if state.get("status") == PROCESSED and not force:
        logger.info(
            "RPI %s (%s): já processada (%s despachos) — pulando.",
            edition.numero,
            edition.section,
            state.get("despachos"),
        )
        return {"status": "SKIPPED"}

    logger.info("RPI %s (%s): processando...", edition.numero, edition.section)
    _save_state(edition, status=PROCESSING, state={"status": PROCESSING})

    try:
        raw_path = download_edition(session, edition)
    except Exception as exc:  # noqa: BLE001 - erro de rede/portal vira FAILED
        logger.error(
            "RPI %s (%s): falha no download: %s", edition.numero, edition.section, exc
        )
        _save_state(
            edition,
            status=FAILED,
            state={"status": FAILED, "erro": str(exc)[:500]},
            row_status="FAILED",
        )
        return {"status": FAILED, "erro": str(exc)}

    try:
        if edition.section == "marcas":
            with zipfile.ZipFile(raw_path) as zf:
                with zf.open(_first_member(zf, ".xml")) as fh:
                    revista = parse_marcas_xml(fh)
            proc_numeros = [p.numero for p in revista.processos]
            codigos = db.marcas_codigos_por_numero(proc_numeros)
            rows = marcas_rows(revista.processos, codigos)
            total_processos = len(revista.processos)
            casados = len(
                {p.numero for p in revista.processos if codigos.get(p.numero)}
            )
        else:
            with zipfile.ZipFile(raw_path) as zf:
                with zf.open(_first_member(zf, ".txt")) as raw:
                    with io.TextIOWrapper(raw, encoding="latin-1", errors="replace") as fh:
                        registros = parse_patentes_txt(fh)
            digitos = db.patentes_digitos_map()
            rows = patentes_rows(registros, digitos)
            total_processos = len(registros)
            casados = len(rows)
    except Exception as exc:  # noqa: BLE001 - formato inesperado vira FAILED
        logger.exception(
            "RPI %s (%s): falha ao processar o conteúdo", edition.numero, edition.section
        )
        _save_state(
            edition,
            status=FAILED,
            state={"status": FAILED, "erro": f"parse: {exc}"[:500]},
            raw_path=raw_path,
            row_status="FAILED",
        )
        return {"status": FAILED, "erro": str(exc)}

    inserted = _insert_in_chunks(
        edition.section,
        numero_rpi=edition.numero,
        data_rpi=edition.data,
        rows=rows,
    )

    stats = {
        "status": PROCESSED,
        "processos": total_processos,
        "casados": casados,
        "despachos": len(rows),
        "despachos_novos": inserted,
        "arquivo": edition.nome_arquivo_escritorio,
    }
    _save_state(
        edition, status=PROCESSED, state=stats, raw_path=raw_path, row_status="PROCESSED"
    )
    logger.info(
        "RPI %s (%s): %d processo(s), %d casado(s), %d linha(s), %d nova(s).",
        edition.numero,
        edition.section,
        total_processos,
        casados,
        len(rows),
        inserted,
    )
    return stats


def sync(
    sections: list[str],
    *,
    ultimas: int = 1,
    dias: int = 30,
    force: bool = False,
) -> dict[str, dict]:
    """Processa as ``ultimas`` edições de cada seção; devolve o resumo por edição."""
    session = build_session()
    results: dict[str, dict] = {}
    for section in sections:
        try:
            editions = discover(session, section, dias=dias)
        except requests.RequestException as exc:
            logger.error("Seção %s: falha na descoberta: %s", section, exc)
            results[f"{section}:?"] = {"status": FAILED, "erro": str(exc)}
            continue
        if not editions:
            logger.warning(
                "Seção %s: nenhuma edição encontrada nos últimos %d dias.", section, dias
            )
            continue
        for edition in editions[: max(1, ultimas)]:
            results[f"{section}:{edition.numero}"] = process_edition(
                session, edition, force=force
            )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Atualiza os despachos de marcas e patentes a partir da RPI (semanal)."
    )
    parser.add_argument(
        "--secao",
        action="append",
        dest="sections",
        choices=sorted(SECOES),
        help="Seção a atualizar (marcas/patentes). Repetível. Padrão: as duas.",
    )
    parser.add_argument(
        "--ultimas",
        type=int,
        default=1,
        help="Quantas edições recentes processar por seção (backfill). Padrão: 1.",
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=30,
        help="Janela de busca das edições (dias). Padrão: 30.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocessa edições mesmo já marcadas como PROCESSED.",
    )
    parser.add_argument(
        "--diagnostico",
        action="store_true",
        help="Só testa a conectividade com o portal das Revistas e sai.",
    )
    args = parser.parse_args(argv)

    if args.diagnostico:
        ok, detail = check_connectivity()
        print(f"rpi_base_url  {CONFIG.rpi_base_url}")
        print(f"conectividade {'OK' if ok else 'FALHOU'}: {detail}")
        return 0 if ok else 2

    ok, detail = check_connectivity()
    if not ok:
        logger.error("Portal das Revistas inacessível (%s). Nada a fazer agora.", detail)
        return 1

    sections = args.sections or list(SECOES)
    results = sync(sections, ultimas=args.ultimas, dias=args.dias, force=args.force)
    for key in sorted(results):
        print(f"{key}  {results[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
