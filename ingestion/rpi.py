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
        if not nome_escritorio and section in {"desenho_industrial", "software"}:
            # Essas seções não informam o ZIP de texto no JSON do portal.
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
    nome = edition.nome_arquivo_escritorio
    if not nome and section in {"desenho_industrial", "software"}:
        nome = _nome_arquivo_padrao(section, edition.numero)
    if not nome:
        raise ValueError(
            f"RPI {edition.numero} ({section}) sem arquivo de texto"
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


def _last_despacho(processo) -> tuple[str | None, str | None]:
    for despacho in reversed(processo.despachos):
        if despacho.codigo:
            return despacho.codigo, despacho.nome
    return None, None


def _pessoa_row(pessoa, index: int) -> dict:
    return {
        "nome": pessoa.nome,
        "ordem": pessoa.ordem or str(index),
        "pais": pessoa.pais,
        "estado": pessoa.estado,
        "cpf_cnpj": pessoa.cpf_cnpj,
        "tipo_pessoa": pessoa.tipo_pessoa,
    }


def desenhos_payloads(
    processos: Iterable[ProcessoDesenho],
    digitos: dict[str, tuple[str, str]],
    *,
    data_rpi: date | None = None,
) -> tuple[list[dict], dict[str, list[str]]]:
    """Monta os dados bibliográficos/filhos de DI e o mapa para as imagens.

    Devolve ``(payloads, codigos_por_numero)``. Só entram processos casados com
    o dump (a RPI não publica o ``codigo_interno``); os demais continuam
    disponíveis para as referências de imagem, mas não geram linha no banco.
    """
    payloads: list[dict] = []
    codigos: dict[str, list[str]] = {}
    for proc in processos:
        match = digitos.get(process_key(proc.numero))
        if not match:
            continue
        codigo_interno, numero_inpi = match
        codigo_situacao, descricao_situacao = _last_despacho(proc)
        payloads.append(
            {
                "codigo_interno": codigo_interno,
                "numero_inpi": numero_inpi,
                "data_deposito": proc.data_deposito,
                "data_concessao": proc.data_concessao,
                "data_publicacao": proc.data_publicacao or data_rpi,
                "titulo": proc.titulo,
                "codigo_situacao": codigo_situacao,
                "descricao_situacao": descricao_situacao,
                "titulares": [
                    _pessoa_row(p, i) for i, p in enumerate(proc.titulares, 1)
                ],
                "autores": [
                    _pessoa_row(p, i) for i, p in enumerate(proc.autores, 1)
                ],
                "procuradores": [
                    _pessoa_row(p, i) for i, p in enumerate(proc.procuradores, 1)
                ],
                "classificacoes": [
                    {"ordem": str(i), "classificacao_locarno": value}
                    for i, value in enumerate(proc.classificacoes, 1)
                ],
                "prioridades": [
                    {
                        "pais_prioridade": p.pais,
                        "numero_prioridade": p.numero,
                        "data_prioridade": p.data,
                    }
                    for p in proc.prioridades
                ],
                "vinculos": [
                    {
                        "codigo_interno_derivado": (
                            digitos.get(process_key(v.numero)) or (None, None)
                        )[0],
                        "numero_inpi_derivado": (
                            digitos.get(process_key(v.numero)) or (None, None)
                        )[1]
                        or v.numero,
                        "data_vinculo": v.data,
                        "tipo_vinculo": v.tipo,
                    }
                    for v in proc.vinculos
                ],
            }
        )
        codigos[proc.numero] = [codigo_interno]
    return payloads, codigos


def desenhos_rows(
    processos: Iterable[ProcessoDesenho],
    digitos: dict[str, tuple[str, str]],
) -> list[dict]:
    """Expande os processos de DI em linhas de ``desenhos_despachos``."""
    rows: list[dict] = []
    for proc in processos:
        match = digitos.get(process_key(proc.numero))
        if not match:
            continue
        codigo_interno, numero_inpi = match
        for despacho in proc.despachos:
            rows.append(
                {
                    "codigo_interno": codigo_interno,
                    "numero_inpi": numero_inpi,
                    "codigo_despacho": despacho.codigo,
                    "descricao_despacho": despacho.nome,
                    "complemento_despacho": despacho.complemento,
                }
            )
    return rows


def softwares_payloads(
    processos: Iterable[ProcessoSoftware],
    digitos: dict[str, tuple[str, str]],
    *,
    data_rpi: date | None = None,
) -> tuple[list[dict], dict[str, list[str]]]:
    """Monta os dados bibliográficos/filhos de Programas de Computador."""
    payloads: list[dict] = []
    codigos: dict[str, list[str]] = {}
    for proc in processos:
        match = digitos.get(process_key(proc.numero))
        if not match:
            continue
        codigo_interno, numero_inpi = match
        codigo_situacao, descricao_situacao = _last_despacho(proc)
        tipos = [{"tipo": value, "campo_aplicacao": None} for value in proc.tipos_programa]
        tipos += [
            {"tipo": None, "campo_aplicacao": value}
            for value in proc.campos_aplicacao
        ]
        campos = [
            {"campo": "Campo de aplicação", "valor": value}
            for value in proc.campos_aplicacao
        ]
        campos += [
            {"campo": "Tipo de programa", "valor": value}
            for value in proc.tipos_programa
        ]
        payloads.append(
            {
                "codigo_interno": codigo_interno,
                "numero_inpi": numero_inpi,
                "data_criacao": proc.data_criacao,
                "data_publicacao": proc.data_publicacao or data_rpi,
                "titulo": proc.titulo,
                "codigo_situacao": codigo_situacao,
                "descricao_situacao": descricao_situacao,
                "titulares": [
                    _pessoa_row(p, i) for i, p in enumerate(proc.titulares, 1)
                ],
                "autores": [
                    _pessoa_row(p, i) for i, p in enumerate(proc.autores, 1)
                ],
                "linguagens": list(proc.linguagens),
                "tipos": tipos,
                "campos": campos,
            }
        )
        codigos[proc.numero] = [codigo_interno]
    return payloads, codigos


def softwares_rows(
    processos: Iterable[ProcessoSoftware],
    digitos: dict[str, tuple[str, str]],
) -> list[dict]:
    """Expande os processos de software em linhas de ``softwares_despachos``."""
    rows: list[dict] = []
    for proc in processos:
        match = digitos.get(process_key(proc.numero))
        if not match:
            continue
        codigo_interno, numero_inpi = match
        for despacho in proc.despachos:
            rows.append(
                {
                    "codigo_interno": codigo_interno,
                    "numero_inpi": numero_inpi,
                    "codigo_despacho": despacho.codigo,
                    "descricao_despacho": despacho.nome,
                    "complemento_despacho": despacho.complemento,
                }
            )
    return rows


_DESPACHO_INSERTERS = {
    "marcas": db.insert_marcas_despachos,
    "patentes": db.insert_patentes_despachos,
    "desenho_industrial": db.insert_desenhos_despachos,
    "software": db.insert_softwares_despachos,
}


def _insert_in_chunks(
    section: str, *, numero_rpi: str, data_rpi: date | None, rows: list[dict]
) -> int:
    insert = _DESPACHO_INSERTERS[normalize_section(section)]
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
    if edition.nome_arquivo_escritorio:
        nome_padrao = edition.nome_arquivo_escritorio
    elif edition.section in {"desenho_industrial", "software"}:
        nome_padrao = _nome_arquivo_padrao(edition.section, edition.numero)
    else:
        nome_padrao = None
    file_name = nome_padrao or existing.get("file_name")
    file_size = raw_path.stat().st_size if has_raw else existing.get("file_size")
    sha256 = _sha256(raw_path) if has_raw else existing.get("sha256")
    raw_path_value = str(raw_path) if raw_path else existing.get("raw_path")
    source_url = (
        f"{CONFIG.rpi_base_url}/txt/{nome_padrao}"
        if nome_padrao
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

    Suporta Marcas, Patentes, Desenhos Industriais e Programas de Computador.
    Para Marcas e Desenhos, após gravar os despachos, dispara o pipeline
    assíncrono de imagens (:mod:`ingestion.rpi_images`). Falhas de imagem
    **não** invalidam a edição: os despachos já estão persistidos e as imagens
    ficam como ``PENDING``/``ERROR`` para retry em
    ``python -m ingestion.rpi_images --pendentes --secao ...``.
    """
    edition.section = normalize_section(edition.section)
    section = edition.section
    state = _section_state(edition.numero, section)
    if state.get("status") == PROCESSED and not force:
        logger.info(
            "RPI %s (%s): já processada (%s despachos) — pulando.",
            edition.numero,
            section,
            state.get("despachos"),
        )
        # Mesmo com a edição concluída, imagens que ficaram ERROR/PENDING numa
        # rodada anterior precisam de nova tentativa (o laço do compose chama
        # o worker de novo a cada 6 h; sem isso elas nunca seriam retomadas).
        if section in {"marcas", "desenho_industrial"} and baixar_imagens:
            try:
                pendentes = run_pending(
                    numero_rpi=edition.numero,
                    section=section,
                    **(image_options or {}),
                )
            except Exception as exc:  # noqa: BLE001 - não invalida a edição
                logger.exception(
                    "RPI %s (%s): falha ao retomar imagens pendentes",
                    edition.numero,
                    section,
                )
                logger.debug("Detalhe: %s", exc)
            else:
                if pendentes.get("pendentes"):
                    logger.info(
                        "RPI %s (%s): imagens pendentes ok=%s sem_imagem=%s "
                        "erro=%s (de %s).",
                        edition.numero,
                        section,
                        pendentes.get("OK", 0),
                        pendentes.get("SEM_IMAGEM", 0),
                        pendentes.get("ERROR", 0),
                        pendentes["pendentes"],
                    )
        return {"status": "SKIPPED"}

    logger.info("RPI %s (%s): processando...", edition.numero, section)
    _save_state(edition, status=PROCESSING, state={"status": PROCESSING})

    try:
        raw_path = download_edition(session, edition)
    except Exception as exc:  # noqa: BLE001 - erro de rede/portal vira FAILED
        logger.error(
            "RPI %s (%s): falha no download: %s", edition.numero, section, exc
        )
        _save_state(
            edition,
            status=FAILED,
            state={"status": FAILED, "erro": str(exc)[:500]},
            row_status="FAILED",
        )
        return {"status": FAILED, "erro": str(exc)}

    def _parse_again():
        """Lê o ZIP; se estiver corrompido, rebaixa uma vez antes de desistir."""
        nonlocal raw_path
        try:
            return _read_for_section(section, raw_path, edition.numero)
        except (zipfile.BadZipFile, ValueError):
            logger.warning(
                "RPI %s (%s): ZIP inválido em %s — baixando novamente.",
                edition.numero,
                section,
                raw_path,
            )
            raw_path.unlink(missing_ok=True)
            raw_path = download_edition(session, edition, force=True)
            try:
                return _read_for_section(section, raw_path, edition.numero)
            except (zipfile.BadZipFile, ValueError):
                # Não deixa o arquivo ruim "resolvido" para a próxima rodada.
                raw_path.unlink(missing_ok=True)
                raise

    try:
        revista = None
        payloads: list[dict] = []
        base_stats: dict[str, int] = {}
        if section == "patentes":
            with zipfile.ZipFile(raw_path) as zf:
                prefer = f"P{edition.numero}.txt"
                with zf.open(_first_member(zf, ".txt", prefer=prefer)) as raw:
                    with io.TextIOWrapper(raw, encoding="latin-1", errors="replace") as fh:
                        registros = parse_patentes_txt(fh)
            digitos = db.patentes_digitos_map()
            rows = patentes_rows(registros, digitos)
            total_processos = len(registros)
            casados = len(rows)
        else:
            revista = _parse_again()
            if revista.parse_error:
                # XML truncado: não grava um delta incompleto como PROCESSED.
                # Remove o ZIP para que a próxima rodada tente baixar de novo
                # (o download normal pularia um arquivo já existente).
                raw_path.unlink(missing_ok=True)
                raise ValueError(
                    f"XML truncado/corrompido: {revista.parse_error}"
                )
            total_processos = len(revista.processos)
            if section == "marcas":
                codigos = db.marcas_codigos_por_numero(
                    [p.numero for p in revista.processos]
                )
                rows = marcas_rows(revista.processos, codigos)
                casados = len(
                    {p.numero for p in revista.processos if codigos.get(p.numero)}
                )
            elif section == "desenho_industrial":
                digitos = db.desenhos_digitos_map()
                payloads, codigos = desenhos_payloads(
                    revista.processos,
                    digitos,
                    data_rpi=revista.data or edition.data,
                )
                rows = desenhos_rows(revista.processos, digitos)
                casados = len(payloads)
            else:  # software
                digitos = db.softwares_digitos_map()
                payloads, codigos = softwares_payloads(
                    revista.processos,
                    digitos,
                    data_rpi=revista.data or edition.data,
                )
                rows = softwares_rows(revista.processos, digitos)
                casados = len(payloads)
    except Exception as exc:  # noqa: BLE001 - formato inesperado vira FAILED
        logger.exception(
            "RPI %s (%s): falha ao processar o conteúdo", edition.numero, section
        )
        _save_state(
            edition,
            status=FAILED,
            state={"status": FAILED, "erro": f"parse: {exc}"[:500]},
            raw_path=raw_path,
            row_status="FAILED",
        )
        return {"status": FAILED, "erro": str(exc)}

    # Atualiza os dados bibliográficos antes dos despachos: o upsert da base
    # também leva a situação mais recente para a ficha do processo.
    if section == "desenho_industrial":
        base_stats = db.upsert_desenhos_rpi(payloads)
    elif section == "software":
        base_stats = db.upsert_softwares_rpi(payloads)

    inserted = _insert_in_chunks(
        section,
        numero_rpi=edition.numero,
        data_rpi=edition.data,
        rows=rows,
    )

    imagens: dict[str, object] = {}
    if (
        section in {"marcas", "desenho_industrial"}
        and baixar_imagens
        and revista is not None
        and revista.processos
    ):
        try:
            if section == "desenho_industrial":
                imagens = download_for_desenho_edition(
                    numero_rpi=edition.numero,
                    processos=revista.processos,
                    codigos=codigos,
                    data_rpi=edition.data,
                    **(image_options or {}),
                )
            else:
                imagens = download_for_edition(
                    numero_rpi=edition.numero,
                    processos=revista.processos,
                    codigos=codigos,
                    data_rpi=edition.data,
                    **(image_options or {}),
                )
        except Exception as exc:  # noqa: BLE001 - imagens nunca invalidam o delta
            logger.exception(
                "RPI %s (%s): falha no pipeline de imagens", edition.numero, section
            )
            imagens = {"erro": str(exc)[:500]}

    stats = {
        "status": PROCESSED,
        "processos": total_processos,
        "casados": casados,
        "despachos": len(rows),
        "despachos_novos": inserted,
        "arquivo": raw_path.name,
    }
    if base_stats:
        stats["base"] = base_stats
    if imagens:
        stats["imagens"] = imagens
    _save_state(
        edition, status=PROCESSED, state=stats, raw_path=raw_path, row_status="PROCESSED"
    )
    logger.info(
        "RPI %s (%s): %d processo(s), %d casado(s), %d linha(s), %d nova(s).",
        edition.numero,
        section,
        total_processos,
        casados,
        len(rows),
        inserted,
    )
    if imagens:
        logger.info(
            "RPI %s (%s): imagens ok=%s sem_imagem=%s erro=%s.",
            edition.numero,
            section,
            imagens.get("OK", 0),
            imagens.get("SEM_IMAGEM", 0),
            imagens.get("ERROR", 0),
        )
    return stats


def _read_for_section(section: str, path: Path, numero: str):
    """Despacha a leitura do ZIP conforme a seção."""
    if section == "marcas":
        return _read_marcas_zip(path, numero)
    if section == "desenho_industrial":
        return _read_desenho_zip(path, numero)
    if section == "software":
        return _read_software_zip(path, numero)
    raise ValueError(f"seção sem leitor de ZIP: {section}")


def sync(
    sections: list[str],
    *,
    ultimas: int = 1,
    dias: int = 30,
    force: bool = False,
    baixar_imagens: bool = True,
    image_options: dict | None = None,
    rpi_inicio: str | None = None,
    rpi_fim: str | None = None,
) -> dict[str, dict]:
    """Processa as ``ultimas`` edições de cada seção; devolve o resumo por edição.

    Com ``rpi_inicio``/``rpi_fim`` (números de edição, inclusivos) faz backfill
    do intervalo em ordem **crescente** — importante para que a situação
    (``codigo_situacao``) termine no despacho mais recente. Nesse modo a janela
    de descoberta é ampliada para localizar edições antigas.
    """
    session = build_session()
    results: dict[str, dict] = {}
    backfill = bool(rpi_inicio or rpi_fim)
    janela = max(dias, 7300) if backfill else dias
    inicio = int(rpi_inicio) if rpi_inicio else None
    fim = int(rpi_fim) if rpi_fim else None

    for section in sections:
        section = normalize_section(section)
        try:
            editions = discover(session, section, dias=janela)
        except requests.RequestException as exc:
            logger.error("Seção %s: falha na descoberta: %s", section, exc)
            results[f"{section}:?"] = {"status": FAILED, "erro": str(exc)}
            continue

        if backfill:
            selecionadas = []
            for edition in editions:
                try:
                    numero = int(edition.numero)
                except (TypeError, ValueError):
                    continue
                if inicio is not None and numero < inicio:
                    continue
                if fim is not None and numero > fim:
                    continue
                selecionadas.append(edition)
            editions = sorted(selecionadas, key=lambda e: int(e.numero))
        else:
            editions = editions[: max(1, ultimas)]

        if not editions:
            logger.warning(
                "Seção %s: nenhuma edição encontrada%s.",
                section,
                (
                    f" no intervalo {rpi_inicio or '...'}–{rpi_fim or '...'}"
                    if backfill
                    else f" nos últimos {dias} dias"
                ),
            )
            continue

        for edition in editions:
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
        description=(
            "Atualiza os despachos da RPI (semanal) para marcas, patentes, "
            "desenhos industriais e programas de computador."
        )
    )
    parser.add_argument(
        "--secao",
        action="append",
        dest="sections",
        type=normalize_section,
        metavar="{marcas,patentes,desenho_industrial,software}",
        help=(
            "Seção a atualizar. Aceita aliases (di, desenhos, pc, "
            "programa_computador). Repetível. Padrão: marcas e patentes."
        ),
    )
    parser.add_argument(
        "--ultimas",
        type=int,
        default=1,
        help="Quantas edições recentes processar por seção (backfill). Padrão: 1.",
    )
    parser.add_argument(
        "--rpi-inicio",
        type=int,
        metavar="NUMERO",
        help=(
            "Primeira edição do backfill (inclusive). Processa o intervalo em "
            "ordem crescente; use junto com --rpi-fim."
        ),
    )
    parser.add_argument(
        "--rpi-fim",
        type=int,
        metavar="NUMERO",
        help="Última edição do backfill (inclusive). Padrão: a mais recente.",
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
        help=(
            "Não baixa logotipos de Marcas nem figuras de Desenhos "
            "Industriais referenciados pelo XML."
        ),
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

    sections = args.sections or ["marcas", "patentes"]
    results = sync(
        sections,
        ultimas=args.ultimas,
        dias=args.dias,
        force=args.force,
        baixar_imagens=not args.sem_imagens,
        image_options=image_options or None,
        rpi_inicio=args.rpi_inicio,
        rpi_fim=args.rpi_fim,
    )
    for key in sorted(results):
        print(f"{key}  {results[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
