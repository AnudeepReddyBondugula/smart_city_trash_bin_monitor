import asyncio
import os

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
