"""Sincroniza as **petições** (documentos GRU) das marcas a partir do pePI.


As petições de um processo de marca NÃO fazem parte dos CSVs de dados abertos do
INPI: elas só existem na aplicação de consulta pePI
(``busca.inpi.gov.br``), atrás de uma sessão anônima — exatamente como os
logotipos (``ingestion.logos``):

1. ``GET {pepi}/servlet/LoginController?action=login`` define os cookies de
   sessão (``JSESSIONID``/``BUSCAID``) — sem credenciais;
2. ``GET {pepi}/servlet/MarcasServletController?Action=detail&CodPedido=<cod>``
   devolve a página de detalhe, de onde ``ingestion.pepi_parse`` extrai as
   petições (Pgo/Protocolo/Data/Serviço/Cliente/Delivery).

O downloader é resumível (status terminal em ``marcas_pepi_sync`` é pulado),
educado (concorrência + delay) e re-loga sozinho quando a sessão cai. Roda em
lote **por apresentação** (ex.: ``Mista``/``Figurativa``) ou sobre os códigos já
enfileirados (``PENDING``), que têm prioridade.

Uso (a partir da raiz do monorepo, com o python do venv do backend)::

    python -m ingestion.peticoes --diagnostico
    python -m ingestion.peticoes --apresentacao Mista --apresentacao Figurativa --limite 2000
    python -m ingestion.peticoes --codigos 4482935
    python -m ingestion.peticoes --dias 30          # re-sincroniza terminais antigos
"""

from __future__ import annotations

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ingestion import db
from ingestion.config import CONFIG
from ingestion.logos import check_connectivity, diagnose
from ingestion.pepi_parse import (
    looks_like_login,
    parse_numero_processo,
    parse_peticoes,
    parse_revista,
)
from ingestion.util import get_logger

logger = get_logger(__name__)

# Statuses persistidos em ``marcas_pepi_sync``. ``OK``/``SEM_DADOS`` são
# terminais (o resume os pula); ``ERROR`` é retentável; ``PENDING`` é a fila.
OK = "OK"
SEM_DADOS = "SEM_DADOS"
ERROR = "ERROR"
PENDING = "PENDING"


