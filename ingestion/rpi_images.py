"""Download assíncrono das **imagens/logotipos de marcas** publicados na RPI.

O XML semanal de Marcas (``RM<numero>.zip`` → ``.xml``) referencia a figura de
cada processo em ``<nome-imagem>`` (ex.: ``912345678.jpg``). Esse arquivo **não
vem dentro do ZIP**: ele é servido pelos endpoints públicos do INPI, em ordens
diferentes conforme a idade do processo:

1. **Busca pública (principal)** — ``/marca/imagem/<processo>.jpg``;
2. **Acervo da edição da RPI** — ``/rpi/images/<numero_rpi>/<nome-imagem>``
   (e também ``/rpi/images/<numero_rpi>/<processo>.jpg``);
3. **Fallback histórico com hash de 3 dígitos** —
   ``/marca/imagem/<3 primeiros dígitos>/<processo>.jpg``.

Este módulo:

* monta as referências a partir dos processos já parseados
  (:func:`build_image_refs`);
* baixa em paralelo com ``httpx`` + ``asyncio.Semaphore`` (concorrência
  limitada), ``User-Agent`` de navegador, retry com *backoff* exponencial e
  fallback ordenado entre as URLs;
* valida os bytes por *magic number* (JPEG/PNG/WebP) e rejeita HTML, GIF de
  placeholder e conteúdo desconhecido;
* grava a imagem no mesmo layout do worker do pePI
  (``data/raw/marcas/logos/<2 primeiros caracteres>/<código>.jpg``) e registra
  a procedência em ``marcas_rpi_imagens``; quando o ``codigo_interno`` já é
  conhecido, também atualiza ``marcas_logos`` para a API servir na hora;
* é resumível: linhas ``OK``/``SEM_IMAGEM`` são terminais e ``ERROR`` volta na
  próxima rodada.

Uso (da raiz do monorepo, com o python do venv do backend)::

    python -m ingestion.rpi_images --diagnostico
    python -m ingestion.rpi_images --rpi 2910
    python -m ingestion.rpi_images --rpi 2910 --limite 500 --concorrencia 4
    python -m ingestion.rpi_images --pendentes
    python -m ingestion.rpi_images --rpi 2910 --processo 912345678 --nome-imagem 912345678.jpg

O worker semanal (:mod:`ingestion.rpi`) chama :func:`download_for_edition`
automaticamente depois de gravar os despachos; ``--sem-imagens`` desliga isso.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import random
import re
import zipfile
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
import requests

from ingestion import db
from ingestion.config import CONFIG
from ingestion.rpi_parse import (
    ProcessoDesenho,
    ProcessoMarcas,
    Revista,
    RevistaDesenho,
    normalize_image_name,
    parse_desenho_industrial_xml,
    parse_marcas_xml,
)
from ingestion.util import ensure_dirs, get_logger, human_size

logger = get_logger(__name__)

SECTION_MARCAS = "marcas"
SECTION_DESENHO = "desenho_industrial"

# Statuses persistidos em ``marcas_rpi_imagens``/``desenhos_rpi_figuras`` (e
# espelhados em ``marcas_logos``/``desenhos_figuras`` quando há
# ``codigo_interno``). ``OK``/``SEM_IMAGEM`` são terminais; ``ERROR`` é
# retentável.
OK = "OK"
SEM_IMAGEM = "SEM_IMAGEM"
ERROR = "ERROR"
PENDING = "PENDING"

_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"
_GIF = b"GIF8"
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}

# Códigos HTTP que valem uma nova tentativa na MESMA URL antes de cair para a
# próxima (429/5xx são transitórios; 403 é o bloqueio intermitente do INPI).
_RETRY_STATUS = frozenset({403, 408, 425, 429, 500, 502, 503, 504})


# --- Normalização / URLs -----------------------------------------------------
def _safe_key(value: str | None) -> str:
    """Sanitiza ``codigo_interno``/``numero_processo`` para uso em caminho."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", (value or "").strip())[:64] or "_"


def _only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _file_name(nome_imagem: str | None, numero_processo: str) -> str:
    """Nome do arquivo da figura, sempre com extensão de imagem."""
    name = normalize_image_name(nome_imagem)
    if not name:
        name = f"{_safe_key(numero_processo)}.jpg"
    if Path(name).suffix.lower() not in _IMAGE_EXT:
        name = f"{name}.jpg"
    return name


