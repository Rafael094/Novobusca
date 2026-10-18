"""Testes de integração do worker da RPI (``ingestion.rpi`` + ``ingestion.db``).

Diferente de ``test_rpi_parse.py`` (parsers puros), aqui exercitamos o caminho
real contra o PostgreSQL de teste: o casamento ``numero_inpi`` → ``codigo_interno``
e a gravação idempotente em ``marcas_despachos``/``patentes_despachos``.

O ``process_edition`` é rodado de ponta a ponta SEM rede: o ``download_edition``
pula o download quando o ZIP já existe em ``rpi_dir``, então basta materializar
um ZIP com o fixture no diretório esperado. ``data_dir`` é redirecionado para um
``tmp_path`` substituindo só ``rpi.CONFIG`` (o ``db.CONFIG`` continua apontando
para o banco de teste).
"""

from __future__ import annotations

import dataclasses
import io
import sys
import zipfile
from datetime import date
from pathlib import Path

import pytest
import requests
from sqlalchemy import func, select

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.models import Marca, MarcaDespacho, Patente, PatenteDespacho  # noqa: E402

from ingestion import db as ing_db  # noqa: E402
from ingestion import rpi as ing_rpi  # noqa: E402

_FIXTURES = Path(__file__).parent / "fixtures"
_MARCAS_XML = _FIXTURES / "rpi_marcas_2910.xml"
_PATENTES_TXT = _FIXTURES / "rpi_patentes_2910.txt"

_RPI = "2910"
_DATA_RPI = date(2026, 10, 13)


