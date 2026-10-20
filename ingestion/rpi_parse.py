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
          <nome-imagem>905687116.jpg</nome-imagem>
        </processo>
      </revista>

  O ``<nome-imagem>`` (quando presente) identifica o arquivo da figura no
  acervo da RPI. Ele pode aparecer como filho direto de ``<processo>``, dentro
  de ``<marca>`` ou como atributo; :func:`parse_marcas_xml` aceita as três
  formas e normaliza o valor (só o nome do arquivo, sem diretório).

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
    "Pessoa",
    "Prioridade",
    "ProcessoDesenho",
    "ProcessoMarcas",
    "ProcessoPatente",
    "ProcessoSoftware",
    "Revista",
    "RevistaDesenho",
    "RevistaSoftware",
    "Vinculo",
    "normalize_image_name",
    "only_digits",
    "parse_date_br",
    "parse_desenho_industrial_xml",
    "parse_marcas_xml",
    "parse_patentes_txt",
    "parse_programa_computador_xml",
    "process_key",
]

_INID = re.compile(r"^\(([A-Za-z0-9]{2})\)\s?(.*)$")
# Tags que carregam o nome do arquivo da imagem da marca. O XML oficial usa
# ``<nome-imagem>``; as variantes abaixo cobrem versões/edições mais antigas e
# exports de terceiros sem quebrar o parser.
_IMAGE_TAGS = frozenset(
    {
        "nome-imagem",
        "nome_imagem",
        "nomeimagem",
        "imagem",
        "arquivo-imagem",
        "arquivo_imagem",
        "logo",
    }
)
_IMAGE_ATTRS = ("nome-imagem", "nome_imagem", "arquivo", "imagem")
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


# Prefixos dos números de processo que a RPI publica COM o dígito verificador,
# mas que os CSVs de dados abertos guardam SEM ele:
#
#   RPI:  "BR 30 2015 001635-3"  → 3020150016353 (13 dígitos)
#   CSV:  "302015001635"         → 302015001635  (12 dígitos)
#
# O mesmo vale para Programas de Computador ("BR 51 2025 006135-8"). A chave
# canônica remove apenas o último dígito nesses casos; números antigos (ex.:
# ``DI2600088``) são mantidos como estão.
_CHECK_DIGIT_PREFIXES = frozenset({"30", "51"})


def process_key(value: str | None) -> str:
    """Chave de casamento entre o número da RPI e ``numero_inpi`` do CSV.

    Remove a pontuação e o dígito verificador dos processos de Desenho
    Industrial/Programa de Computador. É usada tanto pelo parser quanto pelo
    mapeamento no banco (:mod:`ingestion.db`), garantindo os dois lados iguais.
    """
    digits = only_digits(value)
    if len(digits) == 13 and digits[:2] in _CHECK_DIGIT_PREFIXES:
        return digits[:-1]
    return digits


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
    #: Nome do arquivo da figura no acervo da RPI (``<nome-imagem>``), já
    #: normalizado para apenas o nome do arquivo (sem diretório).
    nome_imagem: str | None = None
    titulares: list[str] = field(default_factory=list)
    despachos: list[Despacho] = field(default_factory=list)

    @property
    def tem_imagem(self) -> bool:
        """``True`` quando o processo referencia uma figura da marca."""
        return bool(self.nome_imagem)


@dataclass
class Revista:
    numero: str | None
    data: date | None
    processos: list[ProcessoMarcas] = field(default_factory=list)
    #: Preenchido quando o XML foi truncado/corrompido e só uma parte dos
    #: processos pôde ser lida. O chamador pode então marcar a edição como
    #: ``FAILED`` em vez de gravar um delta incompleto como se fosse completo.
    parse_error: str | None = None


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


