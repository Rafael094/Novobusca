"""Testes do pipeline de imagens/logotipos da RPI (``ingestion.rpi_images``).

Os testes não tocam no INPI nem no banco: usam ``httpx.MockTransport`` para
simular as respostas dos endpoints e substituem as funções de persistência de
``ingestion.db`` por um gravador em memória. O diretório de dados é redirecionado
para ``tmp_path`` (via ``dataclasses.replace`` na configuração congelada).
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

# O pacote ``ingestion`` vive na raiz do monorepo (fora de ``backend/``).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ingestion import rpi_images  # noqa: E402
from ingestion.config import CONFIG as BASE_CONFIG  # noqa: E402
from ingestion.rpi_parse import (  # noqa: E402
    Despacho,
    ProcessoMarcas,
    normalize_image_name,
)

_JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-payload" * 8
_PNG = b"\x89PNG\r\n\x1a\n" + b"png-payload" * 8
_WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"webp" * 8
_GIF = b"GIF89a" + b"placeholder" * 4
_HTML = b"<!DOCTYPE html><html><body>Bloqueado pelo WAF</body></html>"

_ALL = "https://busca.inpi.gov.br/marca/imagem"
_RPI = "https://revistas.inpi.gov.br"


# --- Fixtures / helpers ------------------------------------------------------
@pytest.fixture()
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Configuração isolada (data dir temporário) para o módulo de imagens."""
    config = dataclasses.replace(
        BASE_CONFIG,
        data_dir=tmp_path,
        busca_images_base_url=_ALL,
        rpi_base_url=_RPI,
        rpi_image_max_bytes=1024 * 1024,
        rpi_image_retries=2,
    )
    monkeypatch.setattr(rpi_images, "CONFIG", config)
    return config


class _FakeDb:
    """Gravador em memória das chamadas de persistência."""

    def __init__(self) -> None:
        self.rpi_rows: list[dict[str, Any]] = []
        self.logo_rows: list[dict[str, Any]] = []
        self.logo_cache: dict[str, dict[str, Any]] = {}
        self.rpi_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self.logo_reads = 0

    def get_logo(self, codigo_interno: str) -> dict[str, Any] | None:
        self.logo_reads += 1
        return self.logo_cache.get(codigo_interno)

    def get_rpi_imagem(
        self, numero_rpi: str, numero_processo: str
    ) -> dict[str, Any] | None:
        return self.rpi_cache.get((numero_rpi, numero_processo))

    def upsert_rpi_imagem(self, **kwargs: Any) -> None:
        self.rpi_rows.append(kwargs)

    def upsert_logo(self, **kwargs: Any) -> None:
        self.logo_rows.append(kwargs)


@pytest.fixture()
def fake_db(monkeypatch: pytest.MonkeyPatch) -> _FakeDb:
    fake = _FakeDb()
    monkeypatch.setattr(rpi_images.db, "get_logo", fake.get_logo)
    monkeypatch.setattr(rpi_images.db, "get_rpi_imagem", fake.get_rpi_imagem)
    monkeypatch.setattr(rpi_images.db, "upsert_rpi_imagem", fake.upsert_rpi_imagem)
    monkeypatch.setattr(rpi_images.db, "upsert_logo", fake.upsert_logo)
    # O backoff real dorme segundos; nos testes ele só atrasaria a suíte.
    async def _no_sleep(self: Any, attempt: int, response: Any) -> None:
        return None

    monkeypatch.setattr(rpi_images.RpiImageDownloader, "_sleep_backoff", _no_sleep)
    return fake


def _ref(
    *,
    numero_processo: str = "912345678",
    nome_imagem: str | None = "912345678.jpg",
    codigo_interno: str | None = "4482935",
    numero_rpi: str = "2910",
) -> rpi_images.ImageRef:
    return rpi_images.ImageRef(
        numero_rpi=numero_rpi,
        numero_processo=numero_processo,
        nome_imagem=nome_imagem,
        codigo_interno=codigo_interno,
    )


