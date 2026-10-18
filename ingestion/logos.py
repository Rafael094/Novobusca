"""Download marca logotipos from the public pePI image servlet.



The INPI open-data CSVs carry no images. The pePI search application, however,

exposes them publicly through an *anonymous* session:



1. ``GET {pepi}/servlet/LoginController?action=login`` sets the session cookies

   (``JSESSIONID``/``BUSCAID``) — no credentials required;

2. ``GET {pepi}/servlet/LogoMarcasServletController?Action=image&codProcesso=<cod>``

   returns the JPEG for that ``codigo_interno``.



When a processo has no logotipo the servlet returns an HTML error page or a

fixed "no image" placeholder GIF (while still advertising ``Content-Type:

image/jpg``). Both are detected here and recorded as ``SEM_IMAGEM`` instead of

being stored, so we never persist thousands of copies of an empty placeholder.



The downloader is resumable (terminal rows are skipped), polite (bounded

concurrency + delay) and re-logs-in automatically when the session drops.

"""



from __future__ import annotations



import argparse

import hashlib

import socket

import ssl

import threading

import time

import urllib3

from concurrent.futures import ThreadPoolExecutor, as_completed

from datetime import datetime, timezone

from pathlib import Path

from urllib.parse import urlparse

import requests

from requests.adapters import HTTPAdapter

from urllib3.util.retry import Retry

from urllib3.exceptions import InsecureRequestWarning



from ingestion import db

from ingestion.config import CONFIG

from ingestion.util import ensure_dirs, get_logger, human_size



logger = get_logger(__name__)



# Magic-byte signatures we accept as a real image.

_JPEG = b"\xff\xd8\xff"

_PNG = b"\x89PNG\r\n\x1a\n"

_GIF = b"GIF8"



# Statuses (terminal ones also gate resume).

OK = "OK"

SEM_IMAGEM = "SEM_IMAGEM"

ERROR = "ERROR"





class LogoClient:

    """A thread-confined pePI session (login + fetch).



    ``requests.Session`` is not guaranteed thread-safe, so each worker thread

    owns its own :class:`LogoClient`.

    """



    def __init__(self) -> None:

        self._session = requests.Session()

        self._session.headers.update({"User-Agent": CONFIG.user_agent})

        # Retry transient transport failures at the urllib3 layer too, so a
        # mid-handshake TLS reset (``UNEXPECTED_EOF_WHILE_READING``) that hits
        # the very first request of a fresh session is absorbed here instead of
        # bubbling straight up to ``process_code``. The caller still retries on
        # top of this for HTML/session-expiry cases.
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )

        adapter = HTTPAdapter(max_retries=retry)

        self._session.mount("https://", adapter)

        self._session.mount("http://", adapter)

        self._session.verify = CONFIG.verify_ssl

        self.logged_in = False



    def login(self) -> None:

        url = f"{CONFIG.pePI_base_url}/servlet/LoginController?action=login"

        resp = self._session.get(url, timeout=CONFIG.http_timeout_seconds)

        resp.raise_for_status()

        self.logged_in = True



    def fetch(self, codigo_interno: str) -> tuple[str, bytes, str | None]:

        """Fetch one logo.



        Returns ``(kind, data, mime)`` where ``kind`` is one of ``image``

        (real picture), ``placeholder`` (servlet's "no image") or ``html``

        (login page / error page — a session problem the caller may retry).

        """

        if not self.logged_in:

            self.login()

        url = (

            f"{CONFIG.pePI_base_url}/servlet/LogoMarcasServletController"

            f"?Action=image&codProcesso={codigo_interno}"

        )

        resp = self._session.get(url, timeout=CONFIG.http_timeout_seconds)

        resp.raise_for_status()

        data = resp.content

        ctype = (resp.headers.get("Content-Type") or "").lower()



        if data[:3] == _JPEG:

            return "image", data, "image/jpeg"

        if data[:8] == _PNG:

            return "image", data, "image/png"

        if data[:4] == _GIF:

            # The servlet serves its "no image" placeholder as a GIF (often with

            # a misleading ``image/jpg`` header). A genuine marca image is never

            # a GIF here, so treat all GIFs as "no image".

            return "placeholder", data, ctype or "image/gif"

        if "text/html" in ctype or b"<html" in data[:2048].lower():

            return "html", data, ctype or "text/html"

        # Unknown binary: not storable.

        return "placeholder", data, ctype or None





