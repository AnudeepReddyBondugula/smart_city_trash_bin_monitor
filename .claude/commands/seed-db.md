---
description: Upgrade the schema and seed mock bins into PostgreSQL.
---

# /seed-db

## Docker

```bash
docker compose up -d postgres
docker compose build data_simulator
docker compose run --rm data_simulator alembic upgrade head
docker compose run --rm data_simulator python src/seed.py --count 50
docker compose up -d --force-recreate data_simulator
```

## Native

```bash
cd services/data-simulator
set -a; source .env.local; set +a
alembic upgrade head
PYTHONPATH=. python src/seed.py --count 50
```

`--count` defaults to 50 and rejects values above 500. `--clear` deletes all
existing bin rows before inserting replacements.

New bins have capacity `100.0`, status `ACTIVE`, and one of five Hyderabad
zones with matching coordinates. Rows that existed before the zone migration
remain `UNASSIGNED` until replaced or explicitly updated.

Verify:

```bash
docker exec smartbin_postgres psql -U postgres -d smart_city \
  -c "SELECT bin_id, latitude, longitude, zone, status FROM smart_bins LIMIT 10;"
```