def _run(
    refs: list[rpi_images.ImageRef],
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: Any,
) -> dict[str, int]:
    """Executa ``download_refs`` com um transporte falso e sem pausa entre itens."""
    transport = httpx.MockTransport(handler)

    async def _main() -> dict[str, int]:
        async with httpx.AsyncClient(transport=transport) as client:
            return await rpi_images.download_refs(
                refs, client=client, delay=0.0, **kwargs
            )

    return asyncio.run(_main())


def _sequence(
    responses: dict[str, list[httpx.Response]],
    calls: list[str] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    """Handler que consome respostas por URL (a última se repete)."""

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if calls is not None:
            calls.append(url)
        queue = responses.get(url)
        if not queue:
            return httpx.Response(404, request=request)
        response = queue.pop(0) if len(queue) > 1 else queue[0]
        response.request = request
        return response

    return handler


# --- URLs / sniff / referências ---------------------------------------------
def test_image_url_candidates_ordem_e_fallback(cfg: Any) -> None:
    urls = rpi_images.image_url_candidates("2910", "912345678", "912345678.jpg")

    assert urls == [
        f"{_ALL}/912345678.jpg",
        f"{_RPI}/rpi/images/2910/912345678.jpg",
        f"{_ALL}/912/912345678.jpg",
    ]


def test_image_url_candidates_usa_nome_imagem_do_xml(cfg: Any) -> None:
    urls = rpi_images.image_url_candidates("2910", "912345678", "figura.png")

    assert urls == [
        f"{_ALL}/912345678.jpg",
        f"{_RPI}/rpi/images/2910/figura.png",
        f"{_RPI}/rpi/images/2910/912345678.jpg",
        f"{_ALL}/912/912345678.jpg",
    ]


def test_image_url_candidates_sem_edicao_ou_processo(cfg: Any) -> None:
    assert rpi_images.image_url_candidates(None, "912345678") == [
        f"{_ALL}/912345678.jpg",
        f"{_ALL}/912/912345678.jpg",
    ]
    assert rpi_images.image_url_candidates("2910", "") == []
    assert rpi_images.image_url_candidates("2910", None) == []  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "data,kind,mime",
    [
        (_JPEG, "image", "image/jpeg"),
        (_PNG, "image", "image/png"),
        (_WEBP, "image", "image/webp"),
        (_GIF, "placeholder", "image/gif"),
        (_HTML, "html", "text/html"),
        (b"nao e imagem", "unknown", None),
        (b"", "unknown", None),
    ],
)
def test_sniff_image(data: bytes, kind: str, mime: str | None) -> None:
    assert rpi_images.sniff_image(data) == (kind, mime)


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("912345678.jpg", "912345678.jpg"),
        ("  pasta/912345678.JPG  ", "912345678.JPG"),
        ("https://exemplo/x.jpg?token=1#frag", "x.jpg"),
        ("..\\..\\etc\\passwd", "passwd"),
        ("", None),
        (None, None),
        ("../", None),
        ("..", None),
        ("a\x00b.jpg", "ab.jpg"),
    ],
)
def test_normalize_image_name(entrada: str | None, esperado: str | None) -> None:
    assert normalize_image_name(entrada) == esperado


def test_build_image_refs_so_com_figura_e_expande_codigos() -> None:
    processos = [
        ProcessoMarcas(
            numero="111111111",
            nome_imagem="111111111.jpg",
            marca_nome="ALFA",
            apresentacao="Mista",
            despachos=[Despacho(codigo="IPAS009")],
        ),
        ProcessoMarcas(numero="222222222", nome_imagem=None),
        ProcessoMarcas(numero="333333333", nome_imagem="figura.png"),
    ]
    codigos = {"111111111": ["a", "b"], "222222222": ["c"], "333333333": []}

    refs = rpi_images.build_image_refs(
        processos, codigos, "2910", data_rpi=date(2026, 10, 13)
    )

    assert [(r.numero_processo, r.codigo_interno) for r in refs] == [
        ("111111111", "a"),
        ("111111111", "b"),
        ("333333333", None),
    ]
    assert refs[0].marca_nome == "ALFA"
    assert refs[0].apresentacao == "Mista"
    assert refs[0].despachos == ("IPAS009",)
    assert refs[0].data_rpi == date(2026, 10, 13)


