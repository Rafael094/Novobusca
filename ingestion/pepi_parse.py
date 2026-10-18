"""Parser da página de detalhe de marca do pePI.

A página é servida por ``MarcasServletController?Action=detail&CodPedido=<cod>``
depois de uma sessão **anônima** (``LoginController?action=login``). Ela traz os
"accordions" com Classificação Nice/Viena, Titulares, Representantes, Datas,
Prazos, **Petições** (documentos GRU) e Publicações (despachos). Este módulo
extrai as **petições**, que não existem nos CSVs de dados abertos.

É puro: só usa a stdlib, recebe o HTML já decodificado e devolve estruturas
Python. Não faz rede nem toca no banco — assim é testável isoladamente e serve
tanto ao worker (``ingestion.peticoes``) quanto a testes.
"""

from __future__ import annotations

import html as _html
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

__all__ = [
    "parse_peticoes",
    "parse_revista",
    "parse_numero_processo",
    "looks_like_login",
    "strip_tags",
    "first_date",
]

_RE_TAG = re.compile(r"<[^>]+>")
_RE_WS = re.compile(r"\s+")
_RE_DMY = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _norm(text: str | None) -> str:
    return _RE_WS.sub(" ", (text or "")).strip()


def strip_tags(fragment: str | None) -> str:
    """Remove tags de um fragmento HTML e normaliza espaços/entidades."""
    if not fragment:
        return ""
    text = _RE_TAG.sub(" ", fragment)
    text = _html.unescape(text)
    return _norm(text)


