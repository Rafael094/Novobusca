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
import time
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from ingestion import db
from ingestion.config import CONFIG
from ingestion.rpi_images import (
    SECTION_DESENHO,
    download_for_desenho_edition,
    download_for_edition,
    run_pending,
)
from ingestion.rpi_parse import (
    ProcessoDesenho,
    ProcessoMarcas,
    ProcessoPatente,
    ProcessoSoftware,
    Revista,
    RevistaDesenho,
    RevistaSoftware,
    only_digits,
    parse_date_br,
    parse_desenho_industrial_xml,
    parse_marcas_xml,
    parse_patentes_txt,
    parse_programa_computador_xml,
    process_key,
)
from ingestion.util import build_session, ensure_dirs, get_logger

logger = get_logger(__name__)

# ``revista.tipoRevista.id`` do portal (o mesmo mapa que os leitores públicos da
# RPI usam): 3=Desenhos Industriais, 5=Marcas, 6=Patentes, 7=Programas.
SECOES: dict[str, int] = {
    "marcas": 5,
    "patentes": 6,
    "desenho_industrial": 3,
    "software": 7,
}

# Aceita os nomes usados no dia a dia e as categorias do dump de dados abertos.
SECAO_ALIASES: dict[str, str] = {
    "desenhos": "desenho_industrial",
    "desenhos_industriais": "desenho_industrial",
    "di": "desenho_industrial",
    "programa_computador": "software",
    "programas_de_computador": "software",
    "programas": "software",
    "pc": "software",
}

# Nome do ZIP de texto quando o JSON do portal não traz ``nomeArquivoEscritorio``
# (é o caso da seção de Desenhos, que só informa o PDF).
_ARQUIVO_PADRAO = {
    "marcas": "RM{numero}.zip",
    "patentes": "P{numero}.zip",
    "desenho_industrial": "DI{numero}.zip",
    "software": "PC{numero}.zip",
}

# Estado de cada seção dentro do ``metadata`` de ``inpi_rpi``.
PROCESSING = "PROCESSING"
PROCESSED = "PROCESSED"
FAILED = "FAILED"

# Tamanho do lote do INSERT (uma transação por lote).
_CHUNK = 5000


def normalize_section(section: str) -> str:
    """Converte aliases (``di``, ``programa_computador``, ...) no nome canônico."""
    value = (section or "").strip().lower().replace("-", "_")
    value = SECAO_ALIASES.get(value, value)
    if value not in SECOES:
        raise ValueError(
            f"seção desconhecida: {section!r} "
            f"(use {', '.join(sorted(SECOES))})"
        )
    return value


def _nome_arquivo_padrao(section: str, numero: str) -> str:
    return _ARQUIVO_PADRAO[section].format(numero=numero)


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
    section = normalize_section(section)
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
        numero = str(item["numero"])
        nome_escritorio = item.get("nomeArquivoEscritorio")
        if not nome_escritorio:
            nome_escritorio = _nome_arquivo_padrao(section, numero)
        editions.append(
            Edition(
                section=section,
                numero=numero,
                data=parse_date_br(item.get("dataPublicacao")),
                nome_arquivo_escritorio=nome_escritorio,
                nome_arquivo=item.get("nomeArquivo"),
                raw=item,
            )
        )
    editions.sort(
        key=lambda e: int(e.numero) if e.numero.isdigit() else 0, reverse=True
    )
    return editions