def test_build_image_refs_deduplica() -> None:
    processos = [
        ProcessoMarcas(numero="111111111", nome_imagem="111111111.jpg"),
        ProcessoMarcas(numero="111111111", nome_imagem="111111111.jpg"),
    ]
    refs = rpi_images.build_image_refs(
        processos, {"111111111": ["a", "a"]}, "2910"
    )
    assert len(refs) == 1


# --- Download / fallback / status -------------------------------------------
def test_baixa_na_primeira_url_e_persiste(
    cfg: Any, fake_db: _FakeDb, tmp_path: Path
) -> None:
    calls: list[str] = []
    handler = _sequence(
        {f"{_ALL}/912345678.jpg": [httpx.Response(200, content=_JPEG)]}, calls
    )

    stats = _run([_ref()], handler)

    assert stats == {rpi_images.OK: 1, rpi_images.SEM_IMAGEM: 0, rpi_images.ERROR: 0}
    assert calls == [f"{_ALL}/912345678.jpg"]

    row = fake_db.rpi_rows[0]
    assert row["status"] == rpi_images.OK
    assert row["numero_rpi"] == "2910"
    assert row["numero_processo"] == "912345678"
    assert row["nome_imagem"] == "912345678.jpg"
    assert row["codigo_interno"] == "4482935"
    assert row["origem_url"] == f"{_ALL}/912345678.jpg"
    assert row["mime"] == "image/jpeg"
    assert row["bytes_"] == len(_JPEG)
    assert row["sha256"] == hashlib.sha256(_JPEG).hexdigest()
    assert row["baixado_em"] is not None

    destino = Path(row["arquivo"])
    assert not destino.is_absolute()
    assert destino.as_posix() == "raw/marcas/logos/44/4482935.jpg"
    assert (tmp_path / destino).read_bytes() == _JPEG

    # Espelha em marcas_logos para a API servir imediatamente.
    assert fake_db.logo_rows[0]["codigo_interno"] == "4482935"
    assert fake_db.logo_rows[0]["status"] == rpi_images.OK


def test_fallback_404_busca_para_acervo_da_rpi(
    cfg: Any, fake_db: _FakeDb, tmp_path: Path
) -> None:
    rpi_url = f"{_RPI}/rpi/images/2910/912345678.jpg"
    calls: list[str] = []
    handler = _sequence(
        {
            f"{_ALL}/912345678.jpg": [httpx.Response(404)],
            rpi_url: [httpx.Response(200, content=_PNG)],
        },
        calls,
    )

    stats = _run([_ref()], handler)

    assert stats[rpi_images.OK] == 1
    assert calls == [f"{_ALL}/912345678.jpg", rpi_url]
    assert fake_db.rpi_rows[0]["origem_url"] == rpi_url
    assert fake_db.rpi_rows[0]["mime"] == "image/png"
    # Extensão acompanha o formato detectado.
    assert fake_db.rpi_rows[0]["arquivo"].endswith("/4482935.png")
    assert (tmp_path / fake_db.rpi_rows[0]["arquivo"]).read_bytes() == _PNG


def test_fallback_completo_404_marca_sem_imagem(cfg: Any, fake_db: _FakeDb) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(404, request=request)

    stats = _run([_ref()], handler)

    assert stats[rpi_images.SEM_IMAGEM] == 1
    assert len(calls) == 3  # todas as URLs foram tentadas
    assert fake_db.rpi_rows[0]["status"] == rpi_images.SEM_IMAGEM
    assert fake_db.rpi_rows[0]["baixado_em"] is None
    assert fake_db.logo_rows[0]["status"] == rpi_images.SEM_IMAGEM


def test_retry_em_503_na_mesma_url(cfg: Any, fake_db: _FakeDb) -> None:
    calls: list[str] = []
    handler = _sequence(
        {
            f"{_ALL}/912345678.jpg": [
                httpx.Response(503),
                httpx.Response(200, content=_JPEG),
            ]
        },
        calls,
    )

    stats = _run([_ref()], handler)

    assert stats[rpi_images.OK] == 1
    # Só a primeira URL foi chamada (duas vezes), sem cair no fallback.
    assert calls == [f"{_ALL}/912345678.jpg", f"{_ALL}/912345678.jpg"]
    assert fake_db.rpi_rows[0]["tentativas"] == 2


