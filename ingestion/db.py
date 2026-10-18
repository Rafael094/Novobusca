"""Lightweight database access for the ingestion pipeline.

The pipeline writes to the *tracking* tables (``inpi_dataset``, ``inpi_import``,
``inpi_import_error``, ``inpi_import_checkpoint``, ``inpi_rpi``) with raw SQL.
Using raw SQL keeps the pipeline independent of the backend ORM import path and
avoids session-lifecycle surprises during long COPY loads.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import psycopg

from ingestion.config import CONFIG


def connect() -> psycopg.Connection:
    """Open a new autocommit psycopg connection to the target database."""
    conn = psycopg.connect(CONFIG.psycopg_dsn, autocommit=True)
    return conn


@contextlib.contextmanager
def cursor() -> Iterator[psycopg.Cursor]:
    """Context manager yielding a server-side cursor on a fresh connection."""
    with connect() as conn:
        with conn.cursor() as cur:
            yield cur


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Dataset registry -------------------------------------------------------
def upsert_dataset(
    *,
    name: str,
    category: str,
    source_url: str,
    status: str = "DISCOVERED",
    file_name: str | None = None,
    file_size: int | None = None,
    sha256: str | None = None,
    raw_path: str | None = None,
    extracted_path: str | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """Insert or update a dataset row; returns the dataset UUID as a string."""
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO inpi_dataset
                (id, name, category, source_url, status, file_name, file_size,
                 sha256, raw_path, extracted_path, metadata, created_at, updated_at)
            VALUES
                (%(id)s, %(name)s, %(category)s, %(source_url)s, %(status)s,
                 %(file_name)s, %(file_size)s, %(sha256)s, %(raw_path)s,
                 %(extracted_path)s, %(meta)s, %(now)s, %(now)s)
            ON CONFLICT (name) DO UPDATE SET
                category = EXCLUDED.category,
                source_url = EXCLUDED.source_url,
                status = EXCLUDED.status,
                file_name = EXCLUDED.file_name,
                file_size = EXCLUDED.file_size,
                sha256 = EXCLUDED.sha256,
                raw_path = EXCLUDED.raw_path,
                extracted_path = EXCLUDED.extracted_path,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
            RETURNING id
            """,
            {
                "id": str(uuid.uuid4()),
                "name": name,
                "category": category,
                "source_url": source_url,
                "status": status,
                "file_name": file_name,
                "file_size": file_size,
                "sha256": sha256,
                "raw_path": raw_path,
                "extracted_path": extracted_path,
                "meta": _json(meta),
                "now": _now(),
            },
        )
        row = cur.fetchone()
        return str(row[0])


def set_dataset_status(
    name: str,
    status: str,
    *,
    file_size: int | None = None,
    sha256: str | None = None,
    raw_path: str | None = None,
    extracted_path: str | None = None,
    reference_date: datetime | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Update the mutable fields of a dataset row by name."""
    sets = ["status = %(status)s", "updated_at = %(now)s"]
    params: dict[str, Any] = {"name": name, "status": status, "now": _now()}
    if file_size is not None:
        sets.append("file_size = %(file_size)s")
        params["file_size"] = file_size
    if sha256 is not None:
        sets.append("sha256 = %(sha256)s")
        params["sha256"] = sha256
    if raw_path is not None:
        sets.append("raw_path = %(raw_path)s")
        params["raw_path"] = raw_path
        sets.append("downloaded_at = %(now)s")
    if extracted_path is not None:
        sets.append("extracted_path = %(extracted_path)s")
        params["extracted_path"] = extracted_path
    if reference_date is not None:
        sets.append("reference_date = %(reference_date)s")
        params["reference_date"] = reference_date
    if meta is not None:
        sets.append("metadata = %(meta)s")
        params["meta"] = _json(meta)
    with cursor() as cur:
        cur.execute(
            f"UPDATE inpi_dataset SET {', '.join(sets)} WHERE name = %(name)s",
            params,
        )


def _json(value: Any) -> Any:
    if value is None:
        return None
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


# --- Import runs ------------------------------------------------------------
def start_import(dataset_id: str, *, meta: dict[str, Any] | None = None) -> str:
    """Create a RUNNING import run and return its UUID string."""
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO inpi_import
                (id, dataset_id, started_at, status, rows_read, rows_inserted,
                 rows_updated, rows_skipped, rows_failed, error_count, metadata)
            VALUES
                (%(id)s, %(dataset_id)s, %(now)s, 'RUNNING', 0, 0, 0, 0, 0, 0, %(meta)s)
            RETURNING id
            """,
            {
                "id": str(uuid.uuid4()),
                "dataset_id": dataset_id,
                "now": _now(),
                "meta": _json(meta),
            },
        )
        return str(cur.fetchone()[0])


