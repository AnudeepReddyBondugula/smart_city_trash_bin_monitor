# Schema Migrations — Detailed Trace

Paths are relative to `services/data-simulator/`.

1. `alembic.ini` selects the `alembic/` script directory.
2. `alembic/env.py` adds `src/` to the import path, loads
   `settings.DATABASE_URL`, and exposes `Base.metadata` for drift detection.
3. `alembic/versions/9b7a1e20a036_initial.py` is the baseline. Its upgrade
   creates the pre-zone `smart_bins` table; its downgrade drops the table.
4. `alembic/versions/0002_add_zone.py` adds nullable `zone`, backfills existing
   rows with `UNASSIGNED`, then makes the column non-null. Its downgrade drops
   only `zone`.
5. `src/database.py` is the current ORM schema and includes non-null
   `zone: String(20)`.

Fresh database or an existing database already marked `9b7a1e20a036`:

```bash
alembic upgrade head
```

Existing matching table with no Alembic marker:

```bash
alembic stamp 9b7a1e20a036
alembic upgrade head
```

Only stamp after verifying the table matches the baseline; stamping records a
version without executing its schema operations.
