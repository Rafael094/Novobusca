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
from datetime import date, datetime, timezone
from typing import Any

import psycopg

from ingestion.config import CONFIG
from ingestion.rpi_parse import process_key


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
    """Devolve o estado completo de uma edição RPI.

    Inclui os campos de auditoria do arquivo (``file_name``/``file_size``/
    ``sha256``/``source_url``/``raw_path``) para que o worker possa **preservá-los**
    ao gravar estados intermediários (``PROCESSING``) — antes, o upsert zerava
    esses campos e uma falha depois do download apagava a trilha de auditoria.
    """
    with cursor() as cur:
        cur.execute(
            """
            SELECT number, edition_date, status, metadata, file_name, file_size,
                   sha256, source_url, raw_path
            FROM inpi_rpi WHERE number = %s
            """,
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
        "file_name": row[4],
        "file_size": row[5],
        "sha256": row[6],
        "source_url": row[7],
        "raw_path": row[8],
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
    # Uma edição grande pode trazer dezenas de milhares de processos. Mandar
    # tudo num único array ``ANY`` incha o parâmetro e pode levar o planner a
    # um Seq Scan; lotes de 10 mil mantêm o índice ``ix_marcas_numero_inpi``
    # sendo usado e limitam o pico de memória.
    unique = list(dict.fromkeys(n for n in numeros if n))
    with cursor() as cur:
        for start in range(0, len(unique), 10_000):
            chunk = unique[start : start + 10_000]
            cur.execute(
                "SELECT numero_inpi, codigo_interno FROM marcas WHERE numero_inpi = ANY(%s)",
                (chunk,),
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


def _digitos_map(table: str) -> dict[str, tuple[str, str]]:
    """Mapa ``process_key(numero_inpi)`` → ``(codigo_interno, numero_inpi)``.

    Usado por Desenhos Industriais e Programas de Computador. A chave canônica
    remove o dígito verificador que só a RPI publica (13 → 12 dígitos), então o
    mesmo mapa casa tanto os números antigos (``DI2600088``) quanto os atuais.
    """
    out: dict[str, tuple[str, str]] = {}
    with cursor() as cur:
        cur.execute(
            f"SELECT numero_inpi, codigo_interno FROM {table} "
            "WHERE numero_inpi IS NOT NULL"
        )
        for numero_inpi, codigo_interno in cur.fetchall():
            key = process_key(numero_inpi)
            if key and key not in out:
                out[key] = (codigo_interno, numero_inpi)
    return out


def desenhos_digitos_map() -> dict[str, tuple[str, str]]:
    """Mapa canônico dos processos de Desenho Industrial já carregados."""
    return _digitos_map("desenhos")


def softwares_digitos_map() -> dict[str, tuple[str, str]]:
    """Mapa canônico dos processos de Programa de Computador já carregados."""
    return _digitos_map("softwares")


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

    # ``marcas_despachos``/``desenhos_despachos``/``softwares_despachos`` têm
    # ``descricao_despacho``; ``patentes_despachos`` não.
    cols = [
        "codigo_interno",
        "numero_inpi",
        "codigo_despacho",
        "complemento_despacho",
    ]
    if table in {"marcas_despachos", "desenhos_despachos", "softwares_despachos"}:
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


def insert_desenhos_despachos(
    *, numero_rpi: str, data_rpi: Any, rows: list[dict[str, Any]]
) -> int:
    """Grava despachos em ``desenhos_despachos`` (idempotente)."""
    return _insert_despachos(
        "desenhos_despachos", numero_rpi=numero_rpi, data_rpi=data_rpi, rows=rows
    )


def insert_softwares_despachos(
    *, numero_rpi: str, data_rpi: Any, rows: list[dict[str, Any]]
) -> int:
    """Grava despachos em ``softwares_despachos`` (idempotente)."""
    return _insert_despachos(
        "softwares_despachos", numero_rpi=numero_rpi, data_rpi=data_rpi, rows=rows
    )


def _parameter_cast(column: str, value: Any) -> str:
    """Tipo SQL explícito para o parâmetro.

    O mesmo parâmetro aparece no ``SELECT`` do ``INSERT`` e no anti-join. Sem o
    cast, o PostgreSQL pode deduzir tipos diferentes para ele (ex.: ``text`` no
    anti-join e ``character varying`` na coluna de destino), resultando em
    ``AmbiguousParameter``. O cast fixa um único tipo nos dois lugares.
    """
    if column == "id":
        return "uuid"
    if column.startswith("data_") or isinstance(value, date):
        return "date"
    return "text"


def _insert_missing(
    cur: psycopg.Cursor,
    table: str,
    values: dict[str, Any],
    key_columns: tuple[str, ...],
    *,
    case_insensitive: tuple[str, ...] = (),
) -> int:
    """Insere ``values`` só quando a chave natural ainda não existe.

    As tabelas filhas do dump não têm UNIQUE (o CSV pode repetir linhas), então
    não dá para usar ``ON CONFLICT``. O anti-join mantém a reingestão da mesma
    edição idempotente e evita duplicar dados já trazidos pelo CSV.
    """
    columns = list(values)
    params = {f"v{i}": values[col] for i, col in enumerate(columns)}
    select = ", ".join(
        f"%({name})s::{_parameter_cast(col, values[col])}"
        for name, col in zip(params, columns)
    )
    conditions: list[str] = []
    for i, col in enumerate(columns):
        if col not in key_columns:
            continue
        name = f"v{i}"
        if col in case_insensitive:
            conditions.append(
                f"upper(trim(coalesce({col}::text, ''))) = "
                f"upper(trim(coalesce(%({name})s::text, '')))"
            )
        else:
            conditions.append(
                f"{col}::text IS NOT DISTINCT FROM %({name})s::text"
            )
    if not conditions:
        raise ValueError(f"{table}: nenhuma coluna de chave informada")
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"SELECT {select} "
        f"WHERE NOT EXISTS (SELECT 1 FROM {table} WHERE {' AND '.join(conditions)})"
    )
    cur.execute(sql, params)
    return max(0, cur.rowcount)


def _desenho_base_params(proc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "codigo_interno": proc["codigo_interno"],
        "numero_inpi": proc.get("numero_inpi"),
        "data_deposito": proc.get("data_deposito"),
        "data_concessao": proc.get("data_concessao"),
        "data_publicacao": proc.get("data_publicacao"),
        "titulo": proc.get("titulo"),
        "codigo_situacao": proc.get("codigo_situacao"),
        "descricao_situacao": proc.get("descricao_situacao"),
        "now": _now(),
    }


def upsert_desenhos_rpi(processos: list[dict[str, Any]]) -> dict[str, int]:
    """Atualiza a base e as tabelas filhas de Desenho Industrial com a RPI.

    Só processos já casados com o dump devem chegar aqui (a RPI não traz o
    ``codigo_interno``). Campos bibliográficos existentes nunca são apagados:
    usamos ``COALESCE``; a situação é atualizada para o despacho mais recente
    processado. Todas as escritas acontecem numa única transação.
    """
    stats = {
        "processos": 0,
        "titulares": 0,
        "autores": 0,
        "procuradores": 0,
        "classificacoes": 0,
        "prioridades": 0,
        "vinculos": 0,
    }
    if not processos:
        return stats

    base_sql = """
        INSERT INTO desenhos
            (id, codigo_interno, numero_inpi, data_deposito, data_concessao,
             data_publicacao, titulo, codigo_situacao, descricao_situacao,
             created_at, updated_at)
        VALUES
            (%(id)s, %(codigo_interno)s, %(numero_inpi)s, %(data_deposito)s,
             %(data_concessao)s, %(data_publicacao)s, %(titulo)s,
             %(codigo_situacao)s, %(descricao_situacao)s, %(now)s, %(now)s)
        ON CONFLICT (codigo_interno) DO UPDATE SET
            numero_inpi = COALESCE(desenhos.numero_inpi, EXCLUDED.numero_inpi),
            data_deposito = COALESCE(desenhos.data_deposito, EXCLUDED.data_deposito),
            data_concessao = COALESCE(desenhos.data_concessao, EXCLUDED.data_concessao),
            data_publicacao = COALESCE(desenhos.data_publicacao, EXCLUDED.data_publicacao),
            titulo = COALESCE(desenhos.titulo, EXCLUDED.titulo),
            codigo_situacao = COALESCE(
                EXCLUDED.codigo_situacao, desenhos.codigo_situacao
            ),
            descricao_situacao = COALESCE(
                EXCLUDED.descricao_situacao, desenhos.descricao_situacao
            ),
            updated_at = EXCLUDED.updated_at
    """
    conteudo_sql = """
        INSERT INTO desenhos_conteudo
            (id, codigo_interno, numero_inpi, titulo)
        VALUES (%(id)s, %(codigo_interno)s, %(numero_inpi)s, %(titulo)s)
    """
    conteudo_update = """
        UPDATE desenhos_conteudo SET
            numero_inpi = COALESCE(numero_inpi, %(numero_inpi)s),
            titulo = COALESCE(titulo, %(titulo)s)
        WHERE codigo_interno = %(codigo_interno)s
    """

    with psycopg.connect(CONFIG.psycopg_dsn) as conn:
        with conn.cursor() as cur:
            for proc in processos:
                if not proc.get("codigo_interno"):
                    continue
                params = _desenho_base_params(proc)
                cur.execute(base_sql, params)
                stats["processos"] += 1

                titulo = proc.get("titulo")
                if titulo:
                    conteudo_params = {
                        "id": str(uuid.uuid4()),
                        "codigo_interno": proc["codigo_interno"],
                        "numero_inpi": proc.get("numero_inpi"),
                        "titulo": titulo,
                    }
                    cur.execute(conteudo_update, conteudo_params)
                    if not cur.rowcount:
                        cur.execute(conteudo_sql, conteudo_params)

                for row in proc.get("titulares", []):
                    stats["titulares"] += _insert_missing(
                        cur,
                        "desenhos_depositantes",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno": proc["codigo_interno"],
                            "numero_inpi": proc.get("numero_inpi"),
                            "ordem": row.get("ordem"),
                            "nome": row.get("nome"),
                            "cpf_cnpj": row.get("cpf_cnpj"),
                            "tipo_pessoa": row.get("tipo_pessoa"),
                            "pais": row.get("pais"),
                            "estado": row.get("estado"),
                        },
                        ("codigo_interno", "nome", "cpf_cnpj", "pais"),
                        case_insensitive=("nome",),
                    )

                for row in proc.get("autores", []):
                    stats["autores"] += _insert_missing(
                        cur,
                        "desenhos_autores",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno": proc["codigo_interno"],
                            "numero_inpi": proc.get("numero_inpi"),
                            "ordem": row.get("ordem"),
                            "autor": row.get("nome"),
                            "pais": row.get("pais"),
                            "estado": row.get("estado"),
                        },
                        ("codigo_interno", "autor"),
                        case_insensitive=("autor",),
                    )

                for row in proc.get("procuradores", []):
                    stats["procuradores"] += _insert_missing(
                        cur,
                        "desenhos_procuradores",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno": proc["codigo_interno"],
                            "numero_inpi": proc.get("numero_inpi"),
                            "procurador": row.get("nome"),
                            "cpf_cnpj": row.get("cpf_cnpj"),
                            "tipo_pessoa": row.get("tipo_pessoa"),
                        },
                        ("codigo_interno", "procurador", "cpf_cnpj"),
                        case_insensitive=("procurador",),
                    )

                for row in proc.get("classificacoes", []):
                    stats["classificacoes"] += _insert_missing(
                        cur,
                        "desenhos_classificacoes",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno": proc["codigo_interno"],
                            "numero_inpi": proc.get("numero_inpi"),
                            "ordem": row.get("ordem"),
                            "classificacao_locarno": row.get("classificacao_locarno"),
                            "descricao_locarno": row.get("descricao_locarno"),
                        },
                        ("codigo_interno", "classificacao_locarno"),
                    )

                for row in proc.get("prioridades", []):
                    stats["prioridades"] += _insert_missing(
                        cur,
                        "desenhos_prioridades",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno": proc["codigo_interno"],
                            "numero_inpi": proc.get("numero_inpi"),
                            "pais_prioridade": row.get("pais_prioridade"),
                            "numero_prioridade": row.get("numero_prioridade"),
                            "data_prioridade": row.get("data_prioridade"),
                        },
                        ("codigo_interno", "pais_prioridade", "numero_prioridade"),
                    )

                for row in proc.get("vinculos", []):
                    stats["vinculos"] += _insert_missing(
                        cur,
                        "desenhos_vinculos",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno_derivado": row.get(
                                "codigo_interno_derivado"
                            ),
                            "numero_inpi_derivado": row.get("numero_inpi_derivado"),
                            "codigo_interno_origem": proc["codigo_interno"],
                            "numero_inpi_origem": proc.get("numero_inpi"),
                            "data_vinculo": row.get("data_vinculo"),
                            "tipo_vinculo": row.get("tipo_vinculo"),
                        },
                        ("codigo_interno_origem", "numero_inpi_derivado", "tipo_vinculo"),
                    )
    return stats