def finish_import(
    import_id: str,
    *,
    status: str,
    rows_read: int = 0,
    rows_inserted: int = 0,
    rows_updated: int = 0,
    rows_skipped: int = 0,
    rows_failed: int = 0,
    error_count: int = 0,
    error_message: str | None = None,
    duration_seconds: float | None = None,
) -> None:
    with cursor() as cur:
        cur.execute(
            """
            UPDATE inpi_import SET
                finished_at = %(now)s,
                status = %(status)s,
                rows_read = %(rows_read)s,
                rows_inserted = %(rows_inserted)s,
                rows_updated = %(rows_updated)s,
                rows_skipped = %(rows_skipped)s,
                rows_failed = %(rows_failed)s,
                error_count = %(error_count)s,
                error_message = %(error_message)s,
                duration_seconds = %(duration_seconds)s
            WHERE id = %(id)s
            """,
            {
                "id": import_id,
                "now": _now(),
                "status": status,
                "rows_read": rows_read,
                "rows_inserted": rows_inserted,
                "rows_updated": rows_updated,
                "rows_skipped": rows_skipped,
                "rows_failed": rows_failed,
                "error_count": error_count,
                "error_message": error_message,
                "duration_seconds": duration_seconds,
            },
        )


def record_error(
    import_id: str,
    *,
    dataset: str | None,
    row_number: int | None,
    raw_data: str | None,
    error: str,
) -> None:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO inpi_import_error
                (id, import_id, dataset, row_number, raw_data, error, created_at)
            VALUES (%(id)s, %(import_id)s, %(dataset)s, %(row_number)s,
                    %(raw_data)s, %(error)s, %(now)s)
            """,
            {
                "id": str(uuid.uuid4()),
                "import_id": import_id,
                "dataset": dataset,
                "row_number": row_number,
                "raw_data": raw_data,
                "error": error,
                "now": _now(),
            },
        )


# --- Checkpoints ------------------------------------------------------------
def get_checkpoint(dataset_id: str, target_table: str) -> dict[str, Any] | None:
    with cursor() as cur:
        cur.execute(
            """
            SELECT last_row_number, total_rows, completed
            FROM inpi_import_checkpoint
            WHERE dataset_id = %s AND target_table = %s
            """,
            (dataset_id, target_table),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "last_row_number": row[0],
            "total_rows": row[1],
            "completed": row[2],
        }


def save_checkpoint(
    dataset_id: str,
    target_table: str,
    *,
    last_row_number: int,
    total_rows: int | None = None,
    completed: bool = False,
    meta: dict[str, Any] | None = None,
) -> None:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO inpi_import_checkpoint
                (id, dataset_id, target_table, last_row_number, total_rows,
                 completed, metadata, created_at, updated_at)
            VALUES
                (%(id)s, %(dataset_id)s, %(target_table)s, %(last)s, %(total)s,
                 %(completed)s, %(meta)s, %(now)s, %(now)s)
            ON CONFLICT (dataset_id, target_table) DO UPDATE SET
                last_row_number = EXCLUDED.last_row_number,
                total_rows = EXCLUDED.total_rows,
                completed = EXCLUDED.completed,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "id": str(uuid.uuid4()),
                "dataset_id": dataset_id,
                "target_table": target_table,
                "last": last_row_number,
                "total": total_rows,
                "completed": completed,
                "meta": _json(meta),
                "now": _now(),
            },
        )


def clear_checkpoint(dataset_id: str, target_table: str) -> None:
    with cursor() as cur:
        cur.execute(
            "DELETE FROM inpi_import_checkpoint WHERE dataset_id = %s AND target_table = %s",
            (dataset_id, target_table),
        )


# --- RPI --------------------------------------------------------------------
def upsert_rpi(
    *,
    number: str,
    edition_date: datetime | None = None,
    file_name: str | None = None,
    file_size: int | None = None,
    sha256: str | None = None,
    source_url: str | None = None,
    status: str = "DISCOVERED",
    raw_path: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Grava/atualiza a linha de controle de uma edição da RPI.

    Usa UPDATE + INSERT em vez de ``ON CONFLICT (number)`` de propósito: o worker
    também roda fora do deploy (``docker compose run --rm --no-deps rpi ...``),
    quando o passo ``app.db_indexes`` pode não ter garantido o índice único de
    ``inpi_rpi.number`` — sem ele o ``ON CONFLICT`` falha com
    ``InvalidColumnReference``. A conexão é autocommit, então a corrida com outro
    processo é resolvida refazendo o UPDATE se o INSERT colidir.
    """
    updated = """
        UPDATE inpi_rpi SET
            edition_date = %(edition_date)s,
            file_name    = %(file_name)s,
            file_size    = %(file_size)s,
            sha256       = %(sha256)s,
            source_url   = %(source_url)s,
            status       = %(status)s,
            raw_path     = %(raw_path)s,
            metadata     = %(meta)s,
            updated_at   = %(now)s
        WHERE number = %(number)s
    """
    inserted = """
        INSERT INTO inpi_rpi
            (id, number, edition_date, file_name, file_size, sha256,
             source_url, status, raw_path, metadata, created_at, updated_at)
        VALUES
            (%(id)s, %(number)s, %(edition_date)s, %(file_name)s,
             %(file_size)s, %(sha256)s, %(source_url)s, %(status)s,
             %(raw_path)s, %(meta)s, %(now)s, %(now)s)
    """
    values = {
        "id": str(uuid.uuid4()),
        "number": number,
        "edition_date": edition_date,
        "file_name": file_name,
        "file_size": file_size,
        "sha256": sha256,
        "source_url": source_url,
        "status": status,
        "raw_path": raw_path,
        "meta": _json(meta),
        "now": _now(),
    }
    with cursor() as cur:
        cur.execute(updated, values)
        if cur.rowcount:
            return
        try:
            cur.execute(inserted, values)
        except psycopg.errors.UniqueViolation:
            # Outro processo criou a mesma edição no meio: o UPDATE dele já valeu.
            cur.execute(updated, values)


