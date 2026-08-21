---
description: Run the simulator locally against Dockerized Postgres and Kafka.
---

# /run-local

## Hybrid local

```bash
docker compose up -d postgres kafka
cd services/data-simulator
cp .env.local.example .env.local  # first run only
pip install -r requirements-dev.txt
set -a; source .env.local; set +a
alembic upgrade head
PYTHONPATH=. python src/seed.py --count 50
./scripts/run_local.sh
```

The script starts PostgreSQL and Kafka if necessary, waits for PostgreSQL,
loads `.env.local`, and runs `src/main.py` natively.

## Full Docker

```bash
test -f services/data-simulator/.env.docker || \
  cp services/data-simulator/.env.local.example services/data-simulator/.env.docker
docker compose up -d postgres kafka
docker compose build data_simulator
docker compose run --rm data_simulator alembic upgrade head
docker compose run --rm data_simulator python src/seed.py --count 50
docker compose up -d --force-recreate data_simulator
```

`restart` does not adopt a rebuilt image; use `up --force-recreate` after code
or migration changes.

Read newly produced telemetry without replaying the old topic history:

```bash
docker exec smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic smartbin-telemetry-v1 \
  --max-messages 2 --timeout-ms 20000
```