class PepiDetailClient:
    """Sessão anônima do pePI, confinada a uma thread (login + detalhe)."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": CONFIG.user_agent})
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

    def fetch_detail(self, codigo_interno: str) -> tuple[int, str]:
        """Baixa a página de detalhe; devolve ``(http_status, html)``."""
        if not self.logged_in:
            self.login()
        url = (
            f"{CONFIG.pePI_base_url}/servlet/MarcasServletController"
            f"?Action=detail&CodPedido={codigo_interno}"
        )
        resp = self._session.get(url, timeout=CONFIG.http_timeout_seconds)
        # A página declara ISO-8859-1 no <meta>; decodifica fixo em latin-1 para
        # não depender do header Content-Type (o servlet legado não o define bem).
        text = resp.content.decode("latin-1", errors="replace")
        return resp.status_code, text


def process_code(client: PepiDetailClient, codigo_interno: str) -> tuple[str, str]:
    """Busca + grava as petições de um código; devolve ``(status, detalhe)``.

    Re-tenta com backoff em problemas de sessão (tela de login) e de rede. Uma
    página que não é o detalhe (gateway/erro) conta como falha retentável — só
    gravamos ``SEM_DADOS`` quando o detalhe foi realmente lido e não havia
    petições (distingue "processo sem petições" de "layout/fonte mudou").
    """
    attempts = 0
    last_err: str | None = None
    while attempts <= CONFIG.http_retries:
        attempts += 1
        try:
            status, text = client.fetch_detail(codigo_interno)

            if status == 404:
                db.upsert_pepi_sync(
                    codigo_interno=codigo_interno,
                    status=SEM_DADOS,
                    http_status=status,
                    tentativas=attempts,
                    erro="processo não encontrado",
                    sincronizado_em=datetime.now(timezone.utc),
                )
                return SEM_DADOS, "não encontrado"

            if status >= 400:
                last_err = f"HTTP {status}"
                time.sleep(min(2 ** attempts, 15))
                continue

            if looks_like_login(text):
                last_err = "sessão expirada (retornou a tela de login)"
                client.logged_in = False
                time.sleep(min(2 ** attempts, 15))
                continue

            if "MarcaPesquisa" not in text and "numeroProcesso" not in text:
                last_err = "página inesperada (sem o formulário de detalhe)"
                time.sleep(min(2 ** attempts, 15))
                continue

            rows = parse_peticoes(text)
            numero_inpi = parse_numero_processo(text)
            dados_atualizados_em, revista = parse_revista(text)
            count = db.replace_peticoes(
                codigo_interno=codigo_interno, rows=rows, numero_inpi=numero_inpi
            )
            result = OK if rows else SEM_DADOS
            db.upsert_pepi_sync(
                codigo_interno=codigo_interno,
                status=result,
                peticoes_count=count,
                http_status=status,
                revista=revista,
                dados_atualizados_em=dados_atualizados_em,
                tentativas=attempts,
                sincronizado_em=datetime.now(timezone.utc),
            )
            return result, f"{count} petição(ões)"

        except requests.RequestException as exc:
            last_err = str(exc)
            time.sleep(min(2 ** attempts, 15))

    db.upsert_pepi_sync(
        codigo_interno=codigo_interno,
        status=ERROR,
        tentativas=attempts,
        erro=last_err,
    )
    return ERROR, last_err or "erro"


def sync(
    *,
    apresentacoes: list[str] | None = None,
    limit: int | None = None,
    concurrency: int | None = None,
    delay: float | None = None,
    only_pending: bool = True,
    codes: list[str] | None = None,
    dias: int | None = None,
    force: bool = False,
) -> dict[str, int]:
    """Processa as petições dos códigos selecionados; devolve status -> contagem.

    Falha rápido (sem gravar nada) quando o pePI está inacessível, para uma
    indisponibilidade do INPI não virar milhares de linhas ``ERROR``. Use
    ``force=True`` para pular o preflight.
    """
    concurrency = concurrency or CONFIG.pepi_concurrency
    delay = CONFIG.pepi_delay_seconds if delay is None else delay

    if not force:
        ok, detail = check_connectivity()
        if not ok:
            logger.error("Preflight do pePI falhou: %s", detail)
            logger.error(
                "Nenhuma petição será buscada. Rode "
                "`python -m ingestion.peticoes --diagnostico` para detalhes."
            )
            raise ConnectionError(detail)

    if codes is None:
        codes = db.peticao_codes(
            apresentacoes=apresentacoes,
            only_pending=only_pending,
            limit=limit,
            dias=dias,
        )

    total = len(codes)
    stats = {OK: 0, SEM_DADOS: 0, ERROR: 0}
    logger.info("Marcas a sincronizar: %d (conc=%d, delay=%.2fs)", total, concurrency, delay)
    if total == 0:
        return stats

    counter = {"done": 0}
    lock = threading.Lock()
    _tls = threading.local()

    def _client() -> PepiDetailClient:
        client = getattr(_tls, "client", None)
        if client is None:
            client = PepiDetailClient()
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
                    "  %d/%d  ok=%d sem_dados=%d erro=%d",
                    counter["done"],
                    total,
                    stats[OK],
                    stats[SEM_DADOS],
                    stats[ERROR],
                )
        return status

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_worker, c) for c in codes]
        for fut in as_completed(futures):
            status = fut.result()
            stats[status] = stats.get(status, 0) + 1

    logger.info(
        "Concluído: ok=%d sem_dados=%d erro=%d",
        stats[OK],
        stats[SEM_DADOS],
        stats[ERROR],
    )
    return stats


def _dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sincroniza as petições (documentos GRU) das marcas a partir do "
            "pePI (sessão anônima)."
        )
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
        "--dias",
        type=int,
        default=None,
        help="Re-sincroniza códigos terminais sincronizados há mais de N dias.",
    )
    parser.add_argument(
        "--codigos",
        action="append",
        dest="codes",
        help="Códigos internos específicos (repetível).",
    )
    parser.add_argument(
        "--sem-fila",
        action="store_true",
        help="Não drena antes os códigos enfileirados (PENDING).",
    )
    parser.add_argument(
        "--fila-limite",
        type=int,
        default=500,
        help="Máx. de itens da fila (PENDING) drenados por execução (0 = sem limite).",
    )
    parser.add_argument(
        "--todos",
        action="store_true",
        help="Não pula os já processados (ignora o resume/TTL).",
    )
    parser.add_argument(
        "--diagnostico",
        action="store_true",
        help="Só testa a conectividade com o pePI (DNS/TCP/TLS/HTTP) e sai.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignora o preflight de conectividade e tenta mesmo assim.",
    )
    args = parser.parse_args(argv)

    if args.diagnostico:
        report = diagnose(verbose=False)
        for key in ("pePI_base_url", "verify_ssl", "host", "port", "dns", "tcp", "tls", "http"):
            print(f"{key:<14} {report.get(key)}")
        reachable = not str(report.get("tcp", "")).startswith("FALHOU")
        return 0 if reachable else 2

    codes: list[str] = list(args.codes or [])

    # Drena antes a fila sob demanda (o que alguém abriu na tela), salvo se o
    # usuário pediu códigos específicos ou desligou a fila.
    if not args.sem_fila and not args.codes:
        queue_limit = args.fila_limite or None
        fila = db.pending_codes(limit=queue_limit)
        if fila:
            logger.info("Fila sob demanda (PENDING): %d código(s) com prioridade.", len(fila))
        codes = _dedupe(fila + codes)

    explicit = codes or None
    stats = sync(
        apresentacoes=args.apresentacoes,
        limit=args.limite,
        concurrency=args.concorrencia,
        delay=args.delay,
        only_pending=not args.todos,
        codes=explicit,
        dias=args.dias,
        force=args.force,
    )
    print(f"ok={stats[OK]} sem_dados={stats[SEM_DADOS]} erro={stats[ERROR]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
