---
description: Create the schema and seed mock bins into Postgres.
---

# /seed-db

Initializes the `smart_bins` table and inserts mock bins so the simulator has
`ACTIVE` bins to emit telemetry for.

## Prerequisites

- Postgres running (via `docker compose up -d postgres` or the full stack).
- Env vars available (sourced from `.env.local` for native, or provided by
  `.env.docker` inside containers). See the `config` skill.

## Step 1 — create tables (idempotent)

`src/create_tables.py` runs `Base.metadata.create_all`
(`create_tables.py:5-13`). Only creates missing tables; does not alter existing
ones.

Native:
```bash
cd services/data-simulator
set -a; source .env.local; set +a
PYTHONPATH=. python src/create_tables.py
```

## Step 2 — seed mock bins

`src/seed.py` inserts `--count` bins (default 50, max 500) with `Faker`
coordinates, `capacity=100.0`, `status="ACTIVE"` (`seed.py:31-42`).

Native:
```bash
PYTHONPATH=. python src/seed.py --count 50          # add bins
PYTHONPATH=. python src/seed.py --count 50 --clear  # wipe then re-seed
```

Docker (per `README.md:38`, `:41`):
```bash
docker compose run --rm data_simulator python src/seed.py --count 50
docker compose run --rm data_simulator python src/seed.py --count 50 --clear
```

## Flags (`src/seed.py:51-59`)

- `--count N` — number of bins (default 50; refuses `>500`, `seed.py:16-18`).
- `--clear` — `DELETE FROM smart_bins` before inserting (`seed.py:26-29`).

## Verify

```bash
docker exec -it smartbin_postgres psql -U postgres -d smart_city \
  -c "SELECT bin_id, capacity, latitude, longitude, status FROM smart_bins LIMIT 10;"
```
(from `README.md:64`)

After seeding, restart the simulator so `initialize()` reloads the fleet
(`README.md:48`, `simulation_manager.py:34-46`).
