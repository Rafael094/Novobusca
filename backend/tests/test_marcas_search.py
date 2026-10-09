"""Semantic tests for the /api/marcas/search match modes.

These pin down the corrected search semantics (see
``reports/SPIKE_BUSCA_MARCAS_INPI_VS_INTELLIINPI.md``):

  * ``exact`` (default) matches the whole brand name, case/accent-insensitive,
    using ``public.fold`` — it must NOT behave like a substring search and must
    NOT mix in ``descricao_apresentacao`` / ``numero_inpi``.
  * ``prefix`` matches names starting with the term (folded).
  * ``contains`` preserves the legacy substring behaviour.
  * ``match_mode`` is validated: unknown values are rejected (422), never
    silently downgraded to ``contains``.
  * existing ``numero_inpi`` / ``situacao`` filters keep working.

The real dataset counts (MAGU exact=11, contains=606) are validated separately
against the loaded database, because this suite runs on an isolated schema.
"""

from __future__ import annotations

from sqlalchemy import text

from app.models import Marca
from tests.conftest import assign_role, auth_header, login, make_tenant, make_user


def _add_marca(db, *, codigo, nome, numero=None, situacao=None, apresentacao=None):
    db.add(
        Marca(
            codigo_interno=codigo,
            numero_inpi=numero,
            elemento_nominativo=nome,
            codigo_situacao=situacao,
            descricao_apresentacao=apresentacao,
        )
    )


def _seed(client, db) -> str:
    """Setup a MARCAS_SEARCH user + a controlled dataset; return a token."""
    tenant = make_tenant(db, name="Marcas Search", module_codes=["MARCAS"])
    user = make_user(db, email="searcher@example.com", tenant_id=tenant.id)
    assign_role(db, user.id, "MARCAS_VIEW")  # includes MARCAS_SEARCH

    _add_marca(db, codigo="c1", nome="MAGU", numero="100", situacao="100")
    _add_marca(db, codigo="c2", nome="magu", numero="101", situacao="200")
    # fold('MAGÚ') == 'magu' -> same exact bucket.
    _add_marca(db, codigo="c3", nome="MAGÚ", numero="102", situacao="100")
    _add_marca(db, codigo="c4", nome="MAGUS", numero="103", situacao="100")
    _add_marca(db, codigo="c5", nome="MAGUARY", numero="104", situacao="100")
    _add_marca(db, codigo="c6", nome="X-MAGU", numero="105", situacao="100")
    # NIKE's presentation mentions MAGU: must NOT be matched by name search.
    _add_marca(
        db, codigo="c7", nome="NIKE", numero="106", situacao="300",
        apresentacao="MAGU relacionada a esportes",
    )
    db.commit()
    return login(client, "searcher@example.com")["access_token"]


def _search(client, token, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return client.get(f"/api/marcas/search?{qs}", headers=auth_header(token))



def test_fold_function_available(db):
    """The accent-folding helper used by the exact mode must exist."""
    assert db.execute(text("SELECT public.fold('MAGÚ')")).scalar_one() == "magu"


def test_exact_default_matches_whole_name_case_insensitive(db, seeded, client):
    token = _seed(client, db)
    # No match_mode -> must default to exact.
    resp = _search(client, token, q="MAGU")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    names = {it["elemento_nominativo"] for it in body["items"]}
    assert body["pagination"]["total"] == 3
    assert names == {"MAGU", "magu", "MAGÚ"}
    # NIKE must not appear even though its presentation contains MAGU.
    assert "NIKE" not in names


def test_exact_upper_lower_accent_all_equal(db, seeded, client):
    token = _seed(client, db)
    for term in ("MAGU", "magu", "Magu", "MAGÚ", "magú"):
        resp = _search(client, token, q=term, match_mode="exact")
        assert resp.status_code == 200, resp.text
        assert resp.json()["pagination"]["total"] == 3, term


def test_exact_excludes_prefix_and_contains_only(db, seeded, client):
    token = _seed(client, db)
    resp = _search(client, token, q="MAGU", match_mode="exact")
    names = {it["elemento_nominativo"] for it in resp.json()["items"]}
    assert "MAGUS" not in names
    assert "MAGUARY" not in names
    assert "X-MAGU" not in names


def test_prefix_includes_starts_with(db, seeded, client):
    token = _seed(client, db)
    resp = _search(client, token, q="MAGU", match_mode="prefix")
    assert resp.status_code == 200, resp.text
    names = {it["elemento_nominativo"] for it in resp.json()["items"]}
    exact = {
        it["elemento_nominativo"]
        for it in _search(client, token, q="MAGU", match_mode="exact").json()["items"]
    }
    assert exact.issubset(names)
    assert {"MAGU", "magu", "MAGÚ", "MAGUS", "MAGUARY"}.issubset(names)
    # Substring-only (does not start with MAGU) must be excluded.
    assert "X-MAGU" not in names
    assert resp.json()["pagination"]["total"] > len(exact)


def test_contains_keeps_legacy_substring_behaviour(db, seeded, client):
    token = _seed(client, db)
    resp = _search(client, token, q="MAGU", match_mode="contains")
    assert resp.status_code == 200, resp.text
    names = {it["elemento_nominativo"] for it in resp.json()["items"]}
    # Raw ILIKE substring: matches the unaccented occurrences only.
    assert {"MAGU", "magu", "MAGUS", "MAGUARY", "X-MAGU"}.issubset(names)
    # Still name-only: NIKE (presentation mentions MAGU) is not returned.
    assert "NIKE" not in names


def test_contains_is_not_accent_insensitive_but_exact_is(db, seeded, client):
    """Documented fold() behaviour: exact folds accents, contains (ILIKE) does not.

    fold('MAGÚ') == 'magu', so MAGÚ is an exact match for MAGU; the raw ILIKE
    used by *contains* does not fold accents and therefore misses MAGÚ.
    """
    token = _seed(client, db)
    exact = {
        it["elemento_nominativo"]
        for it in _search(client, token, q="MAGU", match_mode="exact").json()["items"]
    }
    contains = {
        it["elemento_nominativo"]
        for it in _search(client, token, q="MAGU", match_mode="contains").json()["items"]
    }
    assert "MAGÚ" in exact
    assert "MAGÚ" not in contains




def test_invalid_match_mode_is_rejected(db, seeded, client):
    token = _seed(client, db)
    resp = _search(client, token, q="MAGU", match_mode="qualquer_coisa")
    assert resp.status_code == 422, resp.text


def test_numero_inpi_filter_still_works(db, seeded, client):
    token = _seed(client, db)
    resp = _search(client, token, numero_inpi="101")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["numero_inpi"] == "101"


def test_numero_inpi_combined_with_name_exact(db, seeded, client):
    token = _seed(client, db)
    # q=MAGU (3 exact) AND numero_inpi=101 -> exactly the "magu" row.
    resp = _search(client, token, q="MAGU", numero_inpi="101", match_mode="exact")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["elemento_nominativo"] == "magu"


def test_situacao_filter_still_works(db, seeded, client):
    token = _seed(client, db)
    resp = _search(client, token, q="MAGU", situacao="100", match_mode="exact")
    assert resp.status_code == 200, resp.text
    codigos = {it["codigo_interno"] for it in resp.json()["items"]}
    assert codigos == {"c1", "c3"}  # MAGU + MAGÚ with codigo_situacao=100