def test_retry_esgotado_cai_para_fallback(cfg: Any, fake_db: _FakeDb) -> None:
    calls: list[str] = []
    rpi_url = f"{_RPI}/rpi/images/2910/912345678.jpg"
    handler = _sequence(
        {
            f"{_ALL}/912345678.jpg": [httpx.Response(500)],
            rpi_url: [httpx.Response(200, content=_JPEG)],
        },
        calls,
    )

    stats = _run([_ref()], handler, max_retries=1)

    assert stats[rpi_images.OK] == 1
    assert calls == [f"{_ALL}/912345678.jpg", f"{_ALL}/912345678.jpg", rpi_url]


def test_placeholder_gif_vira_sem_imagem(cfg: Any, fake_db: _FakeDb) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_GIF, request=request)

    stats = _run([_ref()], handler)

    assert stats[rpi_images.SEM_IMAGEM] == 1
    assert fake_db.rpi_rows[0]["status"] == rpi_images.SEM_IMAGEM
    assert fake_db.rpi_rows[0]["arquivo"] is None
    assert "placeholder" in (fake_db.rpi_rows[0]["erro"] or "")


def test_html_vira_error(cfg: Any, fake_db: _FakeDb) -> None:
    handler = _sequence(
        {f"{_ALL}/912345678.jpg": [httpx.Response(200, content=_HTML)]}
    )

    stats = _run([_ref()], handler)

    assert stats[rpi_images.ERROR] == 1
    assert fake_db.rpi_rows[0]["status"] == rpi_images.ERROR
    assert fake_db.logo_rows[0]["status"] == rpi_images.ERROR


def test_imagem_acima_do_limite_vira_error(
    cfg: Any, fake_db: _FakeDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = dataclasses.replace(cfg, rpi_image_max_bytes=8)
    monkeypatch.setattr(rpi_images, "CONFIG", config)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_JPEG, request=request)

    stats = _run([_ref()], handler)

    assert stats[rpi_images.ERROR] == 1
    assert "limite" in (fake_db.rpi_rows[0]["erro"] or "")


def test_erro_de_rede_mantem_error_para_retry(cfg: Any, fake_db: _FakeDb) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexão recusada", request=request)

    stats = _run([_ref()], handler)

    assert stats[rpi_images.ERROR] == 1
    assert "ConnectError" in (fake_db.rpi_rows[0]["erro"] or "")
    # Cada uma das 3 URLs faz 1 tentativa + 2 retries.
    assert fake_db.rpi_rows[0]["tentativas"] == 9


def test_cache_por_procedencia_sem_codigo_interno(cfg: Any, fake_db: _FakeDb) -> None:
    destino = cfg.data_dir / "raw" / "marcas" / "logos" / "91" / "912345678.jpg"
    destino.parent.mkdir(parents=True)
    destino.write_bytes(_JPEG)
    fake_db.rpi_cache[("2910", "912345678")] = {
        "numero_rpi": "2910",
        "numero_processo": "912345678",
        "status": rpi_images.OK,
        "arquivo": "raw/marcas/logos/91/912345678.jpg",
        "mime": "image/jpeg",
        "origem_url": f"{_RPI}/rpi/images/2910/912345678.jpg",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"não deveria baixar: {request.url}")

    stats = _run([_ref(codigo_interno=None)], handler)

    assert stats[rpi_images.OK] == 1
    row = fake_db.rpi_rows[0]
    assert row["origem_url"] == f"{_RPI}/rpi/images/2910/912345678.jpg"
    assert row["arquivo"] == "raw/marcas/logos/91/912345678.jpg"
    assert fake_db.logo_rows == []


