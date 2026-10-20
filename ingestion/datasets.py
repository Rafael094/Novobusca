"""Catalog of the official INPI open datasets.

Every URL below was verified against the live portal
(https://dadosabertos.inpi.gov.br/) at build time. The listing pattern is::

    <base>/download/<category>/<FILE>

Categories: ``marcas``, ``patentes``, ``desenhos_industriais``,
``contratos``, ``programas_de_computador`` and the ``rpi`` (Revista da
Propriedade Industrial).

The pipeline currently focuses on **Marcas** and **Patentes** (the two modules
exposed by the application), but the catalog is intentionally declarative so new
datasets can be added without touching the pipeline code.

The ``rpi`` (Revista da Propriedade Industrial) is **not** a bulk dataset here:
it is published weekly and consumed as a *delta* by ``ingestion.rpi`` (which
updates ``marcas_despachos``/``patentes_despachos`` directly from the edition's
XML/TXT), so it deliberately has no :class:`DatasetSpec`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DatasetSpec:
    """Declarative description of a single downloadable dataset.

    ``name`` is the stable identifier persisted in ``inpi_dataset.name`` and is
    also the on-disk base name. ``path`` is the path relative to the base URL.
    ``target_table`` is the local PostgreSQL table the dataset is loaded into
    (``None`` means the dataset is downloaded but not bulk-loaded — e.g. the
    aggregate ``.zip`` bundles that duplicate the split CSVs).
    """

    name: str
    category: str
    path: str
    kind: str  # "csv" | "zip"
    target_table: str | None = None
    description: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def is_csv(self) -> bool:
        return self.kind == "csv"

    @property
    def is_zip(self) -> bool:
        return self.kind == "zip"


# --- Marcas -----------------------------------------------------------------
# NOTE: marcas.zip (2.4 GB) is the aggregate bundle; the split CSVs below are
# the ones actually imported (1:1 with tables) to avoid parsing the same rows
# twice.
MARCAS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        name="marcas",
        category="marcas",
        path="/download/marcas/marcas.zip",
        kind="zip",
        target_table=None,
        description="Bundle agregado de Marcas (contém os CSVs abaixo).",
    ),
    DatasetSpec(
        name="marcas_dados_bibliograficos",
        category="marcas",
        path="/download/marcas/MARCAS_DADOS_BIBLIOGRAFICOS.csv",
        kind="csv",
        target_table="marcas",
        description="Dados bibliográficos dos pedidos de marca.",
    ),
    DatasetSpec(
        name="marcas_depositantes",
        category="marcas",
        path="/download/marcas/MARCAS_DEPOSITANTES.csv",
        kind="csv",
        target_table="marcas_depositantes",
        description="Depositantes/titulares das marcas.",
    ),
    DatasetSpec(
        name="marcas_classificacoes_nacionais",
        category="marcas",
        path="/download/marcas/MARCAS_CLASSIFICACOES_NACIONAIS.csv",
        kind="csv",
        target_table="marcas_classificacoes_nacionais",
        description="Classificação nacional de produtos/serviços.",
    ),
    DatasetSpec(
        name="marcas_classificacoes_nice",
        category="marcas",
        path="/download/marcas/MARCAS_CLASSIFICACOES_NICE.csv",
        kind="csv",
        target_table="marcas_classificacoes_nice",
        description="Classificação de Nice das marcas.",
    ),
    DatasetSpec(
        name="marcas_classificacoes_viena",
        category="marcas",
        path="/download/marcas/MARCAS_CLASSIFICACOES_VIENA.csv",
        kind="csv",
        target_table="marcas_classificacoes_viena",
        description="Classificação de Viena (elementos figurativos).",
    ),
    DatasetSpec(
        name="marcas_despachos",
        category="marcas",
        path="/download/marcas/MARCAS_DESPACHOS.csv",
        kind="csv",
        target_table="marcas_despachos",
        description="Despachos publicados (RPI) para os pedidos de marca.",
    ),
)


# --- Patentes ---------------------------------------------------------------
PATENTES: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        name="patentes",
        category="patentes",
        path="/download/patentes/patentes.zip",
        kind="zip",
        target_table=None,
        description="Bundle agregado de Patentes (contém os CSVs abaixo).",
    ),
    DatasetSpec(
        name="patentes_dados_bibliograficos",
        category="patentes",
        path="/download/patentes/PATENTES_DADOS_BIBLIOGRAFICOS.csv",
        kind="csv",
        target_table="patentes",
        description="Dados bibliográficos dos pedidos de patente.",
    ),
    DatasetSpec(
        name="patentes_conteudo",
        category="patentes",
        path="/download/patentes/PATENTES_CONTEUDO.csv",
        kind="csv",
        target_table="patentes_conteudo",
        description="Título e resumo do conteúdo técnico dos pedidos.",
    ),
    DatasetSpec(
        name="patentes_depositantes",
        category="patentes",
        path="/download/patentes/PATENTES_DEPOSITANTES.csv",
        kind="csv",
        target_table="patentes_depositantes",
        description="Depositantes/titulares das patentes.",
    ),
    DatasetSpec(
        name="patentes_inventores",
        category="patentes",
        path="/download/patentes/PATENTES_INVENTORES.csv",
        kind="csv",
        target_table="patentes_inventores",
        description="Inventores nomeados nos pedidos.",
    ),
    DatasetSpec(
        name="patentes_classificacao_ipc",
        category="patentes",
        path="/download/patentes/PATENTES_CLASSIFICACAO_IPC.csv",
        kind="csv",
        target_table="patentes_classificacao_ipc",
        description="Classificação IPC.",
    ),
    DatasetSpec(
        name="patentes_despachos",
        category="patentes",
        path="/download/patentes/PATENTES_DESPACHOS.csv",
        kind="csv",
        target_table="patentes_despachos",
        description="Despachos publicados para os pedidos.",
    ),
    DatasetSpec(
        name="patentes_prioridades",
        category="patentes",
        path="/download/patentes/PATENTES_PRIORIDADES.csv",
        kind="csv",
        target_table="patentes_prioridades",
        description="Prioridades unionistas reivindicadas.",
    ),
    DatasetSpec(
        name="patentes_renumeracoes",
        category="patentes",
        path="/download/patentes/PATENTES_RENUMERACOES.csv",
        kind="csv",
        target_table="patentes_renumeracoes",
        description="Renumerações de pedidos.",
    ),
    DatasetSpec(
        name="patentes_procuradores",
        category="patentes",
        path="/download/patentes/PATENTES_PROCURADORES.csv",
        kind="csv",
        target_table="patentes_procuradores",
        description="Procuradores dos pedidos.",
    ),
    DatasetSpec(
        name="patentes_vinculos",
        category="patentes",
        path="/download/patentes/PATENTES_VINCULOS.csv",
        kind="csv",
        target_table="patentes_vinculos",
        description="Vínculos entre pedidos (divisões, etc.).",
    ),
)


# --- Desenhos Industriais ---------------------------------------------------
# Verified against https://dadosabertos.inpi.gov.br/index/desenhos_industriais/.
# The DI_FIGURAS_*.ZIP bundles (3.7 GB + 18.7 GB + 22.0 GB) are the design
# images. They are intentionally ``target_table=None``: far too large to bulk
# store on the Oracle Free Tier VM, they follow the same on-demand/worker image
# strategy as the marca logotipos (``desenhos_figuras`` holds only metadata).
DESENHOS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        name="desenhos_industriais",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/desenhos_industriais.zip",
        kind="zip",
        target_table=None,
        description="Bundle agregado de Desenhos Industriais (contém os CSVs abaixo).",
    ),
    DatasetSpec(
        name="di_dados_bibliograficos",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_DADOS_BIBLIOGRAFICOS.csv",
        kind="csv",
        target_table="desenhos",
        description="Dados bibliográficos dos pedidos de desenho industrial.",
    ),
    DatasetSpec(
        name="di_conteudo",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_CONTEUDO.csv",
        kind="csv",
        target_table="desenhos_conteudo",
        description="Título/campo de aplicação/descrição do objeto.",
    ),
    DatasetSpec(
        name="di_depositantes",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_DEPOSITANTES.csv",
        kind="csv",
        target_table="desenhos_depositantes",
        description="Depositantes/titulares dos desenhos.",
    ),
    DatasetSpec(
        name="di_autores",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_AUTORES.csv",
        kind="csv",
        target_table="desenhos_autores",
        description="Autores (designers) dos desenhos.",
    ),
    DatasetSpec(
        name="di_procuradores",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_PROCURADORES.csv",
        kind="csv",
        target_table="desenhos_procuradores",
        description="Procuradores dos pedidos.",
    ),
    DatasetSpec(
        name="di_classificacoes",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_CLASSIFICACOES.csv",
        kind="csv",
        target_table="desenhos_classificacoes",
        description="Classificação de Locarno.",
    ),
    DatasetSpec(
        name="di_prioridades",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_PRIORIDADES.csv",
        kind="csv",
        target_table="desenhos_prioridades",
        description="Prioridades unionistas reivindicadas.",
    ),
    DatasetSpec(
        name="di_despachos",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_DESPACHOS.csv",
        kind="csv",
        target_table="desenhos_despachos",
        description="Despachos publicados (RPI) para os pedidos.",
    ),
    DatasetSpec(
        name="di_vinculos",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_VINCULOS.csv",
        kind="csv",
        target_table="desenhos_vinculos",
        description="Vínculos entre pedidos (divisões, etc.).",
    ),
    # Figure bundles — downloaded on the server but NOT bulk-loaded (images).
    DatasetSpec(
        name="di_figuras_buscaweb_1997_2016",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_FIGURAS_BUSCAWEB_1997-2016.ZIP",
        kind="zip",
        target_table=None,
        description="Figuras dos desenhos (1997-2016). Imagens — não carregadas em tabela.",
    ),
    DatasetSpec(
        name="di_figuras_geradoc_2017_2023",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_FIGURAS_GERADOC_2017-2023.ZIP",
        kind="zip",
        target_table=None,
        description="Figuras dos desenhos (2017-2023). Imagens — não carregadas em tabela.",
    ),
    DatasetSpec(
        name="di_figuras_ipas_2023_hoje",
        category="desenhos_industriais",
        path="/download/desenhos_industriais/DI_FIGURAS_IPAS_2023-HOJE.ZIP",
        kind="zip",
        target_table=None,
        description="Figuras dos desenhos (2023-hoje). Imagens — não carregadas em tabela.",
    ),
)


# --- Programas de Computador (software) -------------------------------------
# Verified against https://dadosabertos.inpi.gov.br/index/programas_de_computador/.
SOFTWARE: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        name="programas_de_computador",
        category="programas_de_computador",
        path="/download/programas_de_computador/programas_de_computador.zip",
        kind="zip",
        target_table=None,
        description="Bundle agregado de Programas de Computador (contém os CSVs abaixo).",
    ),
    DatasetSpec(
        name="prog_comp_dados_basicos",
        category="programas_de_computador",
        path="/download/programas_de_computador/PROG_COMP_DADOS_BASICOS.csv",
        kind="csv",
        target_table="softwares",
        description="Dados básicos dos registros de programa de computador.",
    ),
    DatasetSpec(
        name="prog_comp_titular",
        category="programas_de_computador",
        path="/download/programas_de_computador/PROG_COMP_TITULAR.csv",
        kind="csv",
        target_table="softwares_titulares",
        description="Titulares dos registros.",
    ),
    DatasetSpec(
        name="prog_comp_autores",
        category="programas_de_computador",
        path="/download/programas_de_computador/PROG_COMP_AUTORES.csv",
        kind="csv",
        target_table="softwares_autores",
        description="Autores (criadores) dos programas.",
    ),
    DatasetSpec(
        name="prog_comp_linguagem",
        category="programas_de_computador",
        path="/download/programas_de_computador/PROG_COMP_LINGUAGEM.csv",
        kind="csv",
        target_table="softwares_linguagens",
        description="Linguagens de programação declaradas.",
    ),
    DatasetSpec(
        name="prog_comp_tipo",
        category="programas_de_computador",
        path="/download/programas_de_computador/PROG_COMP_TIPO.csv",
        kind="csv",
        target_table="softwares_tipos",
        description="Tipo/campo de aplicação do programa.",
    ),
    DatasetSpec(
        name="prog_comp_campos",
        category="programas_de_computador",
        path="/download/programas_de_computador/PROG_COMP_CAMPOS.csv",
        kind="csv",
        target_table="softwares_campos",
        description="Campos descritivos do programa.",
    ),
    DatasetSpec(
        name="prog_comp_despachos",
        category="programas_de_computador",
        path="/download/programas_de_computador/PROG_COMP_DESPACHOS.csv",
        kind="csv",
        target_table="softwares_despachos",
        description="Despachos publicados (RPI) para os pedidos.",
    ),
)


ALL: tuple[DatasetSpec, ...] = MARCAS + PATENTES + DESENHOS + SOFTWARE
BY_NAME: dict[str, DatasetSpec] = {spec.name: spec for spec in ALL}
BY_CATEGORY: dict[str, tuple[DatasetSpec, ...]] = {
    "marcas": MARCAS,
    "patentes": PATENTES,
    "desenhos_industriais": DESENHOS,
    "programas_de_computador": SOFTWARE,
}


def resolve(targets: list[str] | None) -> list[DatasetSpec]:
    """Resolve CLI/router targets (categories and/or dataset names) to specs.

    ``targets`` may contain category names (``marcas``, ``patentes``) and/or
    individual dataset names. ``None`` / empty means every dataset.
    """
    if not targets:
        return list(ALL)

    seen: dict[str, DatasetSpec] = {}
    for target in targets:
        if target in BY_CATEGORY:
            for spec in BY_CATEGORY[target]:
                seen[spec.name] = spec
        elif target in BY_NAME:
            spec = BY_NAME[target]
            seen[spec.name] = spec
        else:
            raise KeyError(f"Unknown dataset/category: {target!r}")
    return list(seen.values())
