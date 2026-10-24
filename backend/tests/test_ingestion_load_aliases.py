"""Testes do mapeamento de colunas do carregador de dados abertos.

Os CSVs oficiais de Desenhos Industriais e Programas de Computador usam nomes
de coluna diferentes dos modelos ORM (``titulo_programa``, ``nome_titular``,
``numero_despacho`` etc.). O mapa de aliases evita que o carregador descarte
esses campos silenciosamente.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ingestion.load import COLUMN_ALIASES, _match_columns  # noqa: E402


def _table_columns(names: list[str]) -> dict[str, str]:
    return {name: name for name in names}


@pytest.mark.parametrize(
    ("dataset", "csv_columns", "table_columns", "expected"),
    [
        (
            "di_depositantes",
            [
                "codigo_interno",
                "numero_inpi",
                "ordem",
                "depositante",
                "cgccpfdepositante",
                "tipopessoadepositante",
                "pais",
                "estado",
            ],
            [
                "codigo_interno",
                "numero_inpi",
                "ordem",
                "nome",
                "cpf_cnpj",
                "tipo_pessoa",
                "pais",
                "estado",
            ],
            [
                "codigo_interno",
                "numero_inpi",
                "ordem",
                "nome",
                "cpf_cnpj",
                "tipo_pessoa",
                "pais",
                "estado",
            ],
        ),
        (
            "di_procuradores",
            [
                "codigo_interno",
                "numero_inpi",
                "procurador",
                "cgccpfprocurador",
                "tipopessoaprocurador",
            ],
            [
                "codigo_interno",
                "numero_inpi",
                "procurador",
                "cpf_cnpj",
                "tipo_pessoa",
            ],
            [
                "codigo_interno",
                "numero_inpi",
                "procurador",
                "cpf_cnpj",
                "tipo_pessoa",
            ],
        ),
        (
            "di_classificacoes",
            [
                "codigo_interno",
                "numero_inpi",
                "simbolo",
                "classificacao",
                "ordem",
                "versao",
            ],
            [
                "codigo_interno",
                "numero_inpi",
                "classificacao_locarno",
                "descricao_locarno",
                "ordem",
            ],
            [
                "codigo_interno",
                "numero_inpi",
                "classificacao_locarno",
                "descricao_locarno",
                "ordem",
            ],
        ),
        (
            "prog_comp_dados_basicos",
            ["codigo_interno", "numero_inpi", "data_deposito", "titulo_programa"],
            ["codigo_interno", "numero_inpi", "data_deposito", "titulo"],
            ["codigo_interno", "numero_inpi", "data_deposito", "titulo"],
        ),
        (
            "prog_comp_titular",
            [
                "codigo_interno",
                "numero_inpi",
                "nome_titular",
                "data_inicio_titular",
                "data_fim_titular",
                "cnpj_cpf_titular",
                "pais",
                "estado",
            ],
            [
                "codigo_interno",
                "numero_inpi",
                "nome",
                "cpf_cnpj",
                "pais",
                "estado",
            ],
            [
                "codigo_interno",
                "numero_inpi",
                "nome",
                "cpf_cnpj",
                "pais",
                "estado",
            ],
        ),
        (
            "prog_comp_autores",
            ["codigo_interno", "numero_inpi", "nome_autor"],
            ["codigo_interno", "numero_inpi", "autor"],
            ["codigo_interno", "numero_inpi", "autor"],
        ),
        (
            "prog_comp_tipo",
            ["codigo_interno", "numero_inpi", "codigo_tipo", "descricao_tipo"],
            ["codigo_interno", "numero_inpi", "tipo", "campo_aplicacao"],
            ["codigo_interno", "numero_inpi", "tipo", "campo_aplicacao"],
        ),
        (
            "prog_comp_campos",
            ["codigo_interno", "numero_inpi", "codigo_campo", "descricao_campo"],
            ["codigo_interno", "numero_inpi", "campo", "valor"],
            ["codigo_interno", "numero_inpi", "campo", "valor"],
        ),
        (
            "prog_comp_despachos",
            [
                "codigo_interno",
                "numero_inpi",
                "numero_rpi",
                "data_rpi",
                "numero_despacho",
                "descricao_despacho",
                "complemento_despacho",
            ],
            [
                "codigo_interno",
                "numero_inpi",
                "numero_rpi",
                "data_rpi",
                "codigo_despacho",
                "descricao_despacho",
                "complemento_despacho",
            ],
            [
                "codigo_interno",
                "numero_inpi",
                "numero_rpi",
                "data_rpi",
                "codigo_despacho",
                "descricao_despacho",
                "complemento_despacho",
            ],
        ),
    ],
)
def test_dataset_column_aliases(
    dataset: str,
    csv_columns: list[str],
    table_columns: list[str],
    expected: list[str],
) -> None:
    mapped = _match_columns(
        csv_columns,
        _table_columns(table_columns),
        COLUMN_ALIASES.get(dataset, {}),
    )
    assert [target for _, target in mapped] == expected


def test_alias_never_uses_same_target_twice() -> None:
    mapped = _match_columns(
        ["codigo_interno", "numero_inpi", "numero_despacho", "codigo_despacho"],
        _table_columns(["codigo_interno", "numero_inpi", "codigo_despacho"]),
        COLUMN_ALIASES["prog_comp_despachos"],
    )
    assert [target for _, target in mapped] == [
        "codigo_interno",
        "numero_inpi",
        "codigo_despacho",
    ]