def normalize_image_name(value: str | None) -> str | None:
    """Normaliza o valor de ``<nome-imagem>`` para um nome de arquivo seguro.

    O XML do INPI normalmente traz só o nome (``912345678.jpg``), mas exports
    antigos podem trazer um caminho completo. Só o ``basename`` interessa (e é o
    que o endpoint ``/rpi/images/...`` espera). Valores vazios, ``.``/``..`` e
    nomes com separadores após a normalização são rejeitados — defesa contra
    *path traversal* ao gravar a imagem em disco.
    """
    if not value:
        return None
    text = str(value).strip().replace("\\", "/")
    if not text:
        return None
    name = text.rsplit("/", 1)[-1].strip()
    # Alguns exports trazem o nome como URL; query/fragmento não fazem parte do
    # nome do arquivo no acervo.
    name = name.split("?", 1)[0].split("#", 1)[0].strip()
    if not name or name in {".", ".."}:
        return None
    # Remove caracteres de controle e componentes de caminho que sobreviveram.
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    if not name or "/" in name or "\\" in name:
        return None
    return name[:255]


def _image_name(elem: ET.Element) -> str | None:
    """Extrai o ``nome-imagem`` de um ``<processo>`` (ou de seus filhos).

    Ordem de precedência: filho direto do processo → atributo do processo →
    filho de ``<marca>``. A primeira ocorrência preenchida vence.
    """
    for child in elem:
        if _local(child.tag) in _IMAGE_TAGS:
            found = normalize_image_name(_text(child) or _attr(child, "nome"))
            if found:
                return found

    for attr in _IMAGE_ATTRS:
        found = normalize_image_name(_attr(elem, attr))
        if found:
            return found

    for marca_el in _children(elem, "marca"):
        for child in marca_el:
            if _local(child.tag) in _IMAGE_TAGS:
                found = normalize_image_name(_text(child) or _attr(child, "nome"))
                if found:
                    return found
        for attr in _IMAGE_ATTRS:
            found = normalize_image_name(_attr(marca_el, attr))
            if found:
                return found
    return None


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
        nome_imagem=_image_name(elem),
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
    parse_error: str | None = None

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
    except ET.ParseError as exc:
        # Mantém os processos já lidos (o chamador decide se o parcial serve),
        # mas expõe o erro: um XML truncado NÃO pode ser tratado como uma
        # edição completa — era o que fazia o worker marcar PROCESSED e nunca
        # reprocessar o delta.
        parse_error = f"{type(exc).__name__}: {exc}"

    return Revista(
        numero=numero, data=data_pub, processos=processos, parse_error=parse_error
    )


# --- Desenho Industrial / Programa de Computador (XML) ----------------------
@dataclass
class Pessoa:
    """Titular, autor ou procurador de um processo (dados da RPI)."""

    nome: str
    ordem: str | None = None
    pais: str | None = None
    estado: str | None = None
    cpf_cnpj: str | None = None
    tipo_pessoa: str | None = None


@dataclass
class Prioridade:
    """Prioridade unionista declarada em um Desenho Industrial."""

    pais: str | None = None
    numero: str | None = None
    data: date | None = None


@dataclass
class Vinculo:
    """Vínculo entre processos (ex.: divisão de pedido de desenho)."""

    numero: str | None = None
    data: date | None = None
    tipo: str | None = None


@dataclass
class ProcessoDesenho:
    """Processo de Desenho Industrial agregado a partir de uma edição da RPI.

    O XML de Desenhos é centrado em ``<despacho>``: o mesmo processo pode
    aparecer em vários despachos da mesma edição. Agregamos tudo por número para
    gravar uma única linha bibliográfica e o histórico completo de despachos.
    """

    numero: str
    data_deposito: date | None = None
    data_concessao: date | None = None
    data_publicacao: date | None = None
    titulo: str | None = None
    nome_imagem: str | None = None
    #: ``True`` quando o XML traz ``<complemento-figura-rosto/>`` (há figura).
    figura_rosto: bool = False
    titulares: list[Pessoa] = field(default_factory=list)
    autores: list[Pessoa] = field(default_factory=list)
    procuradores: list[Pessoa] = field(default_factory=list)
    classificacoes: list[str] = field(default_factory=list)
    prioridades: list[Prioridade] = field(default_factory=list)
    vinculos: list[Vinculo] = field(default_factory=list)
    despachos: list[Despacho] = field(default_factory=list)

    @property
    def tem_imagem(self) -> bool:
        """``True`` quando a edição indica/referencia uma figura do desenho."""
        return bool(self.nome_imagem) or self.figura_rosto