def _zip_bytes(name: str, payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(name, payload)
    return buffer.getvalue()


@pytest.fixture()
def rpi_tmp(tmp_path, monkeypatch) -> Path:
    """Redireciona o ``rpi_dir`` do worker para um diretório temporário."""
    monkeypatch.setattr(ing_rpi, "CONFIG", dataclasses.replace(ing_rpi.CONFIG, data_dir=tmp_path))
    ing_rpi.CONFIG.rpi_dir.mkdir(parents=True, exist_ok=True)
    return ing_rpi.CONFIG.rpi_dir


# --- Casamento número → codigo_interno --------------------------------------
def test_marcas_codigos_por_numero(db) -> None:
    db.add(Marca(codigo_interno="4482935", numero_inpi="922437041"))
    db.add(Marca(codigo_interno="6248375", numero_inpi="939393107"))
    db.commit()

    mapa = ing_db.marcas_codigos_por_numero(["922437041", "939393107", "000000000"])
    assert mapa == {"922437041": ["4482935"], "939393107": ["6248375"]}


def test_patentes_digitos_map_normaliza_formato(db) -> None:
    db.add(Patente(codigo_interno="pat-1", numero_inpi="BR 10 2020 000000-0"))
    db.add(Patente(codigo_interno="pat-2", numero_inpi="PI 0000000-0"))
    db.commit()

    mapa = ing_db.patentes_digitos_map()
    assert mapa["1020200000000"] == ("pat-1", "BR 10 2020 000000-0")
    assert mapa["00000000"] == ("pat-2", "PI 0000000-0")


# --- Idempotência da gravação ----------------------------------------------
def test_insert_marcas_despachos_e_idempotente(db) -> None:
    rows = [
        {
            "codigo_interno": "4482935",
            "numero_inpi": "922437041",
            "codigo_despacho": "IPAS158",
            "descricao_despacho": "Concessão de registro",
            "complemento_despacho": None,
        },
        {
            "codigo_interno": "4482935",
            "numero_inpi": "922437041",
            "codigo_despacho": "IPAS009",
            "descricao_despacho": "Publicação de pedido",
            "complemento_despacho": "Imagem alterada.",
        },
    ]

    assert ing_db.insert_marcas_despachos(numero_rpi=_RPI, data_rpi=_DATA_RPI, rows=rows) == 2
    # Rodar de novo não duplica (anti-join).
    assert ing_db.insert_marcas_despachos(numero_rpi=_RPI, data_rpi=_DATA_RPI, rows=rows) == 0

    db.commit()
    total = db.execute(select(func.count()).select_from(MarcaDespacho)).scalar()
    assert total == 2
    got = db.execute(select(MarcaDespacho.numero_rpi)).scalars().all()
    assert set(got) == {_RPI}


def test_insert_patentes_despachos_e_idempotente(db) -> None:
    rows = [
        {
            "codigo_interno": "pat-1",
            "numero_inpi": "BR 10 2020 000000-0",
            "codigo_despacho": "3.1",
            "complemento_despacho": None,
        }
    ]
    assert ing_db.insert_patentes_despachos(numero_rpi=_RPI, data_rpi=_DATA_RPI, rows=rows) == 1
    assert ing_db.insert_patentes_despachos(numero_rpi=_RPI, data_rpi=_DATA_RPI, rows=rows) == 0

    db.commit()
    assert db.execute(select(func.count()).select_from(PatenteDespacho)).scalar() == 1


def test_insert_marcas_despachos_conserva_o_que_ja_veio_do_csv(db) -> None:
    """Um despacho idêntico vindo do CSV aberto não é duplicado pelo worker."""
    db.add(
        MarcaDespacho(
            codigo_interno="4482935",
            numero_inpi="922437041",
            numero_rpi=_RPI,
            data_rpi=_DATA_RPI,
            codigo_despacho="IPAS158",
            descricao_despacho="Concessão de registro",
            complemento_despacho=None,
        )
    )
    db.commit()

    rows = [
        {
            "codigo_interno": "4482935",
            "numero_inpi": "922437041",
            "codigo_despacho": "IPAS158",
            "descricao_despacho": "Concessão de registro",
            "complemento_despacho": None,
        },
        {
            "codigo_interno": "4482935",
            "numero_inpi": "922437041",
            "codigo_despacho": "IPAS423",
            "descricao_despacho": "Notificação de oposição",
            "complemento_despacho": None,
        },
    ]
    assert ing_db.insert_marcas_despachos(numero_rpi=_RPI, data_rpi=_DATA_RPI, rows=rows) == 1

    db.commit()
    assert db.execute(select(func.count()).select_from(MarcaDespacho)).scalar() == 2


# --- Estado em inpi_rpi -----------------------------------------------------
def test_upsert_e_get_rpi_preserva_metadata(db) -> None:
    ing_db.upsert_rpi(
        number=_RPI,
        edition_date=None,
        status="PROCESSING",
        meta={"sections": {"marcas": {"status": "PROCESSED", "despachos_novos": 5}}},
    )
    row = ing_db.get_rpi(_RPI)
    assert row is not None
    assert row["status"] == "PROCESSING"
    assert row["metadata"]["sections"]["marcas"]["despachos_novos"] == 5


def test_upsert_rpi_funciona_sem_a_constraint_unica() -> None:
    """Regressão do bug de produção: o banco estava sem `uq_inpi_rpi_number`.

    Com o `ON CONFLICT (number)` antigo, a primeira gravação do worker falhava com
    ``InvalidColumnReference``. O upsert tem de funcionar mesmo num schema
    divergente (é justamente o caso de um restore/dump antigo).

    Não usa a fixture ``db`` de propósito: uma sessão ORM aberta segura um
    ``ACCESS SHARE`` que travaria o ``ALTER TABLE`` que devolve a constraint.
    """
    from sqlalchemy import text

    from app.db import engine

    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE inpi_rpi DROP CONSTRAINT IF EXISTS uq_inpi_rpi_number")
        )
        conn.execute(text("DROP INDEX IF EXISTS uq_inpi_rpi_number"))

    try:
        ing_db.upsert_rpi(number="9999", status="DISCOVERED", meta={"sections": {}})
        ing_db.upsert_rpi(
            number="9999", status="PROCESSED", meta={"sections": {"marcas": {}}}
        )

        row = ing_db.get_rpi("9999")
        assert row is not None
        assert row["status"] == "PROCESSED"
        assert row["metadata"]["sections"] == {"marcas": {}}

        with engine.connect() as conn:
            total = conn.execute(
                text("SELECT count(*) FROM inpi_rpi WHERE number = '9999'")
            ).scalar()
        assert total == 1  # atualiza, não duplica
    finally:
        # Devolve o schema ao estado do Alembic para o resto da suíte.
        with engine.begin() as conn:
            conn.execute(text("DROP INDEX IF EXISTS uq_inpi_rpi_number"))
            conn.execute(
                text(
                    "ALTER TABLE inpi_rpi ADD CONSTRAINT uq_inpi_rpi_number"
                    " UNIQUE (number)"
                )
            )


