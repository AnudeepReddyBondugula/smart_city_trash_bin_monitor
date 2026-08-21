# Schema Migrations — Debug Guide

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

Never stamp an unknown schema or downgrade below `9b7a1e20a036` on valuable
data: the baseline downgrade drops `smart_bins`.