def _bucket_dir(codigo_interno: str) -> Path:

    """Shard by the first two chars to avoid a single huge directory."""

    prefix = (codigo_interno or "_")[:2]

    return CONFIG.logos_dir / prefix





def _rel_arquivo(path: Path) -> str:

    """Store a path relative to the data dir when possible (portable)."""

    try:

        return path.relative_to(CONFIG.data_dir).as_posix()

    except ValueError:

        return str(path)





def _write_atomic(path: Path, data: bytes) -> None:

    ensure_dirs(path.parent)

    tmp = path.with_suffix(path.suffix + ".part")

    tmp.write_bytes(data)

    tmp.replace(path)





def _destino(codigo_interno: str, mime: str | None) -> Path:

    ext = ".png" if mime == "image/png" else ".jpg"

    return _bucket_dir(codigo_interno) / f"{codigo_interno}{ext}"




def _host_port(url: str) -> tuple[str, int]:

    """Return ``(host, port)`` for an http(s) URL (default ports applied)."""

    parsed = urlparse(url)

    host = parsed.hostname or ""

    if parsed.port:

        return host, parsed.port

    return host, 443 if parsed.scheme == "https" else 80




def check_connectivity() -> tuple[bool, str]:

    """Preflight the pePI host before starting a (long) batch download.

    The legacy pePI server (``busca.inpi.gov.br``) sits behind a fragile TLS

    front-end that intermittently aborts handshakes

    (``UNEXPECTED_EOF_WHILE_READING``) or refuses connections entirely. When

    that happens every code would burn ``http_retries`` attempts with backoff

    and flood ``marcas_logos`` with ``ERROR`` rows, so we fail fast with a

    single, actionable message instead.

    Returns ``(ok, detail)``. ``ok`` is False only when the endpoint is clearly

    unreachable; a reachable-but-erroring server (e.g. HTTP 4xx/5xx) is treated

    as ``ok`` so the normal retry path still applies.

    """

    host, port = _host_port(f"{CONFIG.pePI_base_url}/servlet/LoginController")

    if not host:

        return False, f"URL do pePI invalida: {CONFIG.pePI_base_url!r}"

    # 1) TCP reachability (fast, no TLS involved).

    try:

        with socket.create_connection((host, port), timeout=15):

            pass

    except OSError as exc:

        return False, f"TCP {host}:{port} inacessivel ({type(exc).__name__}: {exc})"

    # 2) TLS handshake (only for https).

    if port == 443:

        try:

            ctx = ssl.create_default_context()

            if not CONFIG.verify_ssl:

                ctx.check_hostname = False

                ctx.verify_mode = ssl.CERT_NONE

            with socket.create_connection((host, port), timeout=15) as raw:

                with ctx.wrap_socket(raw, server_hostname=host):

                    pass

        except ssl.SSLError as exc:

            return False, (

                f"handshake TLS com {host}:{port} falhou ({type(exc).__name__}: {exc}). "

                "O host legado do pePI costuma recusar/derrubar a conexao TLS "

                "de forma intermitente ou bloquear o seu IP; verifique a rede, "

                "tente novamente mais tarde ou use --diagnostico para detalhes."

            )

        except OSError as exc:

            return False, f"conexao TLS {host}:{port} falhou ({type(exc).__name__}: {exc})"

    return True, f"{host}:{port} acessivel"