@dataclass
class ProcessoSoftware:
    """Processo de Programa de Computador agregado a partir de uma edição."""

    numero: str
    titulo: str | None = None
    data_criacao: date | None = None
    data_publicacao: date | None = None
    titulares: list[Pessoa] = field(default_factory=list)
    autores: list[Pessoa] = field(default_factory=list)
    linguagens: list[str] = field(default_factory=list)
    campos_aplicacao: list[str] = field(default_factory=list)
    tipos_programa: list[str] = field(default_factory=list)
    despachos: list[Despacho] = field(default_factory=list)


@dataclass
class RevistaDesenho:
    numero: str | None
    data: date | None
    processos: list[ProcessoDesenho] = field(default_factory=list)
    parse_error: str | None = None


@dataclass
class RevistaSoftware:
    numero: str | None
    data: date | None
    processos: list[ProcessoSoftware] = field(default_factory=list)
    parse_error: str | None = None


def _first_text(elem: ET.Element | None, *names: str) -> str | None:
    """Primeiro filho (na ordem de ``names``) com texto não vazio."""
    if elem is None:
        return None
    for name in names:
        found = _text(next(iter(_children(elem, name)), None))
        if found:
            return found
    return None


def _child(elem: ET.Element | None, *names: str) -> ET.Element | None:
    if elem is None:
        return None
    for name in names:
        found = next(iter(_children(elem, name)), None)
        if found is not None:
            return found
    return None


def _location(elem: ET.Element | None) -> tuple[str | None, str | None]:
    """Extrai ``(uf, país)`` de ``<endereco><uf/><pais><sigla/></pais>``."""
    endereco = _child(elem, "endereco")
    if endereco is None:
        return None, None
    estado = _first_text(endereco, "uf", "estado")
    pais_el = _child(endereco, "pais")
    pais = _first_text(pais_el, "sigla", "pais") or _text(pais_el)
    return estado, pais


def _person(elem: ET.Element, *name_tags: str) -> Pessoa | None:
    nome = _first_text(elem, *name_tags)
    if not nome:
        return None
    estado, pais = _location(elem)
    documento = _first_text(elem, "cpf-cnpj", "cpf_cnpj", "cpf/cnpj", "documento")
    if documento is None:
        documento = (
            _attr(elem, "cpf-cnpj")
            or _attr(elem, "cpf_cnpj")
            or _attr(elem, "documento")
        )
    return Pessoa(
        nome=nome,
        ordem=_attr(elem, "sequencia") or _attr(elem, "ordem"),
        pais=pais,
        estado=estado,
        cpf_cnpj=documento,
        tipo_pessoa=_attr(elem, "tipo-pessoa") or _attr(elem, "tipo_pessoa"),
    )


def _people(elem: ET.Element | None, list_names: tuple[str, ...], item_names: tuple[str, ...]):
    """Percorre listas como ``<titular-lista><titular>...``."""
    if elem is None:
        return []
    out: list[Pessoa] = []
    for list_name in list_names:
        for list_el in _children(elem, list_name):
            for item_name in item_names:
                for item_el in _children(list_el, item_name):
                    person = _person(item_el, "nome-completo", "nome", "razao-social")
                    if person is not None:
                        out.append(person)
    return out


def _despacho_from(elem: ET.Element) -> Despacho | None:
    """Lê um ``<despacho>`` no formato de DI/PC (código e título como filhos)."""
    codigo = _first_text(elem, "codigo") or _attr(elem, "codigo")
    if not codigo:
        return None
    return Despacho(
        codigo=codigo.strip(),
        nome=_first_text(elem, "titulo") or _attr(elem, "nome"),
        complemento=_first_text(elem, "comentario"),
    )


def _process_element(elem: ET.Element) -> ET.Element | None:
    """Localiza o bloco do processo dentro de um ``<despacho>``."""
    return _child(
        elem,
        "processo-patente",
        "processo-programa",
        "processo-desenho",
        "processo",
    )


def _append_unique(target: list, value, key) -> None:
    if value is None:
        return
    marker = key(value)
    if all(key(existing) != marker for existing in target):
        target.append(value)


def _merge_despachos(target: list[Despacho], despachos: list[Despacho]) -> None:
    for despacho in despachos:
        _append_unique(
            target,
            despacho,
            lambda d: (d.codigo, d.complemento or "", d.nome or ""),
        )