def get_rpi(number: str) -> dict[str, Any] | None:
    """Devolve ``{number, edition_date, status, metadata}`` de uma edição RPI."""
    with cursor() as cur:
        cur.execute(
            "SELECT number, edition_date, status, metadata FROM inpi_rpi WHERE number = %s",
            (number,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "number": row[0],
        "edition_date": row[1],
        "status": row[2],
        "metadata": row[3] or {},
    }


# --- Despachos publicados na RPI --------------------------------------------
def marcas_codigos_por_numero(numeros: list[str]) -> dict[str, list[str]]:
    """Mapeia ``marcas.numero_inpi`` → ``[codigo_interno, ...]``.

    O XML da RPI só traz o número do processo (9 dígitos, o ``numero_inpi``); o
    ``codigo_interno`` que o app usa é resolvido aqui. Um mesmo processo pode ter
    mais de uma linha em ``marcas`` em casos-limite, daí a lista.
    """
    if not numeros:
        return {}
    out: dict[str, list[str]] = {}
    with cursor() as cur:
        cur.execute(
            "SELECT numero_inpi, codigo_interno FROM marcas WHERE numero_inpi = ANY(%s)",
            (list(numeros),),
        )
        for numero_inpi, codigo_interno in cur.fetchall():
            out.setdefault(numero_inpi, []).append(codigo_interno)
    return out


def patentes_digitos_map() -> dict[str, tuple[str, str]]:
    """Mapa ``só-dígitos(numero_inpi)`` → ``(codigo_interno, numero_inpi)``.

    A RPI de Patentes formata o número de formas variadas (``BR 10 2020 000000-0``,
    ``PI 0000000-0``, ...) e o CSV de dados abertos usa outro formato; casar pelo
    conjunto de dígitos é o que os leitores de referência fazem. São ~1 M de
    linhas (duas colunas), carregadas uma vez por rodada.
    """
    out: dict[str, tuple[str, str]] = {}
    with cursor() as cur:
        cur.execute(
            "SELECT numero_inpi, codigo_interno FROM patentes WHERE numero_inpi IS NOT NULL"
        )
        for numero_inpi, codigo_interno in cur.fetchall():
            digits = "".join(ch for ch in numero_inpi if ch.isdigit())
            if digits and digits not in out:
                out[digits] = (codigo_interno, numero_inpi)
    return out


def _insert_despachos(
    table: str, *, numero_rpi: str, data_rpi: Any, rows: list[dict[str, Any]]
) -> int:
    """Insere despachos em lote, ignorando (via anti-join) os que já existem.

    A identidade de um despacho é ``(codigo_interno, numero_rpi,
    codigo_despacho, complemento_despacho)`` — é o que torna o worker
    idempotente mesmo quando o CSV de dados abertos já trouxe a publicação da
    semana. Roda numa transação única: ou o lote entra inteiro, ou nada entra.
    """
    if not rows:
        return 0

    # ``marcas_despachos`` tem ``descricao_despacho``; ``patentes_despachos`` não.
    cols = [
        "codigo_interno",
        "numero_inpi",
        "codigo_despacho",
        "complemento_despacho",
    ]
    if table == "marcas_despachos":
        cols.append("descricao_despacho")

    names = [f"a{i}" for i in range(len(cols))]
    arrays = ", ".join(f"%({name})s::text[]" for name in names)
    params: dict[str, Any] = {
        name: [row.get(col) for row in rows] for name, col in zip(names, cols)
    }
    params["numero_rpi"] = numero_rpi
    params["data_rpi"] = data_rpi
    insert_cols = ", ".join([*cols, "numero_rpi", "data_rpi"])
    select_cols = ", ".join(
        ["gen_random_uuid()", *names, "%(numero_rpi)s::text", "%(data_rpi)s::date"]
    )
    sql = (
        f"INSERT INTO {table} (id, {insert_cols}) "
        f"SELECT {select_cols} "
        f"FROM unnest({arrays}) AS v({', '.join(names)}) "
        f"WHERE NOT EXISTS (SELECT 1 FROM {table} d "
        "WHERE d.codigo_interno = v.a0 "
        "AND d.numero_rpi IS NOT DISTINCT FROM %(numero_rpi)s::text "
        "AND d.codigo_despacho IS NOT DISTINCT FROM v.a2 "
        "AND coalesce(d.complemento_despacho, '') = coalesce(v.a3, ''))"
    )
    with psycopg.connect(CONFIG.psycopg_dsn) as conn:  # transacional (não autocommit)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


def insert_marcas_despachos(
    *, numero_rpi: str, data_rpi: Any, rows: list[dict[str, Any]]
) -> int:
    """Grava despachos em ``marcas_despachos`` (idempotente). Devolve o nº novo."""
    return _insert_despachos(
        "marcas_despachos", numero_rpi=numero_rpi, data_rpi=data_rpi, rows=rows
    )


def insert_patentes_despachos(
    *, numero_rpi: str, data_rpi: Any, rows: list[dict[str, Any]]
) -> int:
    """Grava despachos em ``patentes_despachos`` (idempotente). Devolve o nº novo."""
    return _insert_despachos(
        "patentes_despachos", numero_rpi=numero_rpi, data_rpi=data_rpi, rows=rows
    )


# --- Marcas logotipos (pePI images) ------------------------------------------
def logo_codes(
    *,
    apresentacoes: list[str] | None = None,
    only_pending: bool = True,
    limit: int | None = None,
) -> list[str]:
    """Return ``codigo_interno`` values that still need a logotipo.

    ``apresentacoes`` filters by ``marcas.descricao_apresentacao`` (e.g. only
    ``Mista``/``Figurativa``, which are the ones that usually carry an image).
    When ``only_pending`` is True, codes already recorded in ``marcas_logos``
    with a terminal status (``OK``/``SEM_IMAGEM``) are skipped so the downloader
    can resume cheaply.
    """
    where: list[str] = ["m.codigo_interno IS NOT NULL"]
    params: dict[str, Any] = {}
    if apresentacoes:
        where.append("m.descricao_apresentacao = ANY(%(apres)s)")
        params["apres"] = apresentacoes
    if only_pending:
        where.append(
            """
            NOT EXISTS (
                SELECT 1 FROM marcas_logos l
                WHERE l.codigo_interno = m.codigo_interno
                  AND l.status IN ('OK', 'SEM_IMAGEM')
            )
            """
        )
    sql = f"SELECT m.codigo_interno FROM marcas m WHERE {' AND '.join(where)}"
    # ``ORDER BY`` explícito (usa ``ix_marcas_codigo_interno``): sem ele o
    # ``LIMIT`` devolve a ordem que o planner quiser, então rodadas sucessivas
    # com ``--limite`` podem reprocessar sempre as mesmas linhas — e, como quem
    # falha (``ERROR``) volta a ficar pendente, o lote nunca alcança códigos
    # novos. Com ordem determinística o progresso é garantido e retomável.
    sql += " ORDER BY m.codigo_interno"
    if limit:
        sql += " LIMIT %(limit)s"
        params["limit"] = limit
    with cursor() as cur:
        cur.execute(sql, params)
        return [r[0] for r in cur.fetchall()]


def upsert_logo(
    *,
    codigo_interno: str,
    status: str,
    arquivo: str | None = None,
    mime: str | None = None,
    bytes_: int | None = None,
    sha256: str | None = None,
    tentativas: int = 0,
    erro: str | None = None,
    baixado_em: datetime | None = None,
) -> None:
    """Insert or update a ``marcas_logos`` row keyed by ``codigo_interno``."""
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO marcas_logos
                (id, codigo_interno, arquivo, mime, bytes, sha256, status,
                 tentativas, erro, baixado_em, created_at, updated_at)
            VALUES
                (%(id)s, %(codigo_interno)s, %(arquivo)s, %(mime)s, %(bytes)s,
                 %(sha256)s, %(status)s, %(tentativas)s, %(erro)s,
                 %(baixado_em)s, %(now)s, %(now)s)
            ON CONFLICT (codigo_interno) DO UPDATE SET
                arquivo = EXCLUDED.arquivo,
                mime = EXCLUDED.mime,
                bytes = EXCLUDED.bytes,
                sha256 = EXCLUDED.sha256,
                status = EXCLUDED.status,
                tentativas = EXCLUDED.tentativas,
                erro = EXCLUDED.erro,
                baixado_em = EXCLUDED.baixado_em,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "id": str(uuid.uuid4()),
                "codigo_interno": codigo_interno,
                "arquivo": arquivo,
                "mime": mime,
                "bytes": bytes_,
                "sha256": sha256,
                "status": status,
                "tentativas": tentativas,
                "erro": erro,
                "baixado_em": baixado_em,
                "now": _now(),
            },
        )


