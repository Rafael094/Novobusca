"""Testes dos parsers da RPI (``ingestion.rpi_parse``) e da montagem das linhas.

Os parsers são puros (só stdlib), então não precisam de banco nem de rede:
alimentamos com fixtures estruturalmente fiéis aos arquivos oficiais do INPI
(XML de Marcas e TXT INID de Patentes).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

# O pacote ``ingestion`` vive na raiz do monorepo (fora de ``backend/``). Ele é
# deliberadamente autônomo (não importa ``app``), então basta pôr a raiz no path.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ingestion.rpi_parse import (  # noqa: E402
    only_digits,
    parse_date_br,
    parse_marcas_xml,
    parse_patentes_txt,
)

_FIXTURES = Path(__file__).parent / "fixtures"
_MARCAS_XML = _FIXTURES / "rpi_marcas_2910.xml"
_PATENTES_TXT = _FIXTURES / "rpi_patentes_2910.txt"


# --- Marcas (XML) -----------------------------------------------------------
def test_parse_marcas_xml_cabecalho() -> None:
    revista = parse_marcas_xml(_MARCAS_XML.read_bytes())
    assert revista.numero == "2910"
    assert revista.data == date(2026, 10, 13)
    assert len(revista.processos) == 3


def test_parse_marcas_xml_campos_do_processo() -> None:
    proc = parse_marcas_xml(_MARCAS_XML.read_bytes()).processos[0]
    assert proc.numero == "922437041"
    assert proc.data_deposito == date(2012, 1, 12)
    assert proc.data_concessao == date(2013, 5, 7)
    assert proc.data_vigencia == date(2023, 5, 7)
    assert proc.apresentacao == "Mista"
    assert proc.natureza == "De Produto"
    assert proc.marca_nome == "MAGU"
    assert proc.titulares == ["ISABELA LIMA BRAZ GUEDES"]
    assert [d.codigo for d in proc.despachos] == ["IPAS158"]
    assert proc.despachos[0].nome == "Concessão de registro"
    assert proc.despachos[0].complemento is None


def test_parse_marcas_xml_varios_despachos_e_complemento() -> None:
    proc = parse_marcas_xml(_MARCAS_XML.read_bytes()).processos[1]
    assert proc.numero == "939393107"
    assert len(proc.titulares) == 2
    assert [d.codigo for d in proc.despachos] == ["IPAS009", "IPAS423"]
    assert proc.despachos[0].complemento == "Imagem da Marca alterada."
    assert proc.despachos[1].nome == "Notificação de oposição"


def test_parse_marcas_xml_processo_sem_detalhes() -> None:
    proc = parse_marcas_xml(_MARCAS_XML.read_bytes()).processos[2]
    assert proc.numero == "999999999"
    assert proc.apresentacao is None
    assert proc.titulares == []
    assert [d.codigo for d in proc.despachos] == ["IPAS085"]


def test_parse_marcas_xml_respeita_encoding_declarado() -> None:
    xml = (
        '<?xml version="1.0" encoding="ISO-8859-1" ?>'
        '<revista numero="1" data="01/01/2020">'
        '<processo numero="123456789">'
        '<despachos><despacho codigo="IPAS005" nome="Exigência formal"/></despachos>'
        '<marca apresentacao="Nominativa" natureza="De Produto"><nome>Ação</nome></marca>'
        "</processo></revista>"
    )
    revista = parse_marcas_xml(xml.encode("latin-1"))
    assert revista.processos[0].marca_nome == "Ação"
    assert revista.processos[0].despachos[0].nome == "Exigência formal"


def test_parse_marcas_xml_vazio_nao_quebra() -> None:
    assert parse_marcas_xml(b"").processos == []
    assert parse_marcas_xml(b"<revista numero='9' data='01/02/2020'></revista>").numero == "9"


# --- Patentes (TXT) ---------------------------------------------------------
def _patentes_bytes() -> bytes:
    # O arquivo oficial é latin-1; o fixture está em UTF-8 no disco.
    return _PATENTES_TXT.read_text(encoding="utf-8").encode("latin-1")


def test_parse_patentes_txt_registros() -> None:
    registros = parse_patentes_txt(_patentes_bytes())
    assert len(registros) == 3

    primeiro = registros[0]
    assert primeiro.despacho_codigo == "3.1"
    assert primeiro.numero == "BR 10 2020 000000-0"
    assert primeiro.data_deposito == date(2020, 1, 1)
    assert primeiro.complemento is None

    segundo = registros[1]
    assert segundo.despacho_codigo == "8.6"
    assert segundo.numero == "BR 10 2015 000000-0"
    assert segundo.complemento == "Arquivamento por falta de pagamento da anuidade"

    terceiro = registros[2]
    assert terceiro.despacho_codigo == "16.1"
    assert terceiro.numero == "PI 0000000-0"
    assert terceiro.complemento == "Concessão de patente"


def test_parse_patentes_txt_aceita_str_e_bytes() -> None:
    texto = _PATENTES_TXT.read_text(encoding="utf-8")
    assert len(parse_patentes_txt(texto)) == 3
    assert len(parse_patentes_txt(_patentes_bytes())) == 3


def test_parse_patentes_txt_aceita_iteravel_de_linhas() -> None:
    # Caminho em streaming (linhas já decodificadas, ex.: TextIOWrapper do ZIP).
    texto = _PATENTES_TXT.read_text(encoding="utf-8")
    assert len(parse_patentes_txt(texto.splitlines())) == 3


def test_parse_marcas_xml_aceita_stream_binario() -> None:
    # Caminho em streaming (ex.: membro do ZIP aberto), sem carregar tudo em bytes.
    with _MARCAS_XML.open("rb") as fh:
        revista = parse_marcas_xml(fh)
    assert len(revista.processos) == 3
    assert revista.numero == "2910"


def test_parse_patentes_txt_vazio_nao_quebra() -> None:
    assert parse_patentes_txt(b"") == []
    assert parse_patentes_txt("cabecalho sem (Cd)\n(21) BR 10 2020 000000-0\n") == []


def test_parse_patentes_txt_ignora_cabecalhos() -> None:
    registros = parse_patentes_txt(_patentes_bytes())
    assert all(r.despacho_codigo for r in registros)
    assert all("Publicação do Pedido" not in r.despacho_codigo for r in registros)


# --- Utilidades -------------------------------------------------------------
@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("BR 10 2020 000000-0", "1020200000000"),
        ("PI 0000000-0", "00000000"),
        ("922437041", "922437041"),
        (None, ""),
        ("", ""),
    ],
)
def test_only_digits(entrada, esperado) -> None:
    assert only_digits(entrada) == esperado


def test_parse_date_br() -> None:
    assert parse_date_br("13/10/2026") == date(2026, 10, 13)
    assert parse_date_br("31/02/2021") is None  # data inválida
    assert parse_date_br("") is None
    assert parse_date_br(None) is None


# --- Montagem das linhas de despacho ---------------------------------------
def test_marcas_rows_casa_e_expande_por_codigo() -> None:
    from ingestion.rpi import marcas_rows

    revista = parse_marcas_xml(_MARCAS_XML.read_bytes())
    # Só os dois primeiros processos existem no banco; o terceiro é ignorado.
    codigos = {"922437041": ["4482935"], "939393107": ["6248375", "6248400"]}
    rows = marcas_rows(revista.processos, codigos)

    # 1 + (2 despachos × 2 códigos) = 5 linhas.
    assert len(rows) == 5
    assert {r["codigo_interno"] for r in rows} == {"4482935", "6248375", "6248400"}
    assert all(r["numero_inpi"] != "999999999" for r in rows)

    do_009 = [r for r in rows if r["codigo_despacho"] == "IPAS009"]
    assert len(do_009) == 2
    assert all(r["complemento_despacho"] == "Imagem da Marca alterada." for r in do_009)


def test_patentes_rows_casa_por_digitos() -> None:
    from ingestion.rpi import patentes_rows

    registros = parse_patentes_txt(_patentes_bytes())
    digitos = {
        "1020200000000": ("pat-1", "BR102020000000"),
        "00000000": ("pat-2", "PI0000000"),
    }
    rows = patentes_rows(registros, digitos)

    assert len(rows) == 2
    assert rows[0]["codigo_interno"] == "pat-1"
    assert rows[0]["numero_inpi"] == "BR102020000000"
    assert rows[0]["codigo_despacho"] == "3.1"
    assert rows[1]["codigo_interno"] == "pat-2"
    assert rows[1]["complemento_despacho"] == "Concessão de patente"


def test_patentes_rows_ignora_sem_match() -> None:
    from ingestion.rpi import patentes_rows

    registros = parse_patentes_txt(_patentes_bytes())
    assert patentes_rows(registros, {}) == []