def _merge_desenho(target: ProcessoDesenho, incoming: ProcessoDesenho) -> None:
    for attr in (
        "data_deposito",
        "data_concessao",
        "data_publicacao",
        "titulo",
        "nome_imagem",
    ):
        if not getattr(target, attr) and getattr(incoming, attr):
            setattr(target, attr, getattr(incoming, attr))
    target.figura_rosto = target.figura_rosto or incoming.figura_rosto
    for attr, key in (
        ("titulares", lambda p: (p.nome, p.cpf_cnpj or "")),
        ("autores", lambda p: (p.nome,)),
        ("procuradores", lambda p: (p.nome, p.cpf_cnpj or "")),
        ("classificacoes", lambda c: (c,)),
        ("prioridades", lambda p: (p.pais or "", p.numero or "")),
        ("vinculos", lambda v: (v.numero or "", v.tipo or "")),
    ):
        for value in getattr(incoming, attr):
            _append_unique(getattr(target, attr), value, key)
    _merge_despachos(target.despachos, incoming.despachos)


def _merge_software(target: ProcessoSoftware, incoming: ProcessoSoftware) -> None:
    for attr in ("titulo", "data_criacao", "data_publicacao"):
        if not getattr(target, attr) and getattr(incoming, attr):
            setattr(target, attr, getattr(incoming, attr))
    for attr, key in (
        ("titulares", lambda p: (p.nome,)),
        ("autores", lambda p: (p.nome,)),
        ("linguagens", lambda v: (v,)),
        ("campos_aplicacao", lambda v: (v,)),
        ("tipos_programa", lambda v: (v,)),
    ):
        for value in getattr(incoming, attr):
            _append_unique(getattr(target, attr), value, key)
    _merge_despachos(target.despachos, incoming.despachos)


def _classificacoes(proc: ET.Element) -> list[str]:
    out: list[str] = []
    for list_el in _children(proc, "classificacao-nacional-lista"):
        for item in _children(list_el, "classificacao-nacional"):
            value = _text(item) or _attr(item, "codigo")
            if value:
                _append_unique(out, value.strip(), lambda v: (v,))
    return out


def _prioridades(proc: ET.Element) -> list[Prioridade]:
    out: list[Prioridade] = []
    for list_el in _children(proc, "prioridade-unionista-lista"):
        for item in _children(list_el, "prioridade-unionista"):
            prioridade = Prioridade(
                pais=_first_text(item, "sigla-pais", "pais"),
                numero=_first_text(item, "numero-prioridade", "numero"),
                data=parse_date_br(_first_text(item, "data-prioridade", "data")),
            )
            _append_unique(
                out,
                prioridade,
                lambda p: (p.pais or "", p.numero or "", p.data or ""),
            )
    return out


def _vinculos(proc: ET.Element) -> list[Vinculo]:
    out: list[Vinculo] = []
    for item in _children(proc, "divisao-pedido"):
        vinculo = Vinculo(
            numero=_first_text(item, "numero"),
            data=parse_date_br(_first_text(item, "data-deposito", "data")),
            tipo="divisao",
        )
        _append_unique(out, vinculo, lambda v: (v.numero or "", v.tipo or ""))
    return out


def _parse_processo_desenho(proc: ET.Element) -> ProcessoDesenho | None:
    numero = _first_text(proc, "numero") or _attr(proc, "numero")
    if not numero:
        return None

    concessao = _child(proc, "concessao")
    publicacao = _child(proc, "publicacao-nacional")
    titulo = _first_text(proc, "titulo")
    nome_imagem = _image_name(proc)

    return ProcessoDesenho(
        numero=numero,
        data_deposito=parse_date_br(
            _first_text(proc, "data-deposito") or _attr(proc, "data-deposito")
        ),
        data_concessao=parse_date_br(
            _first_text(concessao, "data") if concessao is not None else None
        ),
        data_publicacao=parse_date_br(
            _first_text(publicacao, "data-rpi", "data")
            if publicacao is not None
            else None
        ),
        titulo=titulo,
        nome_imagem=nome_imagem,
        figura_rosto=bool(_children(proc, "complemento-figura-rosto"))
        or bool(nome_imagem),
        titulares=_people(
            proc, ("titular-lista", "titulares"), ("titular",)
        ),
        autores=_people(proc, ("inventor-lista",), ("inventor", "autor")),
        procuradores=_people(proc, ("procurador-lista",), ("procurador",)),
        classificacoes=_classificacoes(proc),
        prioridades=_prioridades(proc),
        vinculos=_vinculos(proc),
    )