# --- Marcas petições (pePI detail page) --------------------------------------
def pending_codes(*, limit: int | None = None) -> list[str]:
    """``codigo_interno`` marcados como ``PENDING`` na fila do pePI.

    A fila é alimentada sob demanda (o endpoint de detalhe da marca insere uma
    linha ``PENDING``) e o worker a drena **antes** do lote em massa, para que as
    marcas que alguém abriu na tela cheguem primeiro.
    """
    sql = "SELECT codigo_interno FROM marcas_pepi_sync WHERE status = 'PENDING'"
    params: dict[str, Any] = {}
    sql += " ORDER BY created_at"
    if limit:
        sql += " LIMIT %(limit)s"
        params["limit"] = limit
    with cursor() as cur:
        cur.execute(sql, params)
        return [r[0] for r in cur.fetchall()]


def peticao_codes(
    *,
    apresentacoes: list[str] | None = None,
    only_pending: bool = True,
    limit: int | None = None,
    codes: list[str] | None = None,
    dias: int | None = None,
) -> list[str]:
    """``codigo_interno`` de marcas que ainda precisam ter as petições buscadas.

    Filtra por ``marcas.descricao_apresentacao`` (ex.: ``Mista``/``Figurativa``,
    que é onde há mais processos com imagem) e, com ``only_pending=True``, pula
    os códigos já sincronizados com status terminal (``OK``/``SEM_DADOS``). Com
    ``dias`` > 0, re-processa os terminais mais antigos que o TTL (atualização
    periódica). ``ORDER BY m.codigo_interno`` usa o índice da chave para parar
    cedo no ``LIMIT`` em vez de varrer/ordenar 6,6 M de linhas.
    """
    where: list[str] = ["m.codigo_interno IS NOT NULL"]
    params: dict[str, Any] = {}
    if codes:
        where.append("m.codigo_interno = ANY(%(codes)s)")
        params["codes"] = codes
    if apresentacoes:
        where.append("m.descricao_apresentacao = ANY(%(apres)s)")
        params["apres"] = apresentacoes

    join = ""
    if only_pending:
        join = "LEFT JOIN marcas_pepi_sync s ON s.codigo_interno = m.codigo_interno"
        terminal = (
            "s.status IN ('OK', 'SEM_DADOS')"
            if not dias
            else (
                "s.status IN ('OK', 'SEM_DADOS') "
                "AND s.sincronizado_em >= now() - %(ttl)s::interval"
            )
        )
        if dias:
            params["ttl"] = f"{int(dias)} days"
        where.append(
            f"(s.codigo_interno IS NULL OR NOT ({terminal}))"
            " AND (s.status IS DISTINCT FROM 'ERROR' OR s.tentativas < 5)"
        )

    sql = (
        f"SELECT m.codigo_interno FROM marcas m {join} "
        f"WHERE {' AND '.join(where)} ORDER BY m.codigo_interno"
    )
    if limit:
        sql += " LIMIT %(limit)s"
        params["limit"] = limit
    with cursor() as cur:
        cur.execute(sql, params)
        return [r[0] for r in cur.fetchall()]


