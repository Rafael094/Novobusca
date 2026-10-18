"""Testes do parser da página de detalhe do pePI (``ingestion.pepi_parse``).

O parser é puro (só stdlib), então não precisa de banco nem de rede: alimentamos
com um fixture estruturalmente fiel da página real do processo 4482935.
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

# O pacote ``ingestion`` vive na raiz do monorepo (fora de ``backend/``). Ele é
# deliberadamente autônomo (não importa ``app``), então basta pôr a raiz no path.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ingestion.pepi_parse import (  # noqa: E402
    first_date,
    looks_like_login,
    parse_numero_processo,
    parse_peticoes,
    parse_revista,
    strip_tags,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "pepi_detail_4482935.html"


@pytest.fixture()
def html() -> str:
    return _FIXTURE.read_text(encoding="utf-8")


def test_parse_peticoes_extrai_as_duas_linhas(html: str) -> None:
    rows = parse_peticoes(html)
    assert len(rows) == 2

    first = rows[0]
    assert first["protocolo"] == "800210453297"
    assert first["data_protocolo"] == date(2021, 12, 22)
    assert first["codigo_servico"] == "372"
    assert first["descricao_servico"] is not None
    assert "Primeiro decênio" in first["descricao_servico"]
    assert first["cliente"] == "ISABELA LIMA BRAZ GUEDES"
    assert first["pagamento_conciliado"] is True
    assert first["banco_codigo"] == "077"
    assert first["banco_nome"] == "Banco Intermedium S.A."
    assert first["data_pagamento"] == date(2021, 12, 22)
    assert first["valor_pagamento"] == Decimal("298.0")
    assert first["tem_imagem"] is False

    second = rows[1]
    assert second["protocolo"] == "850210116414"
    assert second["data_protocolo"] == date(2021, 3, 23)
    assert second["codigo_servico"] == "389"
    assert "Pedido de registro" in (second["descricao_servico"] or "")
    assert second["pagamento_conciliado"] is True
    # Linha sem os dados bancários no balão continua válida, só sem pagamento.
    assert second["banco_codigo"] is None
    assert second["valor_pagamento"] is None


def test_parse_peticoes_nao_confunde_despachos(html: str) -> None:
    """Só linhas com ``pgto`` são petições (a tabela de Publicações não entra)."""
    rows = parse_peticoes(html)
    protocolos = {r["protocolo"] for r in rows}
    assert protocolos == {"800210453297", "850210116414"}


def test_parse_revista_le_rodape(html: str) -> None:
    data, numero = parse_revista(html)
    assert data == date(2026, 10, 13)
    assert numero == "2910"


def test_parse_numero_processo(html: str) -> None:
    assert parse_numero_processo(html) == "922437041"


def test_looks_like_login(html: str) -> None:
    assert looks_like_login(html) is False
    assert looks_like_login('<form name="F_LoginCliente" method="post">') is True


def test_html_vazio_nao_quebra() -> None:
    assert parse_peticoes("") == []
    assert parse_peticoes("<html><body>nada</body></html>") == []
    assert parse_revista("") == (None, None)
    assert parse_numero_processo("") is None


def test_strip_tags_e_first_date() -> None:
    assert strip_tags("<b>Olá</b>&nbsp; mundo") == "Olá mundo"
    assert first_date("Data: 22/12/2021 e depois 01/02/2022") == date(2021, 12, 22)
    assert first_date("sem data") is None
    assert first_date("31/02/2021") is None  # data inválida
