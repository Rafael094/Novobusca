"""Testes do manifesto/reconciliador de índices (`app.db_indexes`).

Puros: não precisam de dados nem de conexão — só garantem que o manifesto não
regete nomes, está bem formado e cobre os índices que destravam a busca.
"""

from __future__ import annotations

import pytest

from app import db_indexes


def test_normalise_ignora_nome_e_schema() -> None:
    assert (
        db_indexes.normalise(
            "CREATE INDEX ix_marcas_elemento_nominativo_fold ON public.marcas "
            "USING btree (public.fold(elemento_nominativo))"
        )
        == "marcas USING btree (fold(elemento_nominativo))"
    )
    assert (
        db_indexes.normalise(
            "CREATE UNIQUE INDEX uq_marcas_codigo_interno ON public.marcas "
            "USING  btree   (codigo_interno)"
        )
        == "marcas USING btree (codigo_interno)"
    )


def test_manifesto_sem_nomes_repetidos() -> None:
    db_indexes._check_manifest()  # não deve levantar
    names = [spec.name for spec in db_indexes.ALL_INDEXES]
    assert len(names) == len(set(names))


def test_manifesto_bem_formado() -> None:
    for spec in db_indexes.ALL_INDEXES:
        assert spec.definition.startswith(f"public.{spec.table} USING "), spec.name
        assert "USING btree" in spec.definition or "USING gin" in spec.definition
    heavy = [spec for spec in db_indexes.ALL_INDEXES if spec.heavy]
    assert heavy, "os GIN trigram devem estar marcados como heavy"
    assert all("gin_trgm_ops" in spec.definition for spec in heavy)


def test_cobre_os_indices_criticos_da_busca() -> None:
    esperados = {
        # busca exata (btree na expressão) e o prefixo/contém (GIN trigram)
        "ix_marcas_elemento_nominativo_fold",
        "ix_marcas_fold_trgm",
        "ix_marcas_elemento_nominativo_trgm",
        # ordenação/prazo do dashboard e as relações (evitam N+1 Seq Scans)
        "ix_marcas_data_vigencia",
        "ix_marcas_dep_codigo_interno",
        "ix_patentes_conteudo_titulo_trgm",
    }
    assert esperados <= {spec.name for spec in db_indexes.INPI_INDEXES}


def test_analyze_apenas_de_tabelas_do_manifesto() -> None:
    indexadas = {spec.table for spec in db_indexes.INPI_INDEXES}
    assert set(db_indexes.INPI_ANALYZE_TABLES) <= indexadas


def test_tabelas_do_app_sao_comparadas_por_nome() -> None:
    # O Alembic manda na definição das tabelas do aplicativo.
    assert all(spec.by_name for spec in db_indexes.APP_INDEXES)
    assert not any(spec.by_name for spec in db_indexes.INPI_INDEXES)


def test_emit_sql_contem_todos_os_indices() -> None:
    sql = db_indexes._emit_sql()
    for spec in db_indexes.ALL_INDEXES:
        assert (
            f'CREATE INDEX IF NOT EXISTS "{spec.name}" ON {spec.definition};' in sql
        )
    assert 'ANALYZE "marcas";' in sql


@pytest.mark.parametrize(
    ("nome", "definicao"),
    [
        ("ix_marcas_elemento_nominativo_fold", "public.marcas USING btree (public.fold(elemento_nominativo))"),
        ("ix_marcas_data_deposito", "public.marcas USING btree (data_deposito DESC NULLS LAST)"),
        ("ix_marcas_fold_trgm", "public.marcas USING gin (public.fold(elemento_nominativo) gin_trgm_ops)"),
    ],
)
def test_definicoes_criticas_nao_mudaram(nome: str, definicao: str) -> None:
    """Trava a definição das expressões: mudar isso invalida o plano de busca."""
    spec = next(s for s in db_indexes.ALL_INDEXES if s.name == nome)
    assert spec.definition == definicao


# --- Índices únicos exigidos pelo `ON CONFLICT` -----------------------------


def test_indices_unicos_bem_formados() -> None:
    nomes = [name for name, _table, _cols in db_indexes.REQUIRED_UNIQUE_INDEXES]
    assert len(nomes) == len(set(nomes))
    # a que faltava em produção e derrubava o worker da RPI
    assert "uq_inpi_rpi_number" in nomes
    for spec in db_indexes._unique_specs():
        assert spec.definition.startswith(f"public.{spec.table} USING btree ("), spec.name
        assert not spec.by_name


def test_emit_sql_inclui_os_indices_unicos() -> None:
    sql = db_indexes._emit_sql()
    for spec in db_indexes._unique_specs():
        assert (
            f'CREATE UNIQUE INDEX IF NOT EXISTS "{spec.name}" ON {spec.definition};'
            in sql
        )


def test_reconcile_unique_recria_a_constraint_ausente() -> None:
    """Regressão: o banco de produção estava SEM `uq_inpi_rpi_number`.

    Aqui removemos a constraint de propósito e conferimos que a reconciliação a
    recria (única e imediata, ou seja, utilizável como árbitro do ON CONFLICT).
    """
    from sqlalchemy import text

    from app.db import engine

    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE inpi_rpi DROP CONSTRAINT IF EXISTS uq_inpi_rpi_number")
        )
        conn.execute(text("DROP INDEX IF EXISTS uq_inpi_rpi_number"))
        assert (
            conn.execute(
                text(
                    "SELECT 1 FROM pg_class WHERE relname = 'uq_inpi_rpi_number'"
                )
            ).scalar()
            is None
        )

    summary = db_indexes.Summary()
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        db_indexes._reconcile_unique(conn, summary, dry_run=False)
    finally:
        conn.close()

    assert "uq_inpi_rpi_number" in summary.created
    with engine.begin() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT i.indisunique AND i.indimmediate FROM pg_index i "
                    "JOIN pg_class c ON c.oid = i.indexrelid "
                    "WHERE c.relname = 'uq_inpi_rpi_number'"
                )
            ).scalar()
            is True
        )