def image_url_candidates(
    numero_rpi: str | None,
    numero_processo: str,
    nome_imagem: str | None = None,
    *,
    section: str = SECTION_MARCAS,
) -> list[str]:
    """URLs de imagem a tentar, na ordem recomendada (sem duplicatas).

    Para Marcas a ordem é: busca pública → acervo da RPI (nome-imagem e, se
    diferente, número do processo) → fallback com hash de 3 dígitos. Para
    Desenhos Industriais usamos o endpoint público de desenhos e o mesmo acervo
    ``/rpi/images``. Um 404 em uma URL apenas passa para a próxima; erros
    transitórios são retentados antes.
    """
    numero = (numero_processo or "").strip()
    key = _only_digits(numero) or numero
    if not key:
        return []

    arquivo = _file_name(nome_imagem, key)
    edicao = str(numero_rpi).strip() if numero_rpi else ""
    urls: list[str] = []

    def add(url: str) -> None:
        if url and url not in urls:
            urls.append(url)

    if section == SECTION_DESENHO:
        # As figuras de DI usam o acervo público de desenhos. O nome do arquivo
        # nem sempre vem no XML (edições antigas trazem só
        # ``<complemento-figura-rosto/>``); nesse caso usamos o processo.
        base = CONFIG.desenho_images_base_url.rstrip("/")
        revistas = CONFIG.rpi_base_url.rstrip("/")
        add(f"{base}/{quote(key, safe='')}.jpg")
        if edicao:
            add(
                f"{revistas}/rpi/images/{quote(edicao, safe='')}/"
                f"{quote(arquivo, safe='')}"
            )
            add(
                f"{revistas}/rpi/images/{quote(edicao, safe='')}/"
                f"{quote(key, safe='')}.jpg"
            )
        return urls

    base = CONFIG.busca_images_base_url.rstrip("/")
    revistas = CONFIG.rpi_base_url.rstrip("/")

    # 1) Busca pública (endpoint principal).
    add(f"{base}/{quote(key, safe='')}.jpg")
    # 2) Acervo da edição da RPI: primeiro o nome-imagem do XML, depois o
    #    número do processo (edições antigas nem sempre têm nome-imagem).
    if edicao:
        add(f"{revistas}/rpi/images/{quote(edicao, safe='')}/{quote(arquivo, safe='')}")
        add(
            f"{revistas}/rpi/images/{quote(edicao, safe='')}/"
            f"{quote(key, safe='')}.jpg"
        )
    # 3) Fallback histórico: hash de 3 dígitos.
    if len(key) >= 3:
        add(f"{base}/{quote(key[:3], safe='')}/{quote(key, safe='')}.jpg")
    return urls


def sniff_image(data: bytes) -> tuple[str, str | None]:
    """Classifica os bytes: ``image``, ``placeholder``, ``html`` ou ``unknown``."""
    if not data:
        return "unknown", None
    if data[:3] == _JPEG:
        return "image", "image/jpeg"
    if data[:8] == _PNG:
        return "image", "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image", "image/webp"
    if data[:4] == _GIF:
        return "placeholder", "image/gif"
    head = data[:2048].lower()
    if b"<html" in head or b"<!doctype html" in head:
        return "html", "text/html"
    return "unknown", None


# --- Referências -------------------------------------------------------------
@dataclass(frozen=True)
class ImageRef:
    """Uma figura a baixar (processo + eventual ``codigo_interno``)."""

    numero_rpi: str
    numero_processo: str
    nome_imagem: str | None = None
    codigo_interno: str | None = None
    marca_nome: str | None = None
    apresentacao: str | None = None
    data_rpi: date | None = None
    despachos: tuple[str, ...] = ()
    #: ``marcas`` (logotipo) ou ``desenho_industrial`` (figura). O default
    #: preserva o contrato histórico do pipeline de marcas.
    section: str = SECTION_MARCAS


def build_image_refs(
    processos: Iterable[ProcessoMarcas],
    codigos: dict[str, list[str]],
    numero_rpi: str,
    *,
    data_rpi: date | None = None,
) -> list[ImageRef]:
    """Seleciona os processos com figura e expande por ``codigo_interno``.

    Só entram processos cujo ``<nome-imagem>`` foi preenchido — é a marcação
    explícita de que há figura (Mista/Figurativa). Um mesmo processo pode ter
    mais de um ``codigo_interno`` em casos-limite; nesse caso a imagem é
    registrada para cada código.
    """
    refs: list[ImageRef] = []
    seen: set[tuple[str, str | None]] = set()
    for proc in processos:
        nome = normalize_image_name(proc.nome_imagem)
        if not nome:
            continue
        for codigo in codigos.get(proc.numero) or [None]:
            key = (proc.numero, codigo)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                ImageRef(
                    numero_rpi=str(numero_rpi),
                    numero_processo=proc.numero,
                    nome_imagem=nome,
                    codigo_interno=codigo,
                    marca_nome=proc.marca_nome,
                    apresentacao=proc.apresentacao,
                    data_rpi=data_rpi,
                    despachos=tuple(d.codigo for d in proc.despachos),
                )
            )
    return refs


def build_desenho_image_refs(
    processos: Iterable[ProcessoDesenho],
    codigos: dict[str, list[str]],
    numero_rpi: str,
    *,
    data_rpi: date | None = None,
) -> list[ImageRef]:
    """Seleciona desenhos com figura e expande por ``codigo_interno``.

    Diferente do XML de Marcas, o de Desenhos pode sinalizar a figura apenas com
    ``<complemento-figura-rosto/>`` (sem nome de arquivo). Nesse caso a
    referência usa o número do processo e os endpoints públicos tentam resolver
    a imagem.
    """
    refs: list[ImageRef] = []
    seen: set[tuple[str, str | None]] = set()
    for proc in processos:
        if not proc.tem_imagem:
            continue
        nome = normalize_image_name(proc.nome_imagem)
        for codigo in codigos.get(proc.numero) or [None]:
            key = (proc.numero, codigo)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                ImageRef(
                    numero_rpi=str(numero_rpi),
                    numero_processo=proc.numero,
                    nome_imagem=nome,
                    codigo_interno=codigo,
                    data_rpi=data_rpi,
                    despachos=tuple(d.codigo for d in proc.despachos),
                    section=SECTION_DESENHO,
                )
            )
    return refs