def diagnose(verbose: bool = True) -> dict[str, object]:

    """Probe the pePI endpoint layer by layer and return a report dict.

    Used by ``python -m ingestion.logos --diagnostico`` to explain failures

    (DNS, TCP, TLS handshake, HTTP) without touching the database.

    """

    report: dict[str, object] = {

        "pePI_base_url": CONFIG.pePI_base_url,

        "verify_ssl": CONFIG.verify_ssl,

        "user_agent": CONFIG.user_agent,

    }

    host, port = _host_port(f"{CONFIG.pePI_base_url}/servlet/LoginController")

    report["host"] = host

    report["port"] = port

    # DNS

    try:

        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)

        ips = sorted({info[4][0] for info in infos})

        report["dns"] = ips

    except OSError as exc:

        report["dns"] = f"FALHOU: {type(exc).__name__}: {exc}"

    # TCP

    try:

        with socket.create_connection((host, port), timeout=15) as sock:

            report["tcp"] = f"OK ({sock.getpeername()[0]}:{sock.getpeername()[1]})"

    except OSError as exc:

        report["tcp"] = f"FALHOU: {type(exc).__name__}: {exc}"

    # TLS

    if port == 443:

        try:

            ctx = ssl.create_default_context()

            if not CONFIG.verify_ssl:

                ctx.check_hostname = False

                ctx.verify_mode = ssl.CERT_NONE

            with socket.create_connection((host, port), timeout=15) as raw:

                with ctx.wrap_socket(raw, server_hostname=host) as tls:

                    report["tls"] = f"OK ({tls.version()})"

        except Exception as exc:  # noqa: BLE001 - diagnostic breadth is the point

            report["tls"] = f"FALHOU: {type(exc).__name__}: {exc}"

    # HTTP (through the real session, honouring retries/verify)

    if CONFIG.verify_ssl:

        pass

    else:

        urllib3.disable_warnings(InsecureRequestWarning)

    try:

        with requests.Session() as sess:

            sess.verify = CONFIG.verify_ssl

            resp = sess.get(

                f"{CONFIG.pePI_base_url}/servlet/LoginController?action=login",

                headers={"User-Agent": CONFIG.user_agent},

                timeout=CONFIG.http_timeout_seconds,

            )

        report["http"] = f"OK (status={resp.status_code}, {len(resp.content)} bytes)"

    except requests.RequestException as exc:

        report["http"] = f"FALHOU: {type(exc).__name__}: {exc}"

    if verbose:

        logger.info("Diagnostico do pePI:")

        for key in ("pePI_base_url", "verify_ssl", "host", "port", "dns", "tcp", "tls", "http"):

            logger.info("  %-14s %s", key, report.get(key))

    return report





def process_code(client: LogoClient, codigo_interno: str) -> tuple[str, str]:

    """Download + persist one logo; returns ``(status, detail)``.



    Retries a few times on session/HTML problems (re-login) and on transient

    network errors, with exponential backoff.

    """

    attempts = 0

    last_err: str | None = None

    while attempts <= CONFIG.http_retries:

        attempts += 1

        try:

            kind, data, mime = client.fetch(codigo_interno)

            if kind == "image":

                dest = _destino(codigo_interno, mime)

                _write_atomic(dest, data)

                sha = hashlib.sha256(data).hexdigest()

                db.upsert_logo(

                    codigo_interno=codigo_interno,

                    status=OK,

                    arquivo=_rel_arquivo(dest),

                    mime=mime,

                    bytes_=len(data),

                    sha256=sha,

                    tentativas=attempts,

                    baixado_em=datetime.now(timezone.utc),

                )

                return OK, f"{human_size(len(data))} -> {dest.name}"

            if kind == "placeholder":

                db.upsert_logo(

                    codigo_interno=codigo_interno,

                    status=SEM_IMAGEM,

                    tentativas=attempts,

                )

                return SEM_IMAGEM, "sem imagem"

            # HTML → likely an expired/anonymous session; re-login and retry.

            last_err = "sessão expirada (resposta HTML)"

            client.logged_in = False

            time.sleep(min(2 ** attempts, 15))

        except requests.RequestException as exc:

            last_err = str(exc)

            time.sleep(min(2 ** attempts, 15))



    db.upsert_logo(

        codigo_interno=codigo_interno, status=ERROR, tentativas=attempts, erro=last_err

    )

    return ERROR, last_err or "erro"





