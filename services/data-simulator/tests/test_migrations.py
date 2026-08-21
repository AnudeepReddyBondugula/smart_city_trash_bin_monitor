from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migrations_have_one_linear_head():
    """Alembic revisions form the expected baseline-to-zone chain."""
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))

    assert scripts.get_heads() == ["0002_add_zone"]
    assert [revision.revision for revision in scripts.walk_revisions()] == [
        "0002_add_zone",
        "0001_initial_schema",
    ]