def upsert_softwares_rpi(processos: list[dict[str, Any]]) -> dict[str, int]:
    """Atualiza a base e as tabelas filhas de Programa de Computador com a RPI."""
    stats = {
        "processos": 0,
        "titulares": 0,
        "autores": 0,
        "linguagens": 0,
        "tipos": 0,
        "campos": 0,
    }
    if not processos:
        return stats

    base_sql = """
        INSERT INTO softwares
            (id, codigo_interno, numero_inpi, data_publicacao, data_criacao,
             titulo, codigo_situacao, descricao_situacao, created_at, updated_at)
        VALUES
            (%(id)s, %(codigo_interno)s, %(numero_inpi)s, %(data_publicacao)s,
             %(data_criacao)s, %(titulo)s, %(codigo_situacao)s,
             %(descricao_situacao)s, %(now)s, %(now)s)
        ON CONFLICT (codigo_interno) DO UPDATE SET
            numero_inpi = COALESCE(softwares.numero_inpi, EXCLUDED.numero_inpi),
            data_publicacao = COALESCE(
                softwares.data_publicacao, EXCLUDED.data_publicacao
            ),
            data_criacao = COALESCE(softwares.data_criacao, EXCLUDED.data_criacao),
            titulo = COALESCE(softwares.titulo, EXCLUDED.titulo),
            codigo_situacao = COALESCE(
                EXCLUDED.codigo_situacao, softwares.codigo_situacao
            ),
            descricao_situacao = COALESCE(
                EXCLUDED.descricao_situacao, softwares.descricao_situacao
            ),
            updated_at = EXCLUDED.updated_at
    """

    with psycopg.connect(CONFIG.psycopg_dsn) as conn:
        with conn.cursor() as cur:
            for proc in processos:
                if not proc.get("codigo_interno"):
                    continue
                cur.execute(
                    base_sql,
                    {
                        "id": str(uuid.uuid4()),
                        "codigo_interno": proc["codigo_interno"],
                        "numero_inpi": proc.get("numero_inpi"),
                        "data_publicacao": proc.get("data_publicacao"),
                        "data_criacao": proc.get("data_criacao"),
                        "titulo": proc.get("titulo"),
                        "codigo_situacao": proc.get("codigo_situacao"),
                        "descricao_situacao": proc.get("descricao_situacao"),
                        "now": _now(),
                    },
                )
                stats["processos"] += 1

                for row in proc.get("titulares", []):
                    stats["titulares"] += _insert_missing(
                        cur,
                        "softwares_titulares",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno": proc["codigo_interno"],
                            "numero_inpi": proc.get("numero_inpi"),
                            "ordem": row.get("ordem"),
                            "nome": row.get("nome"),
                            "cpf_cnpj": row.get("cpf_cnpj"),
                            "tipo_pessoa": row.get("tipo_pessoa"),
                            "pais": row.get("pais"),
                            "estado": row.get("estado"),
                        },
                        ("codigo_interno", "nome"),
                        case_insensitive=("nome",),
                    )

                for row in proc.get("autores", []):
                    stats["autores"] += _insert_missing(
                        cur,
                        "softwares_autores",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno": proc["codigo_interno"],
                            "numero_inpi": proc.get("numero_inpi"),
                            "ordem": row.get("ordem"),
                            "autor": row.get("nome"),
                            "pais": row.get("pais"),
                            "estado": row.get("estado"),
                        },
                        ("codigo_interno", "autor"),
                        case_insensitive=("autor",),
                    )

                for row in proc.get("linguagens", []):
                    stats["linguagens"] += _insert_missing(
                        cur,
                        "softwares_linguagens",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno": proc["codigo_interno"],
                            "numero_inpi": proc.get("numero_inpi"),
                            "linguagem": row,
                        },
                        ("codigo_interno", "linguagem"),
                        case_insensitive=("linguagem",),
                    )

                for row in proc.get("tipos", []):
                    stats["tipos"] += _insert_missing(
                        cur,
                        "softwares_tipos",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno": proc["codigo_interno"],
                            "numero_inpi": proc.get("numero_inpi"),
                            "tipo": row.get("tipo"),
                            "campo_aplicacao": row.get("campo_aplicacao"),
                        },
                        ("codigo_interno", "tipo", "campo_aplicacao"),
                    )

                for row in proc.get("campos", []):
                    stats["campos"] += _insert_missing(
                        cur,
                        "softwares_campos",
                        {
                            "id": str(uuid.uuid4()),
                            "codigo_interno": proc["codigo_interno"],
                            "numero_inpi": proc.get("numero_inpi"),
                            "campo": row.get("campo"),
                            "valor": row.get("valor"),
                        },
                        ("codigo_interno", "campo", "valor"),
                    )
    return stats


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


