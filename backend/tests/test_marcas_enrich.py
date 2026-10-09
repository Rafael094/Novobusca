"""Tests for the enriched /api/marcas/search response.

Covers the INPI-equivalent field richness added on top of the (unchanged) search
semantics:

  * titulares[] (source of truth) + derived titular_principal / num_titulares;
  * classificacoes[] (Nice / nacional / Viena) with real codes and descriptions;
  * cardinality: 1 processo de marca = 1 resultado (joins never duplicate rows);
  * pagination / total correctness with enrichments present;
  * no N+1 (fixed number of queries per page);
  * existing filters keep working with the new fields in place.
"""

from __future__ import annotations

from sqlalchemy import event

from app.models import (
    Marca,
    MarcaClassificacaoNacional,
    MarcaClassificacaoNice,
    MarcaClassificacaoViena,
    MarcaDepositante,
)
from tests.conftest import assign_role, auth_header, login, make_tenant, make_user


def _add_marca(db, *, codigo, nome, numero=None, situacao=None, data=None):
    db.add(
        Marca(
            codigo_interno=codigo,
            numero_inpi=numero,
            elemento_nominativo=nome,
            codigo_situacao=situacao,
            data_deposito=data,
        )
    )


def _seed(client, db) -> str:
    tenant = make_tenant(db, name="Marcas Enrich", module_codes=["MARCAS"])
    user = make_user(db, email="enricher@example.com", tenant_id=tenant.id)
    assign_role(db, user.id, "MARCAS_VIEW")

    # c1: 1 titular, 1 nice + 1 nacional.
    _add_marca(db, codigo="c1", nome="MAGU", numero="100", situacao="100")
    db.add(MarcaDepositante(codigo_interno="c1", nome="ACME LTDA"))
    db.add(
        MarcaClassificacaoNice(
            codigo_interno="c1", edicao_nice="8", classe_nice="35",
            especificacao="Publicidade",
        )
    )
    db.add(
        MarcaClassificacaoNacional(
            codigo_interno="c1", classe="33", especificacao="Serviços diversos"
        )
    )

    # c2: 2 titulares, 2 nice, 1 viena. Both titulares share one procurador.
    _add_marca(db, codigo="c2", nome="MAGU", numero="101", situacao="100")
    db.add(
        MarcaDepositante(
            codigo_interno="c2",
            nome="BETA SA",
            nome_representante_legal="PROC ADVOGADOS",
            cnpj_cpf_representante_legal="12345678000199",
        )
    )
    db.add(
        MarcaDepositante(
            codigo_interno="c2",
            nome="GAMA SA",
            nome_representante_legal="PROC ADVOGADOS",
            cnpj_cpf_representante_legal="12345678000199",
        )
    )
    db.add(
        MarcaClassificacaoNice(codigo_interno="c2", edicao_nice="8", classe_nice="20")
    )
    db.add(
        MarcaClassificacaoNice(codigo_interno="c2", edicao_nice="8", classe_nice="25")
    )
    db.add(MarcaClassificacaoViena(codigo_interno="c2", simbolo="04.01.01"))

    # c3: no titular, no classification (must not break anything).
    _add_marca(db, codigo="c3", nome="MAGU", numero="102", situacao="200")

    db.commit()
    return login(client, "enricher@example.com")["access_token"]