def _download(
    session: requests.Session,
    url: str,
    dest: Path,
    *,
    force: bool = False,
    attempts: int | None = None,
) -> None:
    """Baixa ``url`` para ``dest`` (streaming) com retry e escrita atômica.

    Pula o download quando o arquivo já existe e não é 0 B (resume/auditoria).
    O portal das Revistas devolve 502/503 com alguma frequência nos dias de
    publicação; sem retry uma indisponibilidade momentânea marcava a edição
    inteira como ``FAILED``. O ``.part`` é removido em caso de falha para nunca
    deixar um ZIP truncado "válido" no destino.
    """
    if not force and dest.exists() and dest.stat().st_size > 0:
        return

    total_attempts = max(1, attempts or (CONFIG.http_retries + 1))
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_error: Exception | None = None

    for attempt in range(1, total_attempts + 1):
        try:
            with session.get(
                url, timeout=CONFIG.http_timeout_seconds, stream=True
            ) as resp:
                resp.raise_for_status()
                ensure_dirs(dest.parent)
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            fh.write(chunk)
            tmp.replace(dest)
            return
        except (requests.RequestException, OSError) as exc:
            last_error = exc
            tmp.unlink(missing_ok=True)
            if attempt >= total_attempts:
                break
            logger.warning(
                "Download de %s falhou (tentativa %d/%d): %s — retentando...",
                url,
                attempt,
                total_attempts,
                exc,
            )
            time.sleep(min(2 ** attempt, 20))

    assert last_error is not None
    raise last_error


def download_edition(
    session: requests.Session, edition: Edition, *, force: bool = False
) -> Path:
    """Baixa o ZIP da edição (``/txt/<nomeArquivoEscritorio>``) e devolve o caminho.

    Algumas seções (notadamente Desenhos Industriais) não informam
    ``nomeArquivoEscritorio`` no JSON; nesses casos usamos o nome histórico
    (``DI<numero>.zip``). O portal às vezes responde a um ZIP inexistente com
    HTTP 200 + página de erro — validamos os magic bytes antes de aceitar o
    arquivo para não parsear HTML como se fosse uma edição.
    """
    section = normalize_section(edition.section)
    nome = edition.nome_arquivo_escritorio or _nome_arquivo_padrao(
        section, edition.numero
    )
    url = f"{CONFIG.rpi_base_url}/txt/{nome}"
    dest = CONFIG.rpi_dir / nome
    if force:
        dest.unlink(missing_ok=True)
    _download(session, url, dest, force=force)
    try:
        with dest.open("rb") as fh:
            assinatura = fh.read(4)
    except OSError as exc:
        raise ValueError(f"{dest.name}: não foi possível ler o download: {exc}") from exc
    if not assinatura.startswith(b"PK"):
        dest.unlink(missing_ok=True)
        raise ValueError(
            f"{dest.name}: o portal não devolveu um ZIP válido "
            f"(assinatura {assinatura!r})"
        )
    return dest


def _first_member(zf: zipfile.ZipFile, ext: str, *, prefer: str | None = None) -> str:
    """Escolhe o membro do ZIP com a extensão pedida.

    Prefere o nome esperado (``RM2910.xml``) e, depois, o maior arquivo — um
    ZIP pode trazer README/arquivos auxiliares com a mesma extensão, e pegar o
    primeiro da lista podia parsear o arquivo errado.
    """
    names = [n for n in zf.namelist() if n.lower().endswith(ext.lower())]
    if not names:
        raise ValueError(f"{zf.filename}: nenhum arquivo {ext}")
    if prefer:
        for name in names:
            if Path(name).name.lower() == prefer.lower():
                return name
    names.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
    return names[0]


def _read_marcas_zip(path: Path, numero: str) -> Revista:
    """Abre o ZIP de Marcas e parseia o XML esperado (``RM<numero>.xml``)."""
    with zipfile.ZipFile(path) as zf:
        prefer = f"RM{numero}.xml"
        with zf.open(_first_member(zf, ".xml", prefer=prefer)) as fh:
            return parse_marcas_xml(fh)


def _read_desenho_zip(path: Path, numero: str) -> RevistaDesenho:
    """Abre o ZIP de Desenhos Industriais e parseia o maior XML da edição."""
    with zipfile.ZipFile(path) as zf:
        prefer = f"DesenhoIndustrial_{numero}.xml"
        with zf.open(_first_member(zf, ".xml", prefer=prefer)) as fh:
            return parse_desenho_industrial_xml(fh)