def test_cache_por_procedencia_espelha_logo_quando_codigo_aparece(
    cfg: Any, fake_db: _FakeDb
) -> None:
    destino = cfg.data_dir / "raw" / "marcas" / "logos" / "44" / "4482935.jpg"
    destino.parent.mkdir(parents=True)
    destino.write_bytes(_JPEG)
    fake_db.rpi_cache[("2910", "912345678")] = {
        "numero_rpi": "2910",
        "numero_processo": "912345678",
        "status": rpi_images.OK,
        "arquivo": "raw/marcas/logos/44/4482935.jpg",
        "mime": "image/jpeg",
        "origem_url": f"{_ALL}/912345678.jpg",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"não deveria baixar: {request.url}")

    stats = _run([_ref()], handler)

    assert stats[rpi_images.OK] == 1
    assert fake_db.logo_rows[0]["codigo_interno"] == "4482935"
    assert fake_db.logo_rows[0]["status"] == rpi_images.OK
    assert fake_db.logo_rows[0]["arquivo"] == "raw/marcas/logos/44/4482935.jpg"


def test_cache_local_evita_download(cfg: Any, fake_db: _FakeDb) -> None:
    destino = cfg.data_dir / "raw" / "marcas" / "logos" / "44" / "4482935.jpg"
    destino.parent.mkdir(parents=True)
    destino.write_bytes(_JPEG)
    fake_db.logo_cache["4482935"] = {
        "codigo_interno": "4482935",
        "arquivo": "raw/marcas/logos/44/4482935.jpg",
        "mime": "image/jpeg",
        "status": rpi_images.OK,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"não deveria baixar: {request.url}")

    stats = _run([_ref()], handler)

    assert stats[rpi_images.OK] == 1
    row = fake_db.rpi_rows[0]
    assert row["origem_url"] == "cache"
    assert row["arquivo"] == "raw/marcas/logos/44/4482935.jpg"
    assert row["sha256"] == hashlib.sha256(_JPEG).hexdigest()


def test_force_ignora_cache_local(cfg: Any, fake_db: _FakeDb) -> None:
    destino = cfg.data_dir / "raw" / "marcas" / "logos" / "44" / "4482935.jpg"
    destino.parent.mkdir(parents=True)
    destino.write_bytes(b"antigo")
    fake_db.logo_cache["4482935"] = {
        "codigo_interno": "4482935",
        "arquivo": "raw/marcas/logos/44/4482935.jpg",
        "mime": "image/jpeg",
        "status": rpi_images.OK,
    }
    handler = _sequence(
        {f"{_ALL}/912345678.jpg": [httpx.Response(200, content=_JPEG)]}
    )

    stats = _run([_ref()], handler, force=True)

    assert stats[rpi_images.OK] == 1
    assert fake_db.rpi_rows[0]["origem_url"] == f"{_ALL}/912345678.jpg"
    assert destino.read_bytes() == _JPEG


def test_nao_sobrescreve_logo_ok_com_erro(cfg: Any, fake_db: _FakeDb) -> None:
    fake_db.logo_cache["4482935"] = {
        "codigo_interno": "4482935",
        "arquivo": "raw/marcas/logos/44/4482935.jpg",
        "status": rpi_images.OK,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    stats = _run([_ref()], handler)

    assert stats[rpi_images.SEM_IMAGEM] == 1
    assert fake_db.logo_rows == []


def test_persistencia_de_procedencia_nao_derruba_lote(
    cfg: Any, fake_db: _FakeDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(**kwargs: Any) -> None:
        raise RuntimeError("banco indisponível")

    monkeypatch.setattr(rpi_images.db, "upsert_rpi_imagem", explode)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_JPEG, request=request)

    stats = _run([_ref()], handler)
    assert stats[rpi_images.OK] == 1


def test_download_refs_vazio_nao_cria_cliente(cfg: Any) -> None:
    assert asyncio.run(rpi_images.download_refs([])) == {
        rpi_images.OK: 0,
        rpi_images.SEM_IMAGEM: 0,
        rpi_images.ERROR: 0,
    }


def test_download_sem_codigo_interno_nao_grava_marcas_logos(
    cfg: Any, fake_db: _FakeDb
) -> None:
    handler = _sequence(
        {f"{_ALL}/912345678.jpg": [httpx.Response(200, content=_JPEG)]}
    )

    stats = _run([_ref(codigo_interno=None)], handler)

    assert stats[rpi_images.OK] == 1
    assert len(fake_db.rpi_rows) == 1
    assert fake_db.logo_rows == []
    # Sem código interno, o arquivo usa o número do processo como chave.
    assert fake_db.rpi_rows[0]["arquivo"].endswith("/91/912345678.jpg")