# --- Fluxo completo de uma edição ------------------------------------------
def test_process_edition_marcas_ponta_a_ponta(db, rpi_tmp) -> None:
    db.add(Marca(codigo_interno="4482935", numero_inpi="922437041"))
    db.add(Marca(codigo_interno="6248375", numero_inpi="939393107"))
    db.commit()

    (rpi_tmp / "RM2910.zip").write_bytes(
        _zip_bytes("RM2910.xml", _MARCAS_XML.read_bytes())
    )
    edition = ing_rpi.Edition(
        section="marcas",
        numero=_RPI,
        data=_DATA_RPI,
        nome_arquivo_escritorio="RM2910.zip",
    )

    stats = ing_rpi.process_edition(requests.Session(), edition)
    assert stats["status"] == "PROCESSED"
    assert stats["processos"] == 3
    assert stats["casados"] == 2  # o 999999999 não existe no banco
    assert stats["despachos_novos"] == 3  # 1 despacho + 2 despachos

    db.commit()
    assert db.execute(select(func.count()).select_from(MarcaDespacho)).scalar() == 3

    # O estado da seção fica registrado em inpi_rpi.
    row = ing_db.get_rpi(_RPI)
    assert row["status"] == "PROCESSED"
    assert row["metadata"]["sections"]["marcas"]["despachos_novos"] == 3

    # Rodar de novo: a edição já está PROCESSED → nada é baixado/reprocessado.
    assert ing_rpi.process_edition(requests.Session(), edition) == {"status": "SKIPPED"}
    db.commit()
    assert db.execute(select(func.count()).select_from(MarcaDespacho)).scalar() == 3

    # --force reprocessa, mas o anti-join mantém o total.
    assert ing_rpi.process_edition(requests.Session(), edition, force=True)["despachos_novos"] == 0


def test_process_edition_patentes_ponta_a_ponta(db, rpi_tmp) -> None:
    db.add(Patente(codigo_interno="pat-1", numero_inpi="BR 10 2020 000000-0"))
    db.add(Patente(codigo_interno="pat-2", numero_inpi="PI 0000000-0"))
    db.commit()

    payload = _PATENTES_TXT.read_text(encoding="utf-8").encode("latin-1")
    (rpi_tmp / "P2910.zip").write_bytes(_zip_bytes("P2910.txt", payload))
    edition = ing_rpi.Edition(
        section="patentes",
        numero=_RPI,
        data=_DATA_RPI,
        nome_arquivo_escritorio="P2910.zip",
    )

    stats = ing_rpi.process_edition(requests.Session(), edition)
    assert stats["status"] == "PROCESSED"
    assert stats["despachos_novos"] == 2  # o BR 10 2015 não está no banco

    db.commit()
    despachos = db.execute(select(PatenteDespacho)).scalars().all()
    assert {d.codigo_interno for d in despachos} == {"pat-1", "pat-2"}
    assert {d.codigo_despacho for d in despachos} == {"3.1", "16.1"}
    complementos = {d.complemento_despacho for d in despachos}
    assert "Concessão de patente" in complementos


def test_process_edition_sem_arquivo_marca_failed(db, rpi_tmp) -> None:
    """Se nem o ZIP existe nem o download funciona, a edição fica FAILED."""
    edition = ing_rpi.Edition(
        section="marcas",
        numero="2999",
        data=_DATA_RPI,
        nome_arquivo_escritorio=None,  # sem arquivo → ValueError antes de tocar a rede
    )
    stats = ing_rpi.process_edition(requests.Session(), edition)
    assert stats["status"] == "FAILED"
    assert ing_db.get_rpi("2999")["status"] == "FAILED"