def get_logo(codigo_interno: str) -> dict[str, Any] | None:
    """Metadado de um logotipo já processado (ou ``None``).

    Usado pelo pipeline de imagens da RPI para evitar baixar de novo o que o
    worker do pePI já armazenou (cache local) e para nunca sobrescrever um
    ``OK`` com um ``SEM_IMAGEM``/``ERROR``.
    """
    with cursor() as cur:
        cur.execute(
            """
            SELECT codigo_interno, arquivo, mime, bytes, sha256, status,
                   tentativas, erro, baixado_em
            FROM marcas_logos WHERE codigo_interno = %s
            """,
            (codigo_interno,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "codigo_interno": row[0],
        "arquivo": row[1],
        "mime": row[2],
        "bytes": row[3],
        "sha256": row[4],
        "status": row[5],
        "tentativas": row[6],
        "erro": row[7],
        "baixado_em": row[8],
    }


# --- Imagens/logotipos publicados na RPI -------------------------------------
def upsert_rpi_imagem(
    *,
    numero_rpi: str,
    numero_processo: str,
    nome_imagem: str | None = None,
    codigo_interno: str | None = None,
    status: str = "PENDING",
    arquivo: str | None = None,
    mime: str | None = None,
    bytes_: int | None = None,
    sha256: str | None = None,
    tentativas: int = 0,
    erro: str | None = None,
    origem_url: str | None = None,
    baixado_em: datetime | None = None,
) -> None:
    """Grava/atualiza a procedência de uma figura de marca da RPI.

    Uma linha por ``(numero_rpi, numero_processo)``. A tabela é separada de
    ``marcas_logos`` de propósito: o XML pode referenciar processos que ainda
    não estão no dump de marcas (ou o mesmo processo pode aparecer em edições
    diferentes), e queremos auditoria/resume mesmo sem ``codigo_interno``.

    Usa ``INSERT ... ON CONFLICT`` (e não UPDATE seguido de INSERT) porque duas
    instâncias do worker podem processar a mesma edição em paralelo: no
    PostgreSQL, um ``UniqueViolation`` aborta a transação e o UPDATE seguinte
    falharia com ``InFailedSqlTransaction``.
    """
    sql = """
        INSERT INTO marcas_rpi_imagens
            (id, numero_rpi, numero_processo, nome_imagem, codigo_interno,
             status, arquivo, mime, bytes, sha256, tentativas, erro,
             origem_url, baixado_em, created_at, updated_at)
        VALUES
            (%(id)s, %(numero_rpi)s, %(numero_processo)s, %(nome_imagem)s,
             %(codigo_interno)s, %(status)s, %(arquivo)s, %(mime)s, %(bytes)s,
             %(sha256)s, %(tentativas)s, %(erro)s, %(origem_url)s,
             %(baixado_em)s, %(now)s, %(now)s)
        ON CONFLICT (numero_rpi, numero_processo) DO UPDATE SET
            nome_imagem    = COALESCE(EXCLUDED.nome_imagem, marcas_rpi_imagens.nome_imagem),
            codigo_interno = COALESCE(EXCLUDED.codigo_interno, marcas_rpi_imagens.codigo_interno),
            status         = EXCLUDED.status,
            arquivo        = COALESCE(EXCLUDED.arquivo, marcas_rpi_imagens.arquivo),
            mime           = COALESCE(EXCLUDED.mime, marcas_rpi_imagens.mime),
            bytes          = COALESCE(EXCLUDED.bytes, marcas_rpi_imagens.bytes),
            sha256         = COALESCE(EXCLUDED.sha256, marcas_rpi_imagens.sha256),
            tentativas     = EXCLUDED.tentativas,
            erro           = EXCLUDED.erro,
            origem_url     = COALESCE(EXCLUDED.origem_url, marcas_rpi_imagens.origem_url),
            baixado_em     = COALESCE(EXCLUDED.baixado_em, marcas_rpi_imagens.baixado_em),
            updated_at     = EXCLUDED.updated_at
    """
    values = {
        "id": str(uuid.uuid4()),
        "numero_rpi": numero_rpi,
        "numero_processo": numero_processo,
        "nome_imagem": nome_imagem,
        "codigo_interno": codigo_interno,
        "status": status,
        "arquivo": arquivo,
        "mime": mime,
        "bytes": bytes_,
        "sha256": sha256,
        "tentativas": tentativas,
        "erro": erro,
        "origem_url": origem_url,
        "baixado_em": baixado_em,
        "now": _now(),
    }
    with cursor() as cur:
        cur.execute(sql, values)


def get_rpi_imagem(numero_rpi: str, numero_processo: str) -> dict[str, Any] | None:
    """Procedência de uma figura de uma edição/processo (ou ``None``).

    Usada como cache do pipeline: uma linha ``OK`` cujo arquivo ainda existe em
    disco evita um novo download (inclusive para processos que ainda não têm
    ``codigo_interno``, quando ``marcas_logos`` não pode servir de cache).
    """
    with cursor() as cur:
        cur.execute(
            """
            SELECT numero_rpi, numero_processo, nome_imagem, codigo_interno,
                   status, arquivo, mime, bytes, sha256, tentativas, erro,
                   origem_url, baixado_em
            FROM marcas_rpi_imagens
            WHERE numero_rpi = %s AND numero_processo = %s
            """,
            (numero_rpi, numero_processo),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "numero_rpi": row[0],
        "numero_processo": row[1],
        "nome_imagem": row[2],
        "codigo_interno": row[3],
        "status": row[4],
        "arquivo": row[5],
        "mime": row[6],
        "bytes": row[7],
        "sha256": row[8],
        "tentativas": row[9],
        "erro": row[10],
        "origem_url": row[11],
        "baixado_em": row[12],
    }


def rpi_imagens_pendentes(
    *,
    numero_rpi: str | None = None,
    limit: int | None = None,
    incluir_erro: bool = True,
) -> list[dict[str, Any]]:
    """Figuras da RPI que ainda precisam ser baixadas (resume do worker).

    ``OK``/``SEM_IMAGEM`` são terminais. Com ``incluir_erro=True`` (padrão),
    linhas ``ERROR`` também voltam para uma nova tentativa.
    """
    statuses = ["PENDING", "ERROR"] if incluir_erro else ["PENDING"]
    where = ["status = ANY(%(statuses)s)"]
    params: dict[str, Any] = {"statuses": statuses}
    if numero_rpi:
        where.append("numero_rpi = %(numero_rpi)s")
        params["numero_rpi"] = numero_rpi
    sql = (
        "SELECT numero_rpi, numero_processo, nome_imagem, codigo_interno, "
        "status, tentativas FROM marcas_rpi_imagens "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY numero_rpi, numero_processo"
    )
    if limit:
        sql += " LIMIT %(limit)s"
        params["limit"] = limit
    with cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [
        {
            "numero_rpi": row[0],
            "numero_processo": row[1],
            "nome_imagem": row[2],
            "codigo_interno": row[3],
            "status": row[4],
            "tentativas": row[5],
        }
        for row in rows
    ]


# --- Figuras de Desenho Industrial publicadas na RPI -------------------------
def upsert_desenho_rpi_figura(
    *,
    numero_rpi: str,
    numero_processo: str,
    nome_imagem: str | None = None,
    codigo_interno: str | None = None,
    status: str = "PENDING",
    arquivo: str | None = None,
    mime: str | None = None,
    bytes_: int | None = None,
    sha256: str | None = None,
    tentativas: int = 0,
    erro: str | None = None,
    origem_url: str | None = None,
    baixado_em: datetime | None = None,
) -> None:
    """Grava/atualiza a procedência de uma figura de DI referenciada na RPI.

    Espelha ``marcas_rpi_imagens``: uma linha por ``(numero_rpi, processo)``
    preserva a auditoria mesmo quando o processo ainda não está no dump. O
    binário fica em ``raw/desenhos/figuras`` e o metadado em
    ``desenhos_figuras`` quando há ``codigo_interno``.
    """
    sql = """
        INSERT INTO desenhos_rpi_figuras
            (id, numero_rpi, numero_processo, nome_imagem, codigo_interno,
             status, arquivo, mime, bytes, sha256, tentativas, erro,
             origem_url, baixado_em, created_at, updated_at)
        VALUES
            (%(id)s, %(numero_rpi)s, %(numero_processo)s, %(nome_imagem)s,
             %(codigo_interno)s, %(status)s, %(arquivo)s, %(mime)s, %(bytes)s,
             %(sha256)s, %(tentativas)s, %(erro)s, %(origem_url)s,
             %(baixado_em)s, %(now)s, %(now)s)
        ON CONFLICT (numero_rpi, numero_processo) DO UPDATE SET
            nome_imagem = COALESCE(
                EXCLUDED.nome_imagem, desenhos_rpi_figuras.nome_imagem
            ),
            codigo_interno = COALESCE(
                EXCLUDED.codigo_interno, desenhos_rpi_figuras.codigo_interno
            ),
            status = EXCLUDED.status,
            arquivo = COALESCE(EXCLUDED.arquivo, desenhos_rpi_figuras.arquivo),
            mime = COALESCE(EXCLUDED.mime, desenhos_rpi_figuras.mime),
            bytes = COALESCE(EXCLUDED.bytes, desenhos_rpi_figuras.bytes),
            sha256 = COALESCE(EXCLUDED.sha256, desenhos_rpi_figuras.sha256),
            tentativas = EXCLUDED.tentativas,
            erro = EXCLUDED.erro,
            origem_url = COALESCE(
                EXCLUDED.origem_url, desenhos_rpi_figuras.origem_url
            ),
            baixado_em = COALESCE(
                EXCLUDED.baixado_em, desenhos_rpi_figuras.baixado_em
            ),
            updated_at = EXCLUDED.updated_at
    """
    with cursor() as cur:
        cur.execute(
            sql,
            {
                "id": str(uuid.uuid4()),
                "numero_rpi": numero_rpi,
                "numero_processo": numero_processo,
                "nome_imagem": nome_imagem,
                "codigo_interno": codigo_interno,
                "status": status,
                "arquivo": arquivo,
                "mime": mime,
                "bytes": bytes_,
                "sha256": sha256,
                "tentativas": tentativas,
                "erro": erro,
                "origem_url": origem_url,
                "baixado_em": baixado_em,
                "now": _now(),
            },
        )


def get_desenho_rpi_figura(
    numero_rpi: str, numero_processo: str
) -> dict[str, Any] | None:
    """Procedência de uma figura de DI de uma edição/processo (ou ``None``)."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT numero_rpi, numero_processo, nome_imagem, codigo_interno,
                   status, arquivo, mime, bytes, sha256, tentativas, erro,
                   origem_url, baixado_em
            FROM desenhos_rpi_figuras
            WHERE numero_rpi = %s AND numero_processo = %s
            """,
            (numero_rpi, numero_processo),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "numero_rpi": row[0],
        "numero_processo": row[1],
        "nome_imagem": row[2],
        "codigo_interno": row[3],
        "status": row[4],
        "arquivo": row[5],
        "mime": row[6],
        "bytes": row[7],
        "sha256": row[8],
        "tentativas": row[9],
        "erro": row[10],
        "origem_url": row[11],
        "baixado_em": row[12],
    }