def download(

    *,

    apresentacoes: list[str] | None = None,

    limit: int | None = None,

    concurrency: int | None = None,

    delay: float | None = None,

    only_pending: bool = True,

    codes: list[str] | None = None,

    force: bool = False,

) -> dict[str, int]:

    """Download logos for the selected codes; returns a status -> count map.

    Fails fast (recording nothing) when the pePI host is unreachable, so a

    full INPI outage does not turn into thousands of ERROR rows. Pass

    ``force=True`` to skip that preflight.

    """

    concurrency = concurrency or CONFIG.logo_concurrency

    delay = CONFIG.logo_delay_seconds if delay is None else delay

    if not force:

        ok, detail = check_connectivity()

        if not ok:

            logger.error("Preflight do pePI falhou: %s", detail)

            logger.error(

                "Nenhum logotipo sera baixado. Rode "

                "`python -m ingestion.logos --diagnostico` para detalhes."

            )

            raise ConnectionError(detail)



    if codes is None:

        codes = db.logo_codes(

            apresentacoes=apresentacoes, only_pending=only_pending, limit=limit

        )

    total = len(codes)

    stats = {OK: 0, SEM_IMAGEM: 0, ERROR: 0}

    logger.info(

        "Logotipos a baixar: %d (conc=%d, delay=%.2fs)", total, concurrency, delay

    )

    if total == 0:

        return stats



    counter = {"done": 0}

    lock = threading.Lock()

    _tls = threading.local()



    def _client() -> LogoClient:

        client = getattr(_tls, "client", None)

        if client is None:

            client = LogoClient()

            _tls.client = client

        return client



    def _worker(codigo_interno: str) -> str:

        status, _detail = process_code(_client(), codigo_interno)

        if delay:

            time.sleep(delay)

        with lock:

            counter["done"] += 1

            if counter["done"] % 200 == 0 or counter["done"] == total:

                logger.info(

                    "  %d/%d  ok=%d sem_imagem=%d erro=%d",

                    counter["done"],

                    total,

                    stats[OK],

                    stats[SEM_IMAGEM],

                    stats[ERROR],

                )

        return status



    with ThreadPoolExecutor(max_workers=concurrency) as pool:

        futures = [pool.submit(_worker, c) for c in codes]

        for fut in as_completed(futures):

            status = fut.result()

            stats[status] = stats.get(status, 0) + 1



    logger.info(

        "Concluído: ok=%d sem_imagem=%d erro=%d",

        stats[OK],

        stats[SEM_IMAGEM],

        stats[ERROR],

    )

    return stats





def main(argv: list[str] | None = None) -> int:

    parser = argparse.ArgumentParser(

        description="Baixa os logotipos das marcas do pePI (sessão anônima)."

    )

    parser.add_argument(

        "--apresentacao",

        action="append",

        dest="apresentacoes",

        help="Filtra por descricao_apresentacao (ex.: Mista). Repetível.",

    )

    parser.add_argument("--limite", type=int, default=None, help="Máx. de códigos.")

    parser.add_argument("--concorrencia", type=int, default=None)

    parser.add_argument("--delay", type=float, default=None, help="Pausa por req (s).")

    parser.add_argument(

        "--codigos",

        action="append",

        dest="codes",

        help="Códigos internos específicos (repetível).",

    )

    parser.add_argument(

        "--todos",

        action="store_true",

        help="Não pula os já processados (ignora o resume).",

    )

    parser.add_argument(

        "--diagnostico",

        action="store_true",

        help="So testa a conectividade com o pePI (DNS/TCP/TLS/HTTP) e sai.",

    )

    parser.add_argument(

        "--force",

        action="store_true",

        help="Ignora o preflight de conectividade e tenta baixar mesmo assim.",

    )

    args = parser.parse_args(argv)

    if args.diagnostico:

        report = diagnose(verbose=False)

        for key in ("pePI_base_url", "verify_ssl", "host", "port", "dns", "tcp", "tls", "http"):

            print(f"{key:<14} {report.get(key)}")

        reachable = not str(report.get("tcp", "")).startswith("FALHOU")

        return 0 if reachable else 2

    stats = download(

        apresentacoes=args.apresentacoes,

        limit=args.limite,

        concurrency=args.concorrencia,

        delay=args.delay,

        only_pending=not args.todos,

        codes=args.codes,

        force=args.force,

    )

    print(f"ok={stats[OK]} sem_imagem={stats[SEM_IMAGEM]} erro={stats[ERROR]}")

    return 0





if __name__ == "__main__":

    raise SystemExit(main())