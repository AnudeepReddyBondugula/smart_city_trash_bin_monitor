# Schema Migrations — Debug Guide

## Reading the output

An upgrade reports every revision it applies:

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 9b7a1e20a036, Create the initial smart_bins schema.
INFO  [alembic.runtime.migration] Running upgrade 9b7a1e20a036 -> 0002_add_zone, Add zone to smart_bins and backfill existing rows.
```

Only the first two lines means the database was already at head — nothing to do,
which is not the same as nothing happening.

**No output at all** means logging is not configured. `alembic.ini` needs its
`[loggers]`/`[handlers]`/`[formatters]` sections *and* `env.py` must call
`fileConfig`; either one alone is silent. A silent upgrade is dangerous
precisely because a migration that did nothing looks identical to one that
worked.

To see the SQL as well, raise `logger_sqlalchemy` to `INFO` in `alembic.ini`.

## Commands

```bash
cd services/data-simulator
alembic history
alembic current
alembic heads
alembic check
```

Docker images copy the service source. Rebuild before running newly added
migrations:

```bash
docker compose build data_simulator
docker compose run --rm data_simulator alembic upgrade head
docker compose run --rm data_simulator alembic history --indicate-current
```

## Symptoms

| Symptom | Cause and next check |
|---|---|
| `Can't locate revision identified by ...` | The database marker is absent from the checked-out revision files, or the container image is stale. Compare `SELECT version_num FROM alembic_version` with `alembic history`, then rebuild the image. |
| `relation "smart_bins" does not exist` | Run `alembic upgrade head` before seeding. |
| `table smart_bins already exists` on baseline upgrade | The table predates Alembic and has no marker. Verify its columns, then stamp `9b7a1e20a036` and upgrade. |
| `alembic check` reports operations | ORM metadata changed without a matching revision. Generate and review a migration. |
| Upgrade prints nothing at all | Logging is unconfigured, or the image is stale. Rebuild first — the ini and `env.py` are copied into the image. |

Never stamp an unknown schema or downgrade below `9b7a1e20a036` on valuable
data: the baseline downgrade drops `smart_bins`.