def desenho_rpi_figuras_pendentes(
    *,
    numero_rpi: str | None = None,
    limit: int | None = None,
    incluir_erro: bool = True,
) -> list[dict[str, Any]]:
    """Figuras de DI que ainda precisam ser baixadas (resume do worker)."""
    statuses = ["PENDING", "ERROR"] if incluir_erro else ["PENDING"]
    where = ["status = ANY(%(statuses)s)"]
    params: dict[str, Any] = {"statuses": statuses}
    if numero_rpi:
        where.append("numero_rpi = %(numero_rpi)s")
        params["numero_rpi"] = numero_rpi
    sql = (
        "SELECT numero_rpi, numero_processo, nome_imagem, codigo_interno, "
        "status, tentativas FROM desenhos_rpi_figuras "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY numero_rpi, numero_processo"
    )
    if limit:
        sql += " LIMIT %(limit)s"
        params["limit"] = limit
    with cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [
        {
            "numero_rpi": row[0],
            "numero_processo": row[1],
            "nome_imagem": row[2],
            "codigo_interno": row[3],
            "status": row[4],
            "tentativas": row[5],
        }
        for row in rows
    ]


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


# --- Desenhos industriais: figuras (imagens) ---------------------------------
def figura_codes(*, only_pending: bool = True, limit: int | None = None) -> list[str]:
    """``codigo_interno`` de desenhos industriais que ainda precisam de figura.

    Com ``only_pending=True`` pula os que já têm uma linha terminal
    (``OK``/``SEM_IMAGEM``) em ``desenhos_figuras``, de modo que o worker de
    figuras seja resumível. ``ORDER BY`` determinístico garante progresso sob
    ``--limite`` (mesma lógica de ``logo_codes``).
    """
    where = ["d.codigo_interno IS NOT NULL"]
    params: dict[str, Any] = {}
    if only_pending:
        where.append(
            """
            NOT EXISTS (
                SELECT 1 FROM desenhos_figuras f
                WHERE f.codigo_interno = d.codigo_interno
                  AND f.status IN ('OK', 'SEM_IMAGEM')
            )
            """
        )
    sql = f"SELECT d.codigo_interno FROM desenhos d WHERE {' AND '.join(where)}"
    sql += " ORDER BY d.codigo_interno"
    if limit:
        sql += " LIMIT %(limit)s"
        params["limit"] = limit
    with cursor() as cur:
        cur.execute(sql, params)
        return [r[0] for r in cur.fetchall()]