def _read_software_zip(path: Path, numero: str) -> RevistaSoftware:
    """Abre o ZIP de Programas de Computador e parseia o maior XML da edição."""
    with zipfile.ZipFile(path) as zf:
        prefer = f"Programa_{numero}.xml"
        with zf.open(_first_member(zf, ".xml", prefer=prefer)) as fh:
            return parse_programa_computador_xml(fh)


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
    """Faz merge do estado da seção no ``metadata`` de ``inpi_rpi``.

    Ao gravar estados intermediários (``PROCESSING``) sem ``raw_path``, preserva
    os campos de auditoria já registrados. Sem isso, o upsert zerava
    ``file_size``/``sha256``/``raw_path`` e uma falha posterior apagava a trilha
    do arquivo que já estava em disco.
    """
    existing = db.get_rpi(edition.numero) or {}
    meta = dict(existing.get("metadata") or {})
    sections = dict(meta.get("sections") or {})
    sections[edition.section] = state
    meta["sections"] = sections

    has_raw = raw_path is not None and raw_path.exists()
    file_name = edition.nome_arquivo_escritorio or existing.get("file_name")
    file_size = raw_path.stat().st_size if has_raw else existing.get("file_size")
    sha256 = _sha256(raw_path) if has_raw else existing.get("sha256")
    raw_path_value = str(raw_path) if raw_path else existing.get("raw_path")
    source_url = (
        f"{CONFIG.rpi_base_url}/txt/{edition.nome_arquivo_escritorio}"
        if edition.nome_arquivo_escritorio
        else existing.get("source_url")
    )

    db.upsert_rpi(
        number=edition.numero,
        edition_date=(
            datetime.combine(edition.data, datetime.min.time(), tzinfo=timezone.utc)
            if edition.data
            else existing.get("edition_date")
        ),
        file_name=file_name,
        file_size=file_size,
        sha256=sha256,
        source_url=source_url,
        status=row_status,
        raw_path=raw_path_value,
        meta=meta,
    )