def replace_peticoes(
    *, codigo_interno: str, rows: list[dict[str, Any]], numero_inpi: str | None = None
) -> int:
    """Substitui as petições de uma marca pelo conjunto recém-lido do pePI.

    Numa única transação: apaga o que havia e insere o conjunto atual (assim uma
    petição retirada na fonte também some daqui). Idempotente e seguro para
    reexecução. Devolve quantas linhas ficaram gravadas.
    """
    insert = """
        INSERT INTO marcas_peticoes
            (id, codigo_interno, numero_inpi, protocolo, data_protocolo,
             codigo_servico, descricao_servico, cliente, pagamento_conciliado,
             banco_codigo, banco_nome, data_pagamento, valor_pagamento,
             delivery, data_delivery, tem_imagem, created_at, updated_at)
        VALUES
            (%(id)s, %(codigo_interno)s, %(numero_inpi)s, %(protocolo)s,
             %(data_protocolo)s, %(codigo_servico)s, %(descricao_servico)s,
             %(cliente)s, %(pagamento_conciliado)s, %(banco_codigo)s,
             %(banco_nome)s, %(data_pagamento)s, %(valor_pagamento)s,
             %(delivery)s, %(data_delivery)s, %(tem_imagem)s, %(now)s, %(now)s)
        ON CONFLICT (codigo_interno, protocolo) DO UPDATE SET
            numero_inpi = EXCLUDED.numero_inpi,
            data_protocolo = EXCLUDED.data_protocolo,
            codigo_servico = EXCLUDED.codigo_servico,
            descricao_servico = EXCLUDED.descricao_servico,
            cliente = EXCLUDED.cliente,
            pagamento_conciliado = EXCLUDED.pagamento_conciliado,
            banco_codigo = EXCLUDED.banco_codigo,
            banco_nome = EXCLUDED.banco_nome,
            data_pagamento = EXCLUDED.data_pagamento,
            valor_pagamento = EXCLUDED.valor_pagamento,
            delivery = EXCLUDED.delivery,
            data_delivery = EXCLUDED.data_delivery,
            tem_imagem = EXCLUDED.tem_imagem,
            updated_at = EXCLUDED.updated_at
    """
    now = _now()
    with psycopg.connect(CONFIG.psycopg_dsn) as conn:  # transacional (não autocommit)
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM marcas_peticoes WHERE codigo_interno = %s",
                (codigo_interno,),
            )
            for row in rows:
                params = dict(row)
                params.update(
                    id=str(uuid.uuid4()),
                    codigo_interno=codigo_interno,
                    numero_inpi=row.get("numero_inpi") or numero_inpi,
                    now=now,
                )
                cur.execute(insert, params)
    return len(rows)