def first_date(text: str | None) -> date | None:
    """Primeira data ``dd/mm/aaaa`` encontrada no texto (ou ``None``)."""
    m = _RE_DMY.search(text or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _first_date(text: str | None) -> date | None:
    return first_date(text)


def looks_like_login(html_text: str) -> bool:
    """Heurística: a resposta é a tela de login (sessão expirada/ausente)."""
    return "F_LoginCliente" in (html_text or "")


class _PeticoesTableParser(HTMLParser):
    """Coleta as células de 1º nível (``<td>`` externos) de cada ``<tr>`` da
    tabela de Petições.

    A tabela é identificada por conter um ``<div id="pgtoN">`` por linha (o
    balão de "Informações do Banco"), o que a distingue das demais tabelas da
    página sem depender de ids de accordion. As células internas (o ``<table>``
    aninhado dentro do 1º ``<td>``) são preservadas no HTML da célula externa,
    mas não contadas como colunas.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._in_row = False
        self._cells: list[str] = []
        self._has_pgto = False
        self._td_depth = 0
        self._buf: list[str] | None = None

    # -- start tags ---------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or ""
        if tag == "tr":
            if self._in_row:
                if self._buf is not None:
                    self._buf.append(raw)
                return
            self._in_row = True
            self._cells = []
            self._has_pgto = False
            self._td_depth = 0
            self._buf = None
            return
        if not self._in_row:
            return
        if tag == "td":
            self._td_depth += 1
            if self._td_depth == 1:
                self._buf = [raw]
            elif self._buf is not None:
                self._buf.append(raw)
            return
        if self._buf is not None:
            self._buf.append(raw)
        if tag == "div" and (dict(attrs).get("id") or "").startswith("pgto"):
            self._has_pgto = True

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._buf is not None:
            self._buf.append(self.get_starttag_text() or "")

    # -- end tags -----------------------------------------------------------
    def handle_endtag(self, tag: str) -> None:
        if not self._in_row:
            return
        if tag == "td":
            if self._td_depth == 0:
                return
            if self._buf is not None:
                self._buf.append("</td>")
            self._td_depth -= 1
            if self._td_depth == 0 and self._buf is not None:
                self._cells.append("".join(self._buf))
                self._buf = None
            return
        if tag == "tr":
            if self._td_depth == 0:
                if self._has_pgto and self._cells:
                    self.rows.append(self._cells)
                self._in_row = False
                self._cells = []
                self._buf = None
                return
            if self._buf is not None:
                self._buf.append("</tr>")
            return
        if self._buf is not None:
            self._buf.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._buf is not None:
            self._buf.append(data)


def _has_content(fragment: str) -> bool:
    text = strip_tags(fragment)
    return bool(text) and text != "-"


def _parse_servico(cell: str) -> tuple[str | None, str | None]:
    """Separa ``servico + descrição`` (ex.: "372 Primeiro decênio de..." )."""
    text = strip_tags(cell)
    if not text:
        return None, None
    m = re.match(r"^(\d{1,6})\s*(.*)$", text, re.S)
    if m:
        return m.group(1), (_norm(m.group(2)) or None)
    return None, text


def _parse_valor(raw: str | None) -> Decimal | None:
    s = _norm(raw)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _parse_pagamento(
    cell: str,
) -> tuple[bool, str | None, str | None, date | None, Decimal | None]:
    """Extrai (conciliado, banco_codigo, banco_nome, data, valor) do 1º ``<td>``.

    O conteúdo vem do balão ``<div id="pgtoN">``: "077 - Banco ... <br> Data:
    22/12/2021 <br> Valor: R$298.0". Linhas sem pagamento ficam com o balão
    vazio e devolvem ``(False, None, None, None, None)``.
    """
    text = strip_tags(cell)
    # "Pagamento Conciliado" vem no atributo alt do ícone (não no texto), então
    # a detecção é feita sobre o HTML bruto da célula.
    conciliado = "pagamento conciliado" in (cell or "").lower()

    banco_codigo: str | None = None
    banco_nome: str | None = None
    data_pagamento: date | None = None
    valor: Decimal | None = None

    if text:
        m = re.search(r"(\d{2,5})\s*-\s*(.+?)(?:\s*Data:|\s*Valor:|$)", text)
        if m:
            banco_codigo = m.group(1)
            banco_nome = _norm(m.group(2)) or None
        data_pagamento = _first_date(
            (re.search(r"Data:\s*(\d{2}/\d{2}/\d{4})", text) or [None, None])[1]
        )
        mv = re.search(r"Valor:\s*R\$\s*([\d.,]+)", text)
        valor = _parse_valor(mv.group(1)) if mv else None

    return conciliado, banco_codigo, banco_nome, data_pagamento, valor


def parse_peticoes(html_text: str) -> list[dict]:
    """Extrai as petições (documentos GRU) da página de detalhe.

    Devolve uma lista de dicts (um por protocolo), prontos para ``upsert``.
    Ordem preservada como na página (mais recente primeiro).
    """
    parser = _PeticoesTableParser()
    parser.feed(html_text or "")
    parser.close()

    out: list[dict] = []
    for cells in parser.rows:
        if len(cells) < 7:
            continue
        protocolo = strip_tags(cells[1])
        if not protocolo:
            continue
        data_protocolo = _first_date(strip_tags(cells[2]))
        tem_imagem = _has_content(cells[3])
        codigo_servico, descricao_servico = _parse_servico(cells[5])
        cliente = strip_tags(cells[6]) or None
        delivery = strip_tags(cells[7]) if len(cells) > 7 else ""
        data_delivery = (
            _first_date(strip_tags(cells[8])) if len(cells) > 8 else None
        )
        conciliado, banco_codigo, banco_nome, data_pagamento, valor = _parse_pagamento(
            cells[0]
        )
        out.append(
            {
                "protocolo": protocolo,
                "data_protocolo": data_protocolo,
                "codigo_servico": codigo_servico,
                "descricao_servico": descricao_servico,
                "cliente": cliente,
                "pagamento_conciliado": conciliado,
                "banco_codigo": banco_codigo,
                "banco_nome": banco_nome,
                "data_pagamento": data_pagamento,
                "valor_pagamento": valor,
                "delivery": delivery or None,
                "data_delivery": data_delivery,
                "tem_imagem": tem_imagem,
            }
        )
    return out


def parse_revista(html_text: str) -> tuple[date | None, str | None]:
    """Lê o rodapé "Dados atualizados até <data> - Nº da Revista: <n>".

    Serve de marcador barato de versão/atualidade da fonte (TTL do worker).
    """
    text = html_text or ""
    data: date | None = None
    m = re.search(r"at[ée]\s*(?:<[^>]+>\s*)*(\d{2}/\d{2}/\d{4})", text, re.I)
    if m:
        data = _first_date(m.group(1))
    numero: str | None = None
    m = re.search(r"Revista:\s*(?:<[^>]+>\s*)*(\d+)", text, re.I)
    if m:
        numero = m.group(1)
    return data, numero


def parse_numero_processo(html_text: str) -> str | None:
    """Número do processo INPI (``numero_inpi``) no detalhe da página."""
    m = re.search(
        r'name="numeroProcesso"\s+value\s*=\s*"([^"]*)"', html_text or "", re.I
    )
    if not m:
        return None
    return _norm(m.group(1)) or None