# --- Resultado / armazenamento ----------------------------------------------
@dataclass
class ImageResult:
    ref: ImageRef
    status: str
    url: str | None = None
    path: Path | None = None
    mime: str | None = None
    size: int = 0
    sha256: str | None = None
    tentativas: int = 0
    erro: str | None = None
    cache: bool = False


@dataclass(frozen=True)
class _Fetch:
    kind: str  # image | placeholder | html | not_found | error
    data: bytes | None = None
    mime: str | None = None
    url: str | None = None
    status: int | None = None
    attempts: int = 0
    error: str | None = None


def _bucket_dir(key: str, section: str = SECTION_MARCAS) -> Path:
    """Shard pelo dois primeiros caracteres (mesmo layout de ``ingestion.logos``)."""
    safe = _safe_key(key)
    base = CONFIG.desenho_figuras_dir if section == SECTION_DESENHO else CONFIG.logos_dir
    return base / (safe[:2] or "_")


def _destino(ref: ImageRef, mime: str | None) -> Path:
    """Caminho final do arquivo, usando ``codigo_interno`` quando conhecido."""
    key = _safe_key(ref.codigo_interno or ref.numero_processo)
    ext = {"image/png": ".png", "image/webp": ".webp"}.get(mime or "", ".jpg")
    if ext == ".jpg":
        # Mantém a extensão original quando ela é conhecida e compatível.
        original = Path(ref.nome_imagem or "").suffix.lower()
        if original in {".jpeg", ".jpg"}:
            ext = ".jpg"
    return _bucket_dir(key, ref.section) / f"{key}{ext}"


def _rel_arquivo(path: Path) -> str:
    """Caminho relativo ao ``data_dir``, em POSIX (portável Windows/Linux)."""
    try:
        return path.relative_to(CONFIG.data_dir).as_posix()
    except ValueError:
        return str(path)


def _write_atomic(path: Path, data: bytes) -> None:
    ensure_dirs(path.parent)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)


def _resolve_cached_path(
    arquivo: str | None, codigo_interno: str, section: str = SECTION_MARCAS
) -> Path | None:
    """Resolve o caminho gravado em ``marcas_logos``/``desenhos_figuras``."""
    if not arquivo:
        return None
    salvo = Path(arquivo.replace("\\", "/"))
    candidatos: list[Path] = []
    if salvo.is_absolute():
        candidatos.append(salvo)
    else:
        candidatos.append((CONFIG.data_dir / salvo).resolve())
        prefixo = _safe_key(codigo_interno)[:2] or "_"
        base = (
            CONFIG.desenho_figuras_dir
            if section == SECTION_DESENHO
            else CONFIG.logos_dir
        )
        candidatos.append((base / prefixo / salvo.name).resolve())
    for caminho in candidatos:
        if caminho.is_file():
            return caminho
    return None


