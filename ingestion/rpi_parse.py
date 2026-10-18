"""Parsers puros da RPI (Revista da Propriedade Industrial) do INPI.

A RPI é publicada semanalmente (às terças-feiras) em ``revistas.inpi.gov.br`` e
traz, por seção, apenas as publicações **daquela semana** (o "delta"). É a fonte
certa para manter ``marcas_despachos`` / ``patentes_despachos`` atualizados sem
rebaixar os ~11 GB de CSVs de dados abertos a cada rodada.

Cada seção tem um formato próprio:

* **Marcas** — um XML por edição (``RM<numero>.zip`` → ``.xml``), com a raiz
  ``<revista numero=... data=...>`` e um ``<processo>`` por pedido::

      <revista numero="2910" data="13/10/2026">
        <processo numero="905687116" data-deposito="18/12/2012">
          <despachos>
            <despacho codigo="IPAS009" nome="Publicação de pedido...">
              <texto-complementar>Imagem da Marca alterada.</texto-complementar>
            </despacho>
          </despachos>
          <titulares><titular nome-razao-social="..." pais="BR" uf="SP"/></titulares>
          <marca apresentacao="Mista" natureza="De Produto"><nome>ELITE</nome></marca>
          ...
        </processo>
      </revista>

* **Patentes** — texto simples (``P<numero>.zip`` → ``.txt``) em ``latin-1``,
  com campos marcados por INID de 2 caracteres (``(Cd)`` = código do despacho,
  ``(21)``/``(11)`` = número do pedido, ``(98)`` = complemento, ...). Um registro
  começa em cada ``(Cd)``.

Este módulo é deliberadamente **puro** (só stdlib, sem rede nem banco) para que os
parsers possam ser testados com fixtures, como ``ingestion.pepi_parse``.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import BinaryIO

__all__ = [
    "Despacho",
    "ProcessoMarcas",
    "ProcessoPatente",
    "Revista",
    "only_digits",
    "parse_date_br",
    "parse_marcas_xml",
    "parse_patentes_txt",
]

_INID = re.compile(r"^\(([A-Za-z0-9]{2})\)\s?(.*)$")
# Cabeçalho de seção (ex.: ``"16.1 - Concessão de Patente..."``): NÃO é
# continuação do campo anterior — apenas separa blocos de despachos.
_SECAO = re.compile(r"^\d+(?:\.\d+)*\s*-\s+\S")
# Rótulos que às vezes precedem o valor de ``(98)``/``(99)``.
_ROTULOS = ("complemento:", "comentário:", "comentario:", "comentários:", "comentarios:")


def parse_date_br(value: str | None) -> date | None:
    """``"13/10/2026"`` → ``date(2026, 10, 13)``; inválido/vazio → ``None``."""
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def only_digits(value: str | None) -> str:
    """Remove tudo que não for dígito (ex.: ``"BR 10 2020 000000-0"``)."""
    if not value:
        return ""
    return re.sub(r"\D", "", value)


# --- Marcas (XML) -----------------------------------------------------------
@dataclass
class Despacho:
    """Um despacho publicado (uma linha no histórico RPI)."""

    codigo: str
    nome: str | None = None
    complemento: str | None = None


@dataclass
class ProcessoMarcas:
    numero: str
    data_deposito: date | None = None
    data_concessao: date | None = None
    data_vigencia: date | None = None
    apresentacao: str | None = None
    natureza: str | None = None
    marca_nome: str | None = None
    titulares: list[str] = field(default_factory=list)
    despachos: list[Despacho] = field(default_factory=list)


@dataclass
class Revista:
    numero: str | None
    data: date | None
    processos: list[ProcessoMarcas] = field(default_factory=list)


def _local(tag: str) -> str:
    """``"{ns}tag"`` → ``"tag"`` (tolera XML com/sem namespace)."""
    return tag.rsplit("}", 1)[-1]


def _children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in elem if _local(child.tag) == name]


def _text(elem: ET.Element | None) -> str | None:
    if elem is None or elem.text is None:
        return None
    text = elem.text.strip()
    return text or None


def _attr(elem: ET.Element, name: str) -> str | None:
    value = elem.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _parse_processo(elem: ET.Element) -> ProcessoMarcas | None:
    numero = _attr(elem, "numero")
    if not numero:
        return None

    despachos: list[Despacho] = []
    for despachos_el in _children(elem, "despachos"):
        for despacho_el in _children(despachos_el, "despacho"):
            codigo = _attr(despacho_el, "codigo")
            if not codigo:
                continue
            complemento = _text(
                next(iter(_children(despacho_el, "texto-complementar")), None)
            )
            despachos.append(
                Despacho(
                    codigo=codigo,
                    nome=_attr(despacho_el, "nome"),
                    complemento=complemento,
                )
            )

    apresentacao = None
    natureza = None
    marca_nome = None
    for marca_el in _children(elem, "marca"):
        apresentacao = _attr(marca_el, "apresentacao")
        natureza = _attr(marca_el, "natureza")
        marca_nome = _text(next(iter(_children(marca_el, "nome")), None))

    titulares: list[str] = []
    for titulares_el in _children(elem, "titulares"):
        for titular_el in _children(titulares_el, "titular"):
            nome = _attr(titular_el, "nome-razao-social")
            if nome:
                titulares.append(nome)

    return ProcessoMarcas(
        numero=numero,
        data_deposito=parse_date_br(_attr(elem, "data-deposito")),
        data_concessao=parse_date_br(_attr(elem, "data-concessao")),
        data_vigencia=parse_date_br(_attr(elem, "data-vigencia")),
        apresentacao=apresentacao,
        natureza=natureza,
        marca_nome=marca_nome,
        titulares=titulares,
        despachos=despachos,
    )


def parse_marcas_xml(data: bytes | str | BinaryIO) -> Revista:
    """Lê o XML de uma edição de Marcas.

    Usa ``iterparse`` e limpa cada ``<processo>`` já lido, então o consumo de
    memória não cresce com o tamanho da revista (o XML de uma edição passa de
    dezenas de MB). Aceita ``bytes``/``str`` ou um arquivo binário aberto (ex.:
    o membro do ZIP), o que evita materializar a revista inteira em memória. Um
    arquivo vazio/ilegível devolve uma ``Revista`` sem processos em vez de
    estourar — o chamador decide o que fazer.
    """
    if isinstance(data, str):
        source: BinaryIO = io.BytesIO(data.encode("utf-8"))
    elif isinstance(data, (bytes, bytearray)):
        source = io.BytesIO(bytes(data))
    else:
        source = data

    numero: str | None = None
    data_pub: date | None = None
    processos: list[ProcessoMarcas] = []

    try:
        for event, elem in ET.iterparse(source, events=("start", "end")):
            tag = _local(elem.tag)
            if event == "start":
                if tag == "revista" and numero is None:
                    numero = _attr(elem, "numero")
                    data_pub = parse_date_br(_attr(elem, "data"))
            elif tag == "processo":
                proc = _parse_processo(elem)
                if proc is not None:
                    processos.append(proc)
                elem.clear()
    except ET.ParseError:
        return Revista(numero=numero, data=data_pub, processos=processos)

    return Revista(numero=numero, data=data_pub, processos=processos)


# --- Patentes (TXT) ---------------------------------------------------------
@dataclass
class ProcessoPatente:
    """Um despacho de patente publicado na RPI.

    ``numero`` é o número do pedido como veio no arquivo (ex.:
    ``"BR 10 2020 000000-0"``); o casamento com o banco é feito por
    :func:`only_digits`.
    """

    numero: str | None
    despacho_codigo: str
    complemento: str | None = None
    data_deposito: date | None = None


# Campos que carregam o número do processo (``(11)`` registro, ``(21)`` pedido,
# ``(Np)`` número da petição) e o complemento textual do despacho.
_NUMERO_TAGS = {"11", "21", "Np"}
_COMPLEMENTO_TAGS = {"98", "99"}


def _strip_label(value: str) -> str:
    """Remove um rótulo inicial conhecido (``"Complemento:"``, ...) do valor."""
    text = value.strip()
    lowered = text.lower()
    for label in _ROTULOS:
        if lowered.startswith(label):
            return text[len(label) :].strip()
    return text


def parse_patentes_txt(data: bytes | str | Iterable[str]) -> list[ProcessoPatente]:
    """Lê o ``.txt`` (latin-1) de uma edição de Patentes.

    O arquivo é uma sequência de registros, cada um iniciado por ``(Cd)`` e
    seguido de campos INID. Campos podem quebrar em várias linhas — linhas sem
    tag continuam o campo anterior (mesma heurística do parser de referência do
    INPI). Só os campos relevantes para ``patentes_despachos`` são extraídos.

    Aceita ``bytes`` (decodificados como latin-1), ``str`` ou um iterável de
    linhas já decodificadas — este último permite processar o TXT em *streaming*
    a partir do ZIP, sem carregar a revista inteira em memória.
    """
    if isinstance(data, bytes):
        lines: Iterable[str] = data.decode("latin-1", errors="replace").splitlines()
    elif isinstance(data, str):
        lines = data.splitlines()
    else:
        lines = data

    records: list[ProcessoPatente] = []
    campos: dict[str, str] = {}
    ultima_tag: str | None = None

    def flush() -> None:
        if not campos:
            return
        codigo = campos.get("Cd")
        if not codigo:
            return
        complemento = " ".join(
            _strip_label(campos[tag]) for tag in ("98", "99") if campos.get(tag)
        ) or None
        records.append(
            ProcessoPatente(
                numero=campos.get("numero"),
                despacho_codigo=codigo,
                complemento=complemento,
                data_deposito=parse_date_br(campos.get("22")),
            )
        )

    for raw in lines:
        line = raw.lstrip(" ")
        if not line.strip():
            continue
        if _SECAO.match(line):
            # Cabeçalho de seção: fecha a continuação do campo anterior.
            ultima_tag = None
            continue
        match = _INID.match(line)
        if match:
            tag, value = match.group(1), match.group(2).strip()
            if tag == "Cd":
                flush()
                campos = {"Cd": value}
                ultima_tag = "Cd"
                continue
            if not campos:
                # Linha de cabeçalho/rodapé antes do primeiro despacho.
                continue
            if tag in _NUMERO_TAGS:
                campos["numero"] = ((campos.get("numero") or "") + " " + value).strip()
                ultima_tag = "numero"
            else:
                campos[tag] = value
                ultima_tag = tag
        elif ultima_tag == "numero" or ultima_tag in _COMPLEMENTO_TAGS:
            # Continuação do campo anterior (número/complemento quebram linha).
            # Campos que não usamos (título, resumo, ...) são ignorados.
            value = line.strip()
            if value:
                campos[ultima_tag] = ((campos.get(ultima_tag) or "") + " " + value).strip()

    flush()
    return records