def _search(client, token, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return client.get(f"/api/marcas/search?{qs}", headers=auth_header(token))


def test_new_fields_present_in_response(db, seeded, client):
    token = _seed(client, db)
    resp = _search(client, token, q="MAGU", match_mode="exact")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for it in body["items"]:
        assert "titulares" in it
        assert "titular_principal" in it
        assert "num_titulares" in it
        assert "classificacoes" in it


def test_single_titular(db, seeded, client):
    token = _seed(client, db)
    body = _search(client, token, q="MAGU", match_mode="exact").json()
    item = next(i for i in body["items"] if i["codigo_interno"] == "c1")
    assert item["titulares"] == ["ACME LTDA"]
    assert item["titular_principal"] == "ACME LTDA"
    assert item["num_titulares"] == 1


def test_multiple_titulares_no_duplication(db, seeded, client):
    token = _seed(client, db)
    body = _search(client, token, q="MAGU", match_mode="exact").json()
    # Cardinality: exactly one row per codigo_interno, even with 2 titulares.
    codes = [i["codigo_interno"] for i in body["items"]]
    assert sorted(codes) == ["c1", "c2", "c3"]
    assert len(codes) == len(set(codes))
    item = next(i for i in body["items"] if i["codigo_interno"] == "c2")
    assert item["titulares"] == ["BETA SA", "GAMA SA"]
    assert item["num_titulares"] == 2
    assert item["titular_principal"] == "BETA SA"


def test_marca_without_classification_or_titular(db, seeded, client):
    token = _seed(client, db)
    body = _search(client, token, q="MAGU", match_mode="exact").json()
    item = next(i for i in body["items"] if i["codigo_interno"] == "c3")
    assert item["titulares"] == []
    assert item["num_titulares"] == 0
    assert item["titular_principal"] is None
    assert item["classificacoes"] == []


def test_multiple_classificacoes(db, seeded, client):
    token = _seed(client, db)
    body = _search(client, token, q="MAGU", match_mode="exact").json()
    item = next(i for i in body["items"] if i["codigo_interno"] == "c2")
    tipos = {c["tipo"] for c in item["classificacoes"]}
    assert tipos == {"nice", "viena"}
    nice_codigos = sorted(
        c["codigo"] for c in item["classificacoes"] if c["tipo"] == "nice"
    )
    assert nice_codigos == ["NCL(8) 20", "NCL(8) 25"]


def test_classification_shape_and_description(db, seeded, client):
    token = _seed(client, db)
    body = _search(client, token, q="MAGU", match_mode="exact").json()
    item = next(i for i in body["items"] if i["codigo_interno"] == "c1")
    nice = next(c for c in item["classificacoes"] if c["tipo"] == "nice")
    assert nice["codigo"] == "NCL(8) 35"
    assert nice["descricao"] == "Publicidade"
    nac = next(c for c in item["classificacoes"] if c["tipo"] == "nacional")
    assert nac["codigo"] == "33"
    assert nac["descricao"] == "Serviços diversos"


def test_total_and_pagination_without_duplication(db, seeded, client):
    token = _seed(client, db)
    body = _search(
        client, token, q="MAGU", match_mode="exact", page=1, page_size=2
    ).json()
    assert body["pagination"]["total"] == 3
    assert len(body["items"]) == 2
    body2 = _search(
        client, token, q="MAGU", match_mode="exact", page=2, page_size=2
    ).json()
    assert len(body2["items"]) == 1
    codes = {i["codigo_interno"] for i in body["items"]} | {
        i["codigo_interno"] for i in body2["items"]
    }
    assert codes == {"c1", "c2", "c3"}


def test_no_n_plus_one_fixed_query_count(db, seeded, client):
    """The page enrichment must use a fixed number of queries, not one per row."""
    token = _seed(client, db)
    for n in range(8):
        cod = f"x{n}"
        _add_marca(db, codigo=cod, nome="MAGU", numero=f"9{n}", situacao="100")
        db.add(MarcaDepositante(codigo_interno=cod, nome=f"TIT {n}"))
    db.commit()

    counted = {"n": 0}

    def _count(conn, cursor, statement, params, context, executemany):
        counted["n"] += 1

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", _count)
    try:
        resp = _search(client, token, q="MAGU", match_mode="exact", page_size=100)
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert resp.status_code == 200, resp.text
    assert resp.json()["pagination"]["total"] == 11
    # Fixed count independent of row count (11 rows here). Small margin allowed
    # for auth/tenant lookups + the selective-monitoring lookup, but it must NOT
    # scale with rows.
    assert counted["n"] <= 17, f"too many queries: {counted['n']}"


def test_filters_still_work_with_enrichment(db, seeded, client):
    token = _seed(client, db)
    body = _search(client, token, numero_inpi="101").json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["titulares"] == ["BETA SA", "GAMA SA"]
    body2 = _search(client, token, q="MAGU", situacao="200", match_mode="exact").json()
    assert {i["codigo_interno"] for i in body2["items"]} == {"c3"}


def test_detail_endpoint_carries_enriched_fields(db, seeded, client):
    """The drawer's backing endpoint returns titulares + classificacoes."""
    token = _seed(client, db)
    resp = client.get("/api/marcas/c2", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["titulares"] == ["BETA SA", "GAMA SA"]
    assert body["num_titulares"] == 2
    assert body["titular_principal"] == "BETA SA"
    tipos = {c["tipo"] for c in body["classificacoes"]}
    assert tipos == {"nice", "viena"}
    # Representante legal/procurador de-duplicated across the two titulares.
    assert body["representantes_legais"] == [
        {"nome": "PROC ADVOGADOS", "cnpj_cpf": "12345678000199", "tipo_pfpj": None}
    ]
    # Legacy fields remain intact for existing consumers.
    assert body["depositantes"][0]["nome"] == "BETA SA"
    assert body["classificacoes_nice"][0]["classe_nice"] == "20"


def test_detail_endpoint_not_found(db, seeded, client):
    token = _seed(client, db)
    resp = client.get("/api/marcas/nao-existe", headers=auth_header(token))
    assert resp.status_code == 404


def test_detail_representantes_legais_empty_when_absent(db, seeded, client):
    """A marca without representante legal returns an empty list (no invention)."""
    token = _seed(client, db)
    resp = client.get("/api/marcas/c1", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["representantes_legais"] == []


def test_detail_carries_despachos_ordered_by_date(db, seeded, client):
    """The RPI/despachos history is exposed, newest first, with all columns."""
    token = _seed(client, db)
    from datetime import date

    from app.models import MarcaDespacho

    # Two despachos for c1 with out-of-order dates; one for c2 (must not leak).
    db.add(
        MarcaDespacho(
            codigo_interno="c1",
            numero_inpi="100",
            numero_rpi="1474",
            data_rpi=date(1999, 4, 6),
            codigo_despacho="003",
            descricao_despacho="PUBLICADO o pedido de registro.",
            complemento_despacho=None,
        )
    )
    db.add(
        MarcaDespacho(
            codigo_interno="c1",
            numero_inpi="100",
            numero_rpi="1600",
            data_rpi=date(2001, 9, 19),
            codigo_despacho="200",
            descricao_despacho="Pedido INVIAVEL.",
            complemento_despacho="REV. ADMINISTRATIVA",
        )
    )
    db.add(
        MarcaDespacho(codigo_interno="c2", numero_rpi="999", data_rpi=date(2020, 1, 1))
    )
    db.commit()

    resp = client.get("/api/marcas/c1", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    despachos = resp.json()["despachos"]
    assert len(despachos) == 2
    # Newest first.
    assert [d["data_rpi"] for d in despachos] == ["2001-09-19", "1999-04-06"]
    first = despachos[0]
    assert first["numero_rpi"] == "1600"
    assert first["codigo_despacho"] == "200"
    assert first["descricao_despacho"] == "Pedido INVIAVEL."
    assert first["complemento_despacho"] == "REV. ADMINISTRATIVA"


def test_detail_despachos_empty_when_absent(db, seeded, client):
    """A marca with no despachos returns an empty list (no invention)."""
    token = _seed(client, db)
    resp = client.get("/api/marcas/c3", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["despachos"] == []


def test_detail_defaults_no_logo_when_unprocessed(db, seeded, client):
    """A marca without a marcas_logos row reports tem_logo=False, status None."""
    token = _seed(client, db)
    resp = client.get("/api/marcas/c1", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tem_logo"] is False
    assert body["logo_status"] is None


def test_detail_reports_logo_status(db, seeded, client):
    """tem_logo is only True for status=OK; other statuses flow through."""
    from app.models import MarcaLogo

    token = _seed(client, db)
    db.add(MarcaLogo(codigo_interno="c1", status="SEM_IMAGEM"))
    db.add(
        MarcaLogo(
            codigo_interno="c2",
            status="OK",
            arquivo="raw/marcas/logos/62/x.jpg",
            mime="image/jpeg",
            bytes=10,
        )
    )
    db.commit()

    c1 = client.get("/api/marcas/c1", headers=auth_header(token)).json()
    assert c1["logo_status"] == "SEM_IMAGEM"
    assert c1["tem_logo"] is False

    c2 = client.get("/api/marcas/c2", headers=auth_header(token)).json()
    assert c2["logo_status"] == "OK"
    assert c2["tem_logo"] is True


def test_logo_endpoint_404_when_absent(db, seeded, client):
    token = _seed(client, db)
    resp = client.get("/api/marcas/c1/logo", headers=auth_header(token))
    assert resp.status_code == 404


def test_logo_endpoint_streams_stored_file(db, seeded, client, tmp_path, monkeypatch):
    """When a file exists on disk, the endpoint streams it with the stored mime."""
    from app.config import settings
    from app.models import MarcaLogo

    # Isolate disk writes: point the data dir at a throwaway tmp path so the test
    # never touches the real ingestion data directory.
    monkeypatch.setattr(
        settings.__class__, "data_path", property(lambda self: tmp_path)
    )

    token = _seed(client, db)

    # Write a tiny fake JPEG under the data dir and point the row at a relative
    # path (as the downloader does).
    rel = "raw/marcas/logos/62/c1.jpg"
    dest = tmp_path / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\xff\xd8\xff\xe0FAKEJPEG")
    db.add(
        MarcaLogo(
            codigo_interno="c1",
            status="OK",
            arquivo=rel,
            mime="image/jpeg",
            bytes=12,
        )
    )
    db.commit()

    resp = client.get("/api/marcas/c1/logo", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/jpeg")
    assert resp.content == b"\xff\xd8\xff\xe0FAKEJPEG"