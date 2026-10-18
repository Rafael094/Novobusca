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


def test_detail_carries_peticoes(db, seeded, client):
    """Petições gravadas pelo worker do pePI aparecem no detalhe, com metadados."""
    token = _seed(client, db)
    from datetime import date, datetime, timezone

    from app.models import MarcaPepiSync, MarcaPeticao

    db.add(
        MarcaPeticao(
            codigo_interno="c1",
            numero_inpi="100",
            protocolo="800210453297",
            data_protocolo=date(2021, 12, 22),
            codigo_servico="372",
            descricao_servico="Primeiro decênio de vigência",
            cliente="ISABELA LIMA BRAZ GUEDES",
            pagamento_conciliado=True,
            banco_codigo="077",
            banco_nome="Banco Intermedium S.A.",
            data_pagamento=date(2021, 12, 22),
            valor_pagamento=298.0,
            tem_imagem=False,
        )
    )
    db.add(
        MarcaPepiSync(
            codigo_interno="c1",
            status="OK",
            peticoes_count=1,
            sincronizado_em=datetime.now(timezone.utc),
        )
    )
    db.commit()

    body = client.get("/api/marcas/c1", headers=auth_header(token)).json()
    assert len(body["peticoes"]) == 1
    p = body["peticoes"][0]
    assert p["protocolo"] == "800210453297"
    assert p["data_protocolo"] == "2021-12-22"
    assert p["codigo_servico"] == "372"
    assert p["cliente"] == "ISABELA LIMA BRAZ GUEDES"
    assert p["pagamento_conciliado"] is True
    assert p["banco_codigo"] == "077"
    assert p["valor_pagamento"] == 298.0
    assert body["peticoes_status"] == "OK"
    assert body["peticoes_sincronizado_em"] is not None


def test_detail_enfileira_marca_sem_sync(db, seeded, client):
    """Abrir uma marca sem sync cria a linha PENDING (fila do worker), sem duplicar."""
    token = _seed(client, db)
    from app.models import MarcaPepiSync

    assert db.query(MarcaPepiSync).count() == 0

    resp = client.get("/api/marcas/c3", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["peticoes"] == []
    assert resp.json()["peticoes_status"] == "PENDING"

    db.expire_all()
    row = db.query(MarcaPepiSync).filter_by(codigo_interno="c3").one()
    assert row.status == "PENDING"

    # Um segundo GET encontra a linha existente e não duplica (unique por código).
    client.get("/api/marcas/c3", headers=auth_header(token))
    db.expire_all()
    assert db.query(MarcaPepiSync).filter_by(codigo_interno="c3").count() == 1


def test_detail_reports_logo_status(db, seeded, client, tmp_path, monkeypatch):
    """``tem_logo`` reflects the *file* on disk, not only the ``marcas_logos`` row.

    A row with status ``OK`` whose image never made it to the server (e.g. the
    DB was restored without ``data/raw/marcas/logos``) must NOT advertise
    ``tem_logo`` — otherwise the UI requests ``/logo`` and gets a 404.
    """
    from app.config import settings
    from app.models import MarcaLogo

    monkeypatch.setattr(
        settings.__class__, "data_path", property(lambda self: tmp_path)
    )

    token = _seed(client, db)
    db.add(MarcaLogo(codigo_interno="c1", status="SEM_IMAGEM"))
    grupo = tmp_path / "raw" / "marcas" / "logos" / "62"
    grupo.mkdir(parents=True, exist_ok=True)
    (grupo / "c2.jpg").write_bytes(b"\xff\xd8\xff\xe0FAKEJPEG")
    db.add(
        MarcaLogo(
            codigo_interno="c2",
            status="OK",
            arquivo="raw/marcas/logos/62/c2.jpg",
            mime="image/jpeg",
            bytes=12,
        )
    )
    db.add(
        MarcaLogo(
            codigo_interno="c3",
            status="OK",
            arquivo="raw/marcas/logos/63/ausente.jpg",
            mime="image/jpeg",
            bytes=12,
        )
    )
    db.commit()

    c1 = client.get("/api/marcas/c1", headers=auth_header(token)).json()
    assert c1["logo_status"] == "SEM_IMAGEM"
    assert c1["tem_logo"] is False
    assert c1["logo"] is None

    c2 = client.get("/api/marcas/c2", headers=auth_header(token)).json()
    assert c2["logo_status"] == "OK"
    assert c2["tem_logo"] is True
    # A imagem vai embutida no detalhe: a UI não precisa de uma 2ª requisição.
    assert c2["logo"].startswith("data:image/jpeg;base64,")

    # Linha OK porém arquivo ausente no servidor → nada a mostrar.
    c3 = client.get("/api/marcas/c3", headers=auth_header(token)).json()
    assert c3["logo_status"] == "OK"
    assert c3["tem_logo"] is False
    assert c3["logo"] is None


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


_JPEG = b"\xff\xd8\xff\xe0logo-baixado-na-hora"


class _FakePool:
    """Sessão pePI falsa: devolve um JPEG e conta as chamadas."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self):
        pool = self

        class _Sess:
            def fetch(self, codigo_interno):  # noqa: ANN001
                pool.calls.append(codigo_interno)
                return "image", _JPEG, "image/jpeg"

        return _Sess()

    def close(self):
        pass


def test_detail_busca_logo_na_hora_quando_habilitado(
    db, seeded, client, tmp_path, monkeypatch
):
    """Com ``LOGO_FETCH_ENABLED=true`` o detalhe baixa, guarda e embute o logo.

    É o caminho para povoar uma VM nova sem transferir arquivo (runbook §5.2.1):
    basta abrir a marca, desde que seja Mista/Figurativa.
    """
    from app.config import settings
    from app.services import marca_logos

    monkeypatch.setattr(settings.__class__, "data_path", property(lambda self: tmp_path))
    monkeypatch.setattr(marca_logos.settings, "logo_fetch_enabled", True)
    pool = _FakePool()
    monkeypatch.setattr(marca_logos, "_POOL", pool)

    token = _seed(client, db)
    db.add(
        Marca(
            codigo_interno="mista1",
            numero_inpi="1",
            elemento_nominativo="LOGOMISTA",
            descricao_apresentacao="Mista",
        )
    )
    db.add(
        Marca(
            codigo_interno="nom1",
            numero_inpi="2",
            elemento_nominativo="SEMIMAGEM",
            descricao_apresentacao="Nominativa",
        )
    )
    db.commit()

    body = client.get("/api/marcas/mista1", headers=auth_header(token)).json()
    assert pool.calls == ["mista1"]
    assert body["tem_logo"] is True
    assert body["logo"].startswith("data:image/jpeg;base64,")
    # Ficou armazenado: a segunda leitura não toca a rede de novo.
    again = client.get("/api/marcas/mista1", headers=auth_header(token)).json()
    assert pool.calls == ["mista1"]
    assert again["logo"] == body["logo"]

    # Nominativa não carrega imagem: nem gasta requisição.
    nom = client.get("/api/marcas/nom1", headers=auth_header(token)).json()
    assert pool.calls == ["mista1"]
    assert nom["tem_logo"] is False
    assert nom["logo"] is None