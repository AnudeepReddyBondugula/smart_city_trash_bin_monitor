import asyncio
import configparser
import os
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from src.config import get_settings


def test_migrations_have_one_linear_head():
    """Alembic revisions form the expected baseline-to-zone chain."""
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))

    assert scripts.get_heads() == ["0002_add_zone"]
    assert [revision.revision for revision in scripts.walk_revisions()] == [
        "0002_add_zone",
        "9b7a1e20a036",
    ]


def test_migrations_are_not_silent():
    """Alembic is configured to report the revisions it applies.

    Without these sections an upgrade runs in total silence: no "Running
    upgrade" line and no confirmation of which revision was applied. A migration
    that silently did nothing then looks identical to one that worked, on the
    one command whose whole job is changing the shape of the database.
    """
    parser = configparser.ConfigParser()
    parser.read("alembic.ini")

    for section in ("loggers", "handlers", "formatters", "logger_alembic"):
        assert parser.has_section(section), f"alembic.ini lost [{section}]"

    assert parser.get("logger_alembic", "level") == "INFO"


def test_env_loads_the_logging_configuration():
    """The ini sections are useless unless env.py actually applies them.

    Configuring logging is opt-in: Alembic does not read those sections by
    itself, so this is the other half of the same fix.
    """
    env = Path("alembic/env.py").read_text()

    assert "fileConfig" in env
    # Tearing down existing loggers would silence pytest's own logging partway
    # through a run, since this file is executed by the integration test below.
    assert "disable_existing_loggers=False" in env


@pytest.mark.skipif(
    os.getenv("RUN_MIGRATION_INTEGRATION") != "1",
    reason="requires disposable PostgreSQL",
)
def test_zone_migration_backfills_existing_rows():
    """The real PostgreSQL migration preserves and constrains an existing row."""
    settings = get_settings()
    port = int(os.getenv("MIGRATION_TEST_POSTGRES_PORT", settings.POSTGRES_PORT))
    config = Config("alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        (
            f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{port}/{settings.POSTGRES_DB}"
        ).replace("%", "%%"),
    )

    async def execute(query, *args):
        connection = await asyncpg.connect(
            host=settings.POSTGRES_HOST,
            port=port,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
        )
        try:
            return await connection.fetchrow(query, *args)
        finally:
            await connection.close()

    command.upgrade(config, "9b7a1e20a036")
    asyncio.run(
        execute(
            """
            INSERT INTO smart_bins
                (bin_id, capacity, latitude, longitude, status)
            VALUES ($1, 100, 17.4, 78.5, 'ACTIVE')
            """,
            "BIN-PRE-ZONE-X",
        )
    )

    command.upgrade(config, "head")

    row = asyncio.run(
        execute(
            """
            SELECT zone,
                   (SELECT is_nullable
                      FROM information_schema.columns
                     WHERE table_name = 'smart_bins' AND column_name = 'zone')
                       AS is_nullable
              FROM smart_bins
             WHERE bin_id = $1
            """,
            "BIN-PRE-ZONE-X",
        )
    )
    assert dict(row) == {"zone": "UNASSIGNED", "is_nullable": "NO"}