# --- Processamento de uma edição --------------------------------------------
def process_edition(
    session: requests.Session,
    edition: Edition,
    *,
    force: bool = False,
    baixar_imagens: bool = True,
    image_options: dict | None = None,
) -> dict:
    """Baixa, parseia e grava uma edição; devolve um resumo (stats).

    Para Marcas, após gravar os despachos, dispara o pipeline assíncrono de
    imagens (:mod:`ingestion.rpi_images`) dos processos com ``<nome-imagem>``.
    Falhas de imagem **não** invalidam a edição: os despachos já estão
    persistidos e as imagens ficam como ``PENDING``/``ERROR`` para retry em
    ``python -m ingestion.rpi_images --pendentes``.
    """
    state = _section_state(edition.numero, edition.section)
    if state.get("status") == PROCESSED and not force:
        logger.info(
            "RPI %s (%s): já processada (%s despachos) — pulando.",
            edition.numero,
            edition.section,
            state.get("despachos"),
        )
        # Mesmo com a edição concluída, imagens que ficaram ERROR/PENDING numa
        # rodada anterior precisam de nova tentativa (o laço do compose chama
        # o worker de novo a cada 6 h; sem isso elas nunca seriam retomadas).
        if edition.section == "marcas" and baixar_imagens:
            try:
                pendentes = run_pending(
                    numero_rpi=edition.numero, **(image_options or {})
                )
            except Exception as exc:  # noqa: BLE001 - não invalida a edição
                logger.exception(
                    "RPI %s (marcas): falha ao retomar imagens pendentes",
                    edition.numero,
                )
                logger.debug("Detalhe: %s", exc)
            else:
                if pendentes.get("pendentes"):
                    logger.info(
                        "RPI %s (marcas): imagens pendentes ok=%s sem_imagem=%s "
                        "erro=%s (de %s).",
                        edition.numero,
                        pendentes.get("OK", 0),
                        pendentes.get("SEM_IMAGEM", 0),
                        pendentes.get("ERROR", 0),
                        pendentes["pendentes"],
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
            try:
                revista = _read_marcas_zip(raw_path, edition.numero)
            except (zipfile.BadZipFile, ValueError):
                # ZIP truncado/corrompido ou sem o XML esperado (rodada
                # anterior interrompida): descarta e baixa de novo uma única
                # vez antes de desistir.
                logger.warning(
                    "RPI %s (marcas): ZIP inválido em %s — baixando novamente.",
                    edition.numero,
                    raw_path,
                )
                raw_path.unlink(missing_ok=True)
                raw_path = download_edition(session, edition, force=True)
                try:
                    revista = _read_marcas_zip(raw_path, edition.numero)
                except (zipfile.BadZipFile, ValueError):
                    # Não deixa o arquivo ruim "resolvido" para a próxima rodada.
                    raw_path.unlink(missing_ok=True)
                    raise
            if revista.parse_error:
                # XML truncado: não grava um delta incompleto como PROCESSED.
                # Remove o ZIP para que a próxima rodada tente baixar de novo
                # (o download normal pularia um arquivo já existente).
                raw_path.unlink(missing_ok=True)
                raise ValueError(f"XML truncado/corrompido: {revista.parse_error}")
            proc_numeros = [p.numero for p in revista.processos]
            codigos = db.marcas_codigos_por_numero(proc_numeros)
            rows = marcas_rows(revista.processos, codigos)
            total_processos = len(revista.processos)
            casados = len(
                {p.numero for p in revista.processos if codigos.get(p.numero)}
            )
        else:
            with zipfile.ZipFile(raw_path) as zf:
                prefer = f"P{edition.numero}.txt"
                with zf.open(_first_member(zf, ".txt", prefer=prefer)) as raw:
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

    imagens: dict[str, object] = {}
    if edition.section == "marcas" and baixar_imagens and revista.processos:
        try:
            imagens = download_for_edition(
                numero_rpi=edition.numero,
                processos=revista.processos,
                codigos=codigos,
                data_rpi=edition.data,
                **(image_options or {}),
            )
        except Exception as exc:  # noqa: BLE001 - imagens nunca invalidam o delta
            logger.exception(
                "RPI %s (marcas): falha no pipeline de imagens", edition.numero
            )
            imagens = {"erro": str(exc)[:500]}

    stats = {
        "status": PROCESSED,
        "processos": total_processos,
        "casados": casados,
        "despachos": len(rows),
        "despachos_novos": inserted,
        "arquivo": edition.nome_arquivo_escritorio,
    }
    if imagens:
        stats["imagens"] = imagens
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
    if imagens:
        logger.info(
            "RPI %s (marcas): imagens ok=%s sem_imagem=%s erro=%s.",
            edition.numero,
            imagens.get("OK", 0),
            imagens.get("SEM_IMAGEM", 0),
            imagens.get("ERROR", 0),
        )
    return stats


def sync(
    sections: list[str],
    *,
    ultimas: int = 1,
    dias: int = 30,
    force: bool = False,
    baixar_imagens: bool = True,
    image_options: dict | None = None,
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
                session,
                edition,
                force=force,
                baixar_imagens=baixar_imagens,
                image_options=image_options,
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
        "--sem-imagens",
        action="store_true",
        help="Não baixa as imagens/logotipos referenciados pelo XML de Marcas.",
    )
    parser.add_argument(
        "--imagens-concorrencia",
        type=int,
        default=None,
        help="Requisições simultâneas ao baixar imagens (padrão: INPI_RPI_IMAGE_CONCURRENCY).",
    )
    parser.add_argument(
        "--imagens-delay",
        type=float,
        default=None,
        help="Pausa por imagem, em segundos (padrão: INPI_RPI_IMAGE_DELAY).",
    )
    parser.add_argument(
        "--imagens-limite",
        type=int,
        default=None,
        help="Limita quantas imagens baixar nesta rodada (útil para testar).",
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

    image_options: dict[str, object] = {}
    if args.imagens_concorrencia:
        image_options["concurrency"] = args.imagens_concorrencia
    if args.imagens_delay is not None:
        image_options["delay"] = args.imagens_delay
    if args.imagens_limite:
        image_options["limit"] = args.imagens_limite

    sections = args.sections or list(SECOES)
    results = sync(
        sections,
        ultimas=args.ultimas,
        dias=args.dias,
        force=args.force,
        baixar_imagens=not args.sem_imagens,
        image_options=image_options or None,
    )
    for key in sorted(results):
        print(f"{key}  {results[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