def upsert_figura(
    *,
    codigo_interno: str,
    status: str,
    ordem: int = 1,
    arquivo: str | None = None,
    mime: str | None = None,
    bytes_: int | None = None,
    sha256: str | None = None,
    tentativas: int = 0,
    erro: str | None = None,
    baixado_em: datetime | None = None,
) -> None:
    """Insere/atualiza o *metadado* de uma figura de desenho industrial.

    Só grava a linha de controle — o binário vai para o object storage
    (``arquivo`` guarda a chave/caminho), nunca o disco local da instância Free
    Tier. Keyed por ``codigo_interno`` (uma figura principal por processo).
    """
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO desenhos_figuras
                (id, codigo_interno, ordem, arquivo, mime, bytes, sha256, status,
                 tentativas, erro, baixado_em, created_at, updated_at)
            VALUES
                (%(id)s, %(codigo_interno)s, %(ordem)s, %(arquivo)s, %(mime)s,
                 %(bytes)s, %(sha256)s, %(status)s, %(tentativas)s, %(erro)s,
                 %(baixado_em)s, %(now)s, %(now)s)
            ON CONFLICT (codigo_interno) DO UPDATE SET
                ordem = EXCLUDED.ordem,
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
                "ordem": ordem,
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


def get_figura(codigo_interno: str) -> dict[str, Any] | None:
    """Metadado da figura de um desenho já processado (cache do pipeline)."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT codigo_interno, ordem, arquivo, mime, bytes, sha256, status,
                   tentativas, erro, baixado_em
            FROM desenhos_figuras WHERE codigo_interno = %s
            """,
            (codigo_interno,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "codigo_interno": row[0],
        "ordem": row[1],
        "arquivo": row[2],
        "mime": row[3],
        "bytes": row[4],
        "sha256": row[5],
        "status": row[6],
        "tentativas": row[7],
        "erro": row[8],
        "baixado_em": row[9],
    }