def _result_from_file(
    ref: ImageRef,
    path: Path,
    *,
    url: str,
    mime: str | None,
    cache: bool,
    sha256: str | None = None,
) -> ImageResult | None:
    """Monta um ``ImageResult`` a partir de um arquivo já em disco."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data:
        return None
    return ImageResult(
        ref=ref,
        status=OK,
        url=url,
        path=path,
        mime=mime or "image/jpeg",
        size=len(data),
        sha256=sha256 or hashlib.sha256(data).hexdigest(),
        cache=cache,
    )


def _cached_result(ref: ImageRef) -> ImageResult | None:
    """Imagem já baixada (cache da seção ou procedência desta edição)."""
    if ref.section == SECTION_DESENHO:
        if ref.codigo_interno:
            try:
                row = db.get_figura(ref.codigo_interno)
            except Exception as exc:  # noqa: BLE001 - cache é otimização
                logger.debug(
                    "Cache de figura indisponível para %s: %s",
                    ref.codigo_interno,
                    exc,
                )
                row = None
            if row and row.get("status") == OK:
                path = _resolve_cached_path(
                    row.get("arquivo"), ref.codigo_interno, SECTION_DESENHO
                )
                if path is not None:
                    result = _result_from_file(
                        ref,
                        path,
                        url="cache",
                        mime=row.get("mime"),
                        cache=True,
                        sha256=row.get("sha256"),
                    )
                    if result is not None:
                        return result

        try:
            prov = db.get_desenho_rpi_figura(
                ref.numero_rpi, ref.numero_processo
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Cache de procedência indisponível para %s/%s: %s",
                ref.numero_rpi,
                ref.numero_processo,
                exc,
            )
            return None
        if not prov or prov.get("status") != OK:
            return None
        path = _resolve_cached_path(
            prov.get("arquivo"),
            ref.codigo_interno or ref.numero_processo,
            SECTION_DESENHO,
        )
        if path is None:
            return None
        return _result_from_file(
            ref,
            path,
            url=str(prov.get("origem_url") or "cache"),
            mime=prov.get("mime"),
            cache=False,
            sha256=prov.get("sha256"),
        )

    if ref.codigo_interno:
        try:
            row = db.get_logo(ref.codigo_interno)
        except Exception as exc:  # noqa: BLE001 - cache é otimização, não requisito
            logger.debug(
                "Cache de logo indisponível para %s: %s", ref.codigo_interno, exc
            )
            row = None
        if row and row.get("status") == OK:
            path = _resolve_cached_path(row.get("arquivo"), ref.codigo_interno)
            if path is not None:
                result = _result_from_file(
                    ref,
                    path,
                    url="cache",
                    mime=row.get("mime"),
                    cache=True,
                    sha256=row.get("sha256"),
                )
                if result is not None:
                    return result

    try:
        prov = db.get_rpi_imagem(ref.numero_rpi, ref.numero_processo)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "Cache de procedência indisponível para %s/%s: %s",
            ref.numero_rpi,
            ref.numero_processo,
            exc,
        )
        return None
    if not prov or prov.get("status") != OK:
        return None
    path = _resolve_cached_path(
        prov.get("arquivo"), ref.codigo_interno or ref.numero_processo
    )
    if path is None:
        return None
    # ``cache=False``: se o código interno passou a ser conhecido, ``_persist``
    # deve espelhar a imagem em ``marcas_logos`` para a API servi-la.
    return _result_from_file(
        ref,
        path,
        url=str(prov.get("origem_url") or "cache"),
        mime=prov.get("mime"),
        cache=False,
        sha256=prov.get("sha256"),
    )


# --- Downloader --------------------------------------------------------------
class RpiImageDownloader:
    """Baixa e persiste figuras da RPI com concorrência limitada e fallback."""

    def __init__(
        self,
        *,
        concurrency: int | None = None,
        delay: float | None = None,
        max_retries: int | None = None,
        timeout: float | None = None,
        force: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.concurrency = max(1, int(concurrency or CONFIG.rpi_image_concurrency))
        self.delay = (
            CONFIG.rpi_image_delay_seconds if delay is None else max(0.0, delay)
        )
        self.max_retries = max(
            0, int(CONFIG.rpi_image_retries if max_retries is None else max_retries)
        )
        self.timeout = float(timeout or CONFIG.rpi_image_timeout_seconds)
        self.force = force
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "RpiImageDownloader":
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=_headers(),
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                verify=CONFIG.verify_ssl,
                limits=httpx.Limits(
                    max_connections=max(4, self.concurrency * 2),
                    max_keepalive_connections=max(2, self.concurrency),
                ),
            )
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _sleep_backoff(self, attempt: int, response: httpx.Response | None) -> None:
        retry_after = 0.0
        if response is not None:
            header = response.headers.get("Retry-After")
            if header:
                try:
                    retry_after = float(header)
                except ValueError:
                    retry_after = 0.0
        backoff = min(30.0, 2.0 ** max(0, attempt - 1))
        await asyncio.sleep(min(30.0, retry_after or (backoff + random.uniform(0, 0.5))))

    async def _get(self, url: str) -> _Fetch:
        """GET de uma URL com retry/backoff; devolve o resultado classificado."""
        assert self._client is not None
        attempt = 0
        last_error: str | None = None
        while True:
            attempt += 1
            try:
                async with self._semaphore:
                    response = await self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt > self.max_retries:
                    return _Fetch(
                        "error",
                        url=url,
                        attempts=attempt,
                        error=last_error,
                    )
                await self._sleep_backoff(attempt, None)
                continue

            status = response.status_code
            if status in (404, 410):
                return _Fetch("not_found", url=url, status=status, attempts=attempt)

            if status == 200:
                data = response.content
                kind, mime = sniff_image(data)
                return _Fetch(
                    kind,
                    data=data,
                    mime=mime,
                    url=url,
                    status=status,
                    attempts=attempt,
                )

            last_error = f"HTTP {status}"
            if status in _RETRY_STATUS and attempt <= self.max_retries:
                await self._sleep_backoff(attempt, response)
                continue
            return _Fetch(
                "error",
                url=url,
                status=status,
                attempts=attempt,
                error=last_error,
            )

    async def process(self, ref: ImageRef) -> ImageResult:
        """Processa uma referência: cache local → URLs em ordem → persistência."""
        if not self.force:
            cached = await asyncio.to_thread(_cached_result, ref)
            if cached is not None:
                await asyncio.to_thread(self._persist, cached)
                return cached

        urls = image_url_candidates(
            ref.numero_rpi,
            ref.numero_processo,
            ref.nome_imagem,
            section=ref.section,
        )
        if not urls:
            result = ImageResult(
                ref, ERROR, tentativas=0, erro="processo sem número/URL de imagem"
            )
            self._persist(result)
            return result

        attempts = 0
        last_error: str | None = None
        saw_placeholder = False
        saw_not_found = False

        for url in urls:
            fetch = await self._get(url)
            attempts += fetch.attempts

            if fetch.kind == "image":
                data = fetch.data or b""
                if not data:
                    last_error = "resposta vazia"
                    continue
                if len(data) > CONFIG.rpi_image_max_bytes:
                    last_error = (
                        f"imagem maior que o limite "
                        f"({human_size(len(data))} > "
                        f"{human_size(CONFIG.rpi_image_max_bytes)})"
                    )
                    continue
                mime = fetch.mime or "image/jpeg"
                dest = _destino(ref, mime)
                try:
                    _write_atomic(dest, data)
                except OSError as exc:
                    last_error = f"falha ao gravar {dest.name}: {exc}"
                    logger.warning(
                        "RPI %s processo %s: %s", ref.numero_rpi, ref.numero_processo, last_error
                    )
                    continue
                result = ImageResult(
                    ref=ref,
                    status=OK,
                    url=url,
                    path=dest,
                    mime=mime,
                    size=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    tentativas=attempts,
                )
                await asyncio.to_thread(self._persist, result)
                return result

            if fetch.kind == "placeholder":
                saw_placeholder = True
                logger.debug(
                    "RPI %s processo %s: placeholder em %s",
                    ref.numero_rpi,
                    ref.numero_processo,
                    url,
                )
            elif fetch.kind == "not_found":
                saw_not_found = True
            else:
                last_error = fetch.error
                if not last_error and fetch.status is not None:
                    last_error = f"HTTP {fetch.status}"
                logger.debug(
                    "RPI %s processo %s: %s em %s",
                    ref.numero_rpi,
                    ref.numero_processo,
                    last_error,
                    url,
                )

        # Placeholder é definitivo ("não há imagem"). 404 em todas as URLs
        # também: não adianta insistir até a próxima edição. Qualquer erro
        # transitório mantém ERROR para o retry do worker.
        if saw_placeholder or (saw_not_found and not last_error):
            status = SEM_IMAGEM
            erro = "sem imagem (placeholder/404 em todas as URLs)"
        else:
            status = ERROR
            erro = last_error or "não foi possível baixar a imagem"

        result = ImageResult(
            ref, status, tentativas=attempts, erro=erro[:1000] if erro else None
        )
        await asyncio.to_thread(self._persist, result)
        return result

    def _persist(self, result: ImageResult) -> None:
        """Grava a procedência e espelha na tabela consumida pela API."""
        ref = result.ref
        arquivo = _rel_arquivo(result.path) if result.path else None
        baixado_em = datetime.now(timezone.utc) if result.status == OK else None

        if ref.section == SECTION_DESENHO:
            self._persist_desenho(result, arquivo, baixado_em)
            return

        try:
            db.upsert_rpi_imagem(
                numero_rpi=ref.numero_rpi,
                numero_processo=ref.numero_processo,
                nome_imagem=ref.nome_imagem,
                codigo_interno=ref.codigo_interno,
                status=result.status,
                arquivo=arquivo,
                mime=result.mime,
                bytes_=result.size or None,
                sha256=result.sha256,
                tentativas=result.tentativas,
                erro=result.erro,
                origem_url=result.url,
                baixado_em=baixado_em,
            )
        except Exception as exc:  # noqa: BLE001 - uma linha falhar não para o lote
            logger.warning(
                "RPI %s processo %s: falha ao registrar procedência: %s",
                ref.numero_rpi,
                ref.numero_processo,
                exc,
            )

        # O cache veio de uma linha ``marcas_logos`` já ``OK``: reescrevê-la só
        # perderia ``tentativas``/``baixado_em`` originais. A procedência acima
        # já registra que a figura desta edição foi confirmada.
        if result.cache or not ref.codigo_interno:
            return

        # Nunca apaga um OK já armazenado por causa de um placeholder/erro.
        if result.status != OK:
            try:
                existing = db.get_logo(ref.codigo_interno)
            except Exception:  # noqa: BLE001
                existing = None
            if existing and existing.get("status") == OK:
                return

        try:
            db.upsert_logo(
                codigo_interno=ref.codigo_interno,
                status=result.status,
                arquivo=arquivo,
                mime=result.mime,
                bytes_=result.size or None,
                sha256=result.sha256,
                tentativas=result.tentativas,
                erro=result.erro,
                baixado_em=baixado_em,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "RPI %s processo %s: falha ao atualizar marcas_logos (%s): %s",
                ref.numero_rpi,
                ref.numero_processo,
                ref.codigo_interno,
                exc,
            )

    def _persist_desenho(
        self,
        result: ImageResult,
        arquivo: str | None,
        baixado_em: datetime | None,
    ) -> None:
        """Grava ``desenhos_rpi_figuras`` e espelha em ``desenhos_figuras``."""
        ref = result.ref
        try:
            db.upsert_desenho_rpi_figura(
                numero_rpi=ref.numero_rpi,
                numero_processo=ref.numero_processo,
                nome_imagem=ref.nome_imagem,
                codigo_interno=ref.codigo_interno,
                status=result.status,
                arquivo=arquivo,
                mime=result.mime,
                bytes_=result.size or None,
                sha256=result.sha256,
                tentativas=result.tentativas,
                erro=result.erro,
                origem_url=result.url,
                baixado_em=baixado_em,
            )
        except Exception as exc:  # noqa: BLE001 - uma linha falhar não para o lote
            logger.warning(
                "RPI %s processo %s: falha ao registrar figura: %s",
                ref.numero_rpi,
                ref.numero_processo,
                exc,
            )

        if result.cache or not ref.codigo_interno:
            return

        if result.status != OK:
            try:
                existing = db.get_figura(ref.codigo_interno)
            except Exception:  # noqa: BLE001
                existing = None
            if existing and existing.get("status") == OK:
                return

        try:
            db.upsert_figura(
                codigo_interno=ref.codigo_interno,
                status=result.status,
                arquivo=arquivo,
                mime=result.mime,
                bytes_=result.size or None,
                sha256=result.sha256,
                tentativas=result.tentativas,
                erro=result.erro,
                baixado_em=baixado_em,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "RPI %s processo %s: falha ao atualizar desenhos_figuras (%s): %s",
                ref.numero_rpi,
                ref.numero_processo,
                ref.codigo_interno,
                exc,
            )


def _headers() -> dict[str, str]:
    """Headers de navegador para reduzir 403/503 do WAF do INPI."""
    return {
        "User-Agent": CONFIG.rpi_image_user_agent,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://busca.inpi.gov.br/",
        "Connection": "keep-alive",
    }


# --- Orquestração ------------------------------------------------------------
async def download_refs(
    refs: Sequence[ImageRef],
    *,
    concurrency: int | None = None,
    delay: float | None = None,
    max_retries: int | None = None,
    timeout: float | None = None,
    force: bool = False,
    client: httpx.AsyncClient | None = None,
) -> dict[str, int]:
    """Processa ``refs`` com um pool de workers e devolve ``status -> total``."""
    refs = list(refs)
    stats = {OK: 0, SEM_IMAGEM: 0, ERROR: 0}
    if not refs:
        return stats

    downloader = RpiImageDownloader(
        concurrency=concurrency,
        delay=delay,
        max_retries=max_retries,
        timeout=timeout,
        force=force,
        client=client,
    )
    total = len(refs)
    queue: asyncio.Queue[ImageRef] = asyncio.Queue()
    for ref in refs:
        queue.put_nowait(ref)

    done = 0
    lock = asyncio.Lock()

    async def worker() -> None:
        nonlocal done
        while True:
            try:
                ref = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                result = await downloader.process(ref)
            except Exception as exc:  # noqa: BLE001 - um item nunca derruba o lote
                logger.exception(
                    "RPI %s processo %s: erro inesperado",
                    ref.numero_rpi,
                    ref.numero_processo,
                )
                result = ImageResult(
                    ref, ERROR, tentativas=0, erro=f"{type(exc).__name__}: {exc}"[:1000]
                )
                try:
                    await asyncio.to_thread(
                        downloader._persist, result  # noqa: SLF001 - mesma unidade
                    )
                except Exception:  # noqa: BLE001
                    pass
            finally:
                queue.task_done()

            async with lock:
                stats[result.status] = stats.get(result.status, 0) + 1
                done += 1
                if done % 200 == 0 or done == total:
                    logger.info(
                        "  imagens RPI %d/%d  ok=%d sem_imagem=%d erro=%d",
                        done,
                        total,
                        stats[OK],
                        stats[SEM_IMAGEM],
                        stats[ERROR],
                    )
            if downloader.delay:
                await asyncio.sleep(downloader.delay)

    async with downloader:
        workers = min(downloader.concurrency, total)
        await asyncio.gather(*(asyncio.create_task(worker()) for _ in range(workers)))

    logger.info(
        "Imagens RPI: ok=%d sem_imagem=%d erro=%d (total=%d)",
        stats[OK],
        stats[SEM_IMAGEM],
        stats[ERROR],
        total,
    )
    return stats


def download_images_sync(
    refs: Sequence[ImageRef],
    *,
    concurrency: int | None = None,
    delay: float | None = None,
    max_retries: int | None = None,
    timeout: float | None = None,
    force: bool = False,
) -> dict[str, int]:
    """Ponte síncrona para o worker da RPI (ou CLI).

    Se já houver um event loop no processo (ex.: chamada de dentro da API), o
    ``asyncio.run`` é executado numa thread dedicada — assim a função continua
    segura em qualquer contexto.
    """
    refs = list(refs)
    if not refs:
        return {OK: 0, SEM_IMAGEM: 0, ERROR: 0}
    kwargs = {
        "concurrency": concurrency,
        "delay": delay,
        "max_retries": max_retries,
        "timeout": timeout,
        "force": force,
    }
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(download_refs(refs, **kwargs))

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(download_refs(refs, **kwargs))).result()


def download_for_edition(
    *,
    numero_rpi: str,
    processos: Iterable[ProcessoMarcas],
    codigos: dict[str, list[str]],
    data_rpi: date | None = None,
    concurrency: int | None = None,
    delay: float | None = None,
    max_retries: int | None = None,
    timeout: float | None = None,
    force: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """Baixa as imagens de uma edição já parseada (usado por ``ingestion.rpi``)."""
    refs = build_image_refs(processos, codigos, numero_rpi, data_rpi=data_rpi)
    if limit:
        refs = refs[:limit]
    stats = download_images_sync(
        refs,
        concurrency=concurrency,
        delay=delay,
        max_retries=max_retries,
        timeout=timeout,
        force=force,
    )
    stats["referencias"] = len(refs)
    return stats


def download_for_desenho_edition(
    *,
    numero_rpi: str,
    processos: Iterable[ProcessoDesenho],
    codigos: dict[str, list[str]],
    data_rpi: date | None = None,
    concurrency: int | None = None,
    delay: float | None = None,
    max_retries: int | None = None,
    timeout: float | None = None,
    force: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """Baixa as figuras de uma edição de Desenho Industrial já parseada."""
    refs = build_desenho_image_refs(
        processos, codigos, numero_rpi, data_rpi=data_rpi
    )
    if limit:
        refs = refs[:limit]
    stats = download_images_sync(
        refs,
        concurrency=concurrency,
        delay=delay,
        max_retries=max_retries,
        timeout=timeout,
        force=force,
    )
    stats["referencias"] = len(refs)
    return stats


def run_pending(
    *,
    numero_rpi: str | None = None,
    limit: int | None = None,
    concurrency: int | None = None,
    delay: float | None = None,
    max_retries: int | None = None,
    timeout: float | None = None,
    force: bool = False,
    section: str = SECTION_MARCAS,
) -> dict[str, int]:
    """Retoma figuras pendentes/falhas da seção escolhida."""
    if section == SECTION_DESENHO:
        rows = db.desenho_rpi_figuras_pendentes(
            numero_rpi=numero_rpi, limit=limit, incluir_erro=True
        )
    else:
        rows = db.rpi_imagens_pendentes(
            numero_rpi=numero_rpi, limit=limit, incluir_erro=True
        )
    refs = [
        ImageRef(
            numero_rpi=str(row["numero_rpi"]),
            numero_processo=str(row["numero_processo"]),
            nome_imagem=row.get("nome_imagem"),
            codigo_interno=row.get("codigo_interno"),
            section=section,
        )
        for row in rows
    ]
    stats = download_images_sync(
        refs,
        concurrency=concurrency,
        delay=delay,
        max_retries=max_retries,
        timeout=timeout,
        force=force,
    )
    stats["pendentes"] = len(refs)
    return stats


def load_refs_from_zip(
    numero_rpi: str, *, zip_path: Path | str | None = None
) -> tuple[list[ImageRef], Revista]:
    """Lê o XML de uma edição (baixando o ZIP se preciso) e monta as referências.

    Importa ``ingestion.rpi`` de forma preguiçosa para evitar ciclo de imports
    (``rpi`` importa este módulo para disparar o download após o parse).
    """
    path = Path(zip_path) if zip_path else CONFIG.rpi_dir / f"RM{numero_rpi}.zip"
    if not path.exists():
        from ingestion.rpi import Edition, build_session, download_edition

        edition = Edition(
            section="marcas",
            numero=str(numero_rpi),
            data=None,
            nome_arquivo_escritorio=path.name,
        )
        with build_session() as session:
            path = download_edition(session, edition)

    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
        if not names:
            raise ValueError(f"{path.name}: nenhum XML de marcas encontrado")
        prefer = f"RM{numero_rpi}.xml".lower()
        member = next(
            (n for n in names if Path(n).name.lower() == prefer),
            max(names, key=lambda n: zf.getinfo(n).file_size),
        )
        with zf.open(member) as fh:
            revista = parse_marcas_xml(fh)

    if revista.parse_error:
        raise ValueError(
            f"XML da RPI {numero_rpi} truncado/corrompido: {revista.parse_error}"
        )

    codigos = db.marcas_codigos_por_numero([p.numero for p in revista.processos])
    refs = build_image_refs(
        revista.processos, codigos, str(numero_rpi), data_rpi=revista.data
    )
    return refs, revista


def load_desenho_refs_from_zip(
    numero_rpi: str, *, zip_path: Path | str | None = None
) -> tuple[list[ImageRef], RevistaDesenho]:
    """Lê o ZIP de Desenhos Industriais e monta as referências de figuras."""
    path = Path(zip_path) if zip_path else CONFIG.rpi_dir / f"DI{numero_rpi}.zip"
    if not path.exists():
        from ingestion.rpi import Edition, build_session, download_edition

        edition = Edition(
            section=SECTION_DESENHO,
            numero=str(numero_rpi),
            data=None,
            nome_arquivo_escritorio=path.name,
        )
        with build_session() as session:
            path = download_edition(session, edition)

    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
        if not names:
            raise ValueError(f"{path.name}: nenhum XML de desenhos encontrado")
        member = max(names, key=lambda n: zf.getinfo(n).file_size)
        with zf.open(member) as fh:
            revista = parse_desenho_industrial_xml(fh)

    if revista.parse_error:
        raise ValueError(
            f"XML da RPI {numero_rpi} truncado/corrompido: {revista.parse_error}"
        )

    mapa = db.desenhos_digitos_map()
    codigos: dict[str, list[str]] = {}
    from ingestion.rpi_parse import process_key

    for proc in revista.processos:
        match = mapa.get(process_key(proc.numero))
        if match:
            codigos[proc.numero] = [match[0]]
    refs = build_desenho_image_refs(
        revista.processos, codigos, str(numero_rpi), data_rpi=revista.data
    )
    return refs, revista


# --- Diagnóstico / CLI -------------------------------------------------------
def diagnose(
    *,
    numero_rpi: str | None = None,
    numero_processo: str | None = None,
    nome_imagem: str | None = None,
) -> dict[str, object]:
    """Testa hosts e (opcionalmente) as URLs de um processo, sem tocar no banco."""
    report: dict[str, object] = {
        "busca_images_base_url": CONFIG.busca_images_base_url,
        "rpi_base_url": CONFIG.rpi_base_url,
        "verify_ssl": CONFIG.verify_ssl,
    }
    headers = _headers()
    for key, url in (
        ("busca", CONFIG.busca_images_base_url),
        ("revistas", CONFIG.rpi_base_url),
    ):
        try:
            resp = requests.head(
                url,
                headers=headers,
                timeout=min(30, CONFIG.http_timeout_seconds),
                verify=CONFIG.verify_ssl,
                allow_redirects=True,
            )
            report[key] = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            report[key] = f"FALHOU: {type(exc).__name__}: {exc}"

    if numero_processo:
        for url in image_url_candidates(
            numero_rpi, numero_processo, nome_imagem, section=SECTION_MARCAS
        ):
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    timeout=min(60, CONFIG.http_timeout_seconds),
                    verify=CONFIG.verify_ssl,
                    stream=True,
                )
                data = next(resp.iter_content(4096), b"")
                kind, _mime = sniff_image(data)
                report[url] = (
                    f"HTTP {resp.status_code} "
                    f"({resp.headers.get('Content-Type', '-')}, {kind})"
                )
                resp.close()
            except requests.RequestException as exc:
                report[url] = f"FALHOU: {type(exc).__name__}: {exc}"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Baixa as imagens/logotipos das marcas referenciadas no XML da RPI "
            "(busca pública + acervo da RPI + fallback com hash)."
        )
    )
    parser.add_argument(
        "--rpi",
        action="append",
        dest="rpis",
        metavar="NUMERO",
        help="Edição da RPI a processar (repetível).",
    )
    parser.add_argument("--pendentes", action="store_true", help="Retoma pendentes/erros.")
    parser.add_argument("--processo", help="Processo específico (com --rpi).")
    parser.add_argument("--nome-imagem", help="Nome do arquivo da figura (opcional).")
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--concorrencia", type=int, default=None)
    parser.add_argument("--delay", type=float, default=None, help="Pausa por item (s).")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignora o cache local (marcas_logos OK) e baixa novamente.",
    )
    parser.add_argument(
        "--secao",
        choices=[SECTION_MARCAS, SECTION_DESENHO],
        default=SECTION_MARCAS,
        help="Seção das imagens: marcas (logotipos) ou desenho_industrial (figuras).",
    )
    parser.add_argument(
        "--diagnostico",
        action="store_true",
        help="Testa hosts/URLs e sai (não toca no banco).",
    )
    args = parser.parse_args(argv)

    if args.diagnostico:
        report = diagnose(
            numero_rpi=(args.rpis[0] if args.rpis else None),
            numero_processo=args.processo,
            nome_imagem=args.nome_imagem,
        )
        for key, value in report.items():
            print(f"{key:<45} {value}")
        reachable = not any(
            str(report.get(key, "")).startswith("FALHOU")
            for key in ("busca", "revistas")
        )
        return 0 if reachable else 2

    refs: list[ImageRef] = []
    if args.pendentes:
        if args.secao == SECTION_DESENHO:
            rows = db.desenho_rpi_figuras_pendentes(
                numero_rpi=(args.rpis[0] if args.rpis else None),
                limit=args.limite,
            )
        else:
            rows = db.rpi_imagens_pendentes(
                numero_rpi=(args.rpis[0] if args.rpis else None),
                limit=args.limite,
            )
        refs.extend(
            ImageRef(
                numero_rpi=str(row["numero_rpi"]),
                numero_processo=str(row["numero_processo"]),
                nome_imagem=row.get("nome_imagem"),
                codigo_interno=row.get("codigo_interno"),
                section=args.secao,
            )
            for row in rows
        )

    for numero in args.rpis or []:
        if args.processo:
            refs.append(
                ImageRef(
                    numero_rpi=str(numero),
                    numero_processo=str(args.processo),
                    nome_imagem=args.nome_imagem or f"{args.processo}.jpg",
                    section=args.secao,
                )
            )
        elif args.secao == SECTION_DESENHO:
            edition_refs, _revista = load_desenho_refs_from_zip(str(numero))
            refs.extend(edition_refs)
        else:
            edition_refs, _revista = load_refs_from_zip(str(numero))
            refs.extend(edition_refs)

    if args.processo and not args.rpis:
        parser.error("--processo exige --rpi (o endpoint da edição precisa do número).")

    # Deduplica (o mesmo processo pode vir de --pendentes e de --rpi).
    seen: set[tuple[str, str, str | None]] = set()
    unique: list[ImageRef] = []
    for ref in refs:
        key = (ref.numero_rpi, ref.numero_processo, ref.codigo_interno)
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    if args.limite:
        unique = unique[: args.limite]

    stats = download_images_sync(
        unique,
        concurrency=args.concorrencia,
        delay=args.delay,
        force=args.force,
    )
    print(
        f"ok={stats[OK]} sem_imagem={stats[SEM_IMAGEM]} "
        f"erro={stats[ERROR]} total={len(unique)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