def _codes_from_list(
    proc: ET.Element,
    list_names: tuple[str, ...],
    item_names: tuple[str, ...],
) -> list[str]:
    out: list[str] = []
    for list_name in list_names:
        for list_el in _children(proc, list_name):
            for item_name in item_names:
                for item in _children(list_el, item_name):
                    code = _first_text(item, "codigo") or _text(item)
                    if code:
                        _append_unique(out, code.strip(), lambda v: (v,))
    return out


def _parse_processo_software(proc: ET.Element) -> ProcessoSoftware | None:
    numero = _first_text(proc, "numero") or _attr(proc, "numero")
    if not numero:
        return None
    return ProcessoSoftware(
        numero=numero,
        titulo=_first_text(proc, "titulo"),
        data_criacao=parse_date_br(_first_text(proc, "dataCriacao", "data-criacao")),
        titulares=_people(proc, ("titularLista", "titular-lista"), ("titular",)),
        autores=_people(proc, ("criadorLista", "criador-lista"), ("criador", "autor")),
        linguagens=_codes_from_list(
            proc, ("linguagemLista", "linguagem-lista"), ("linguagem",)
        ),
        campos_aplicacao=_codes_from_list(
            proc,
            ("campoAplicacaoLista", "campo-aplicacao-lista"),
            ("campoAplicacao", "campo-aplicacao"),
        ),
        tipos_programa=_codes_from_list(
            proc,
            ("tipoProgramaLista", "tipo-programa-lista"),
            ("tipoPrograma", "tipo-programa"),
        ),
    )


def _parse_revista_xml(
    data: bytes | str | BinaryIO,
    *,
    process_parser,
    revista_factory,
):
    """Base comum do ``iterparse`` das revistas em que o processo fica no despacho."""
    if isinstance(data, str):
        source: BinaryIO = io.BytesIO(data.encode("utf-8"))
    elif isinstance(data, (bytes, bytearray)):
        source = io.BytesIO(bytes(data))
    else:
        source = data

    numero: str | None = None
    data_pub: date | None = None
    processos: dict[str, object] = {}
    parse_error: str | None = None

    try:
        for event, elem in ET.iterparse(source, events=("start", "end")):
            tag = _local(elem.tag)
            if event == "start":
                if tag == "revista" and numero is None:
                    numero = _attr(elem, "numero")
                    data_pub = parse_date_br(
                        _attr(elem, "dataPublicacao") or _attr(elem, "data")
                    )
                continue
            if tag != "despacho":
                continue
            despacho = _despacho_from(elem)
            proc_el = _process_element(elem)
            if despacho is None or proc_el is None:
                elem.clear()
                continue
            proc = process_parser(proc_el)
            if proc is not None:
                proc.despachos.append(despacho)
                existing = processos.get(proc.numero)
                if existing is None:
                    processos[proc.numero] = proc
                else:
                    # ``_merge_desenho`` e ``_merge_software`` compartilham a
                    # mesma forma; o merge correto é escolhido pelo tipo.
                    if isinstance(existing, ProcessoDesenho):
                        _merge_desenho(existing, proc)
                    else:
                        _merge_software(existing, proc)
            elem.clear()
    except ET.ParseError as exc:
        parse_error = f"{type(exc).__name__}: {exc}"

    return revista_factory(
        numero=numero,
        data=data_pub,
        processos=list(processos.values()),
        parse_error=parse_error,
    )


def parse_desenho_industrial_xml(data: bytes | str | BinaryIO) -> RevistaDesenho:
    """Lê o XML de uma edição de Desenhos Industriais (``DI<numero>.zip``)."""
    return _parse_revista_xml(
        data,
        process_parser=_parse_processo_desenho,
        revista_factory=RevistaDesenho,
    )


def parse_programa_computador_xml(data: bytes | str | BinaryIO) -> RevistaSoftware:
    """Lê o XML de uma edição de Programas de Computador (``PC<numero>.zip``)."""
    return _parse_revista_xml(
        data,
        process_parser=_parse_processo_software,
        revista_factory=RevistaSoftware,
    )


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
