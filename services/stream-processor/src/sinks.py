"""Writing query output to PostgreSQL.

Spark's built-in JDBC writer can only append or overwrite, and both are wrong
here. A micro-batch is re-run after a failed write, so an append double-counts
every retry, and an overwrite would discard history. What is needed is an upsert,
which means going through the driver directly.

Doing that with psycopg2 also removes the need for a JDBC driver jar in the
image, so the only jars are the Kafka connector's.
"""

import logging
from contextlib import closing
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"


def connect():
    """Open a connection to the analytical database.

    `with connection` commits or rolls back but does not close, so callers wrap
    this in `closing` to avoid leaking a connection per micro-batch.
    """
    return closing(psycopg2.connect(settings.DATABASE_URL))


def apply_schema() -> None:
    """
    Create the output tables and views if they are not already there.

    Run once at startup. The schema file is written to be safe to re-run, so
    this never destroys accumulated history.
    """
    logger.info("Applying analytical schema from %s", SCHEMA_PATH)

    with connect() as connection:
        with connection, connection.cursor() as cursor:
            cursor.execute(SCHEMA_PATH.read_text())

    logger.info("Analytical schema applied")


def upsert(rows: list[tuple], table: str, columns: list[str], key: list[str]) -> None:
    """
    Insert rows, updating any that collide with an existing key.

    Args:
        rows:
            Values to write, in the order given by ``columns``.

        table:
            Target table.

        columns:
            Column names being written.

        key:
            The conflicting columns, which must be a unique constraint on the
            table.
    """
    if not rows:
        return

    updates = ", ".join(
        f"{column} = EXCLUDED.{column}" for column in columns if column not in key
    )

    statement = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {updates}"
    )

    with connect() as connection:
        with connection, connection.cursor() as cursor:
            execute_values(cursor, statement, rows, page_size=1000)

    logger.debug("Upserted %d row(s) into %s", len(rows), table)


def insert_ignoring_duplicates(
    rows: list[tuple], table: str, columns: list[str], key: list[str]
) -> None:
    """
    Insert rows, silently skipping any that already exist.

    Used for facts that are true once and never revised - an alert that fired at
    a particular instant does not later fire differently. Re-processing a batch
    produces the identical rows, which are discarded rather than duplicated.
    """
    if not rows:
        return

    statement = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT ({', '.join(key)}) DO NOTHING"
    )

    with connect() as connection:
        with connection, connection.cursor() as cursor:
            execute_values(cursor, statement, rows, page_size=1000)

    logger.debug("Inserted up to %d row(s) into %s", len(rows), table)


def write_batch(dataframe, table: str, columns: list[str], key: list[str], mode: str):
    """
    Write one micro-batch to PostgreSQL.

    Args:
        dataframe:
            The batch, whose columns must include every name in ``columns``.

        table:
            Target table.

        columns:
            Columns to write.

        key:
            Conflict key.

        mode:
            ``"upsert"`` to update existing rows, ``"ignore"`` to keep the
            first version of each.
    """
    # Collected to the driver on purpose. A batch is at most one row per bin,
    # which is thousands of rows, not millions - small enough that a single
    # batched statement from the driver beats opening a connection per executor
    # partition. Revisit if the fleet grows by orders of magnitude.
    rows = [
        tuple(row[column] for column in columns)
        for row in dataframe.select(*columns).collect()
    ]

    if mode == "upsert":
        upsert(rows, table, columns, key)
    else:
        insert_ignoring_duplicates(rows, table, columns, key)