def upsert_pepi_sync(
    *,
    codigo_interno: str,
    status: str,
    peticoes_count: int = 0,
    http_status: int | None = None,
    revista: str | None = None,
    dados_atualizados_em: Any = None,
    tentativas: int = 0,
    erro: str | None = None,
    sincronizado_em: datetime | None = None,
) -> None:
    """Grava o estado da sincronização das petições de uma marca (upsert)."""
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO marcas_pepi_sync
                (id, codigo_interno, status, peticoes_count, http_status, revista,
                 dados_atualizados_em, tentativas, erro, sincronizado_em,
                 created_at, updated_at)
            VALUES
                (%(id)s, %(codigo_interno)s, %(status)s, %(peticoes_count)s,
                 %(http_status)s, %(revista)s, %(dados_atualizados_em)s,
                 %(tentativas)s, %(erro)s, %(sincronizado_em)s, %(now)s, %(now)s)
            ON CONFLICT (codigo_interno) DO UPDATE SET
                status = EXCLUDED.status,
                peticoes_count = EXCLUDED.peticoes_count,
                http_status = EXCLUDED.http_status,
                revista = EXCLUDED.revista,
                dados_atualizados_em = EXCLUDED.dados_atualizados_em,
                tentativas = EXCLUDED.tentativas,
                erro = EXCLUDED.erro,
                sincronizado_em = EXCLUDED.sincronizado_em,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "id": str(uuid.uuid4()),
                "codigo_interno": codigo_interno,
                "status": status,
                "peticoes_count": peticoes_count,
                "http_status": http_status,
                "revista": revista,
                "dados_atualizados_em": dados_atualizados_em,
                "tentativas": tentativas,
                "erro": erro,
                "sincronizado_em": sincronizado_em,
                "now": _now(),
            },
        )
