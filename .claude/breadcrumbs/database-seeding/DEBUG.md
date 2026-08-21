# Database Seeding — Debug Guide

Seed errors print to the invoking terminal rather than `logging_config`.

| Symptom | Check |
|---|---|
| `relation "smart_bins" does not exist` | Run `alembic upgrade head`; see `schema-migrations/DEBUG.md`. |
| Missing `zone` column | Rebuild the Docker image and run migrations to head. |
| More than 500 requested | The safety guard returns before connecting. |
| New bins do not appear in telemetry | Recreate/restart the simulator after seeding; it loads rows only at startup. |
| Old bins have `UNASSIGNED` | Expected for rows backfilled by migration `0002_add_zone`; reseed if geographic zones are required. |

Native:

```bash
cd services/data-simulator
set -a; source .env.local; set +a
alembic upgrade head
PYTHONPATH=. python src/seed.py --count 50
```

Docker:

```bash
docker compose build data_simulator
docker compose run --rm data_simulator alembic upgrade head
docker compose run --rm data_simulator python src/seed.py --count 50
docker compose up -d --force-recreate data_simulator
```

`--clear` deletes all existing bin rows before inserting replacements.
