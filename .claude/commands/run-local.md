---
description: Run the simulator locally against Dockerized Postgres + Kafka.
---

# /run-local

Starts the "hybrid local" dev setup: Postgres and Kafka run in Docker, but the
Python simulator runs natively on your machine (fast iteration, IDE debugging).

## Prerequisites

- Docker + Docker Compose.
- Python 3.12 with runtime deps installed:
  ```bash
  cd services/data-simulator
  pip install -r requirements.txt
  ```
- An env file `services/data-simulator/.env.local` (copy the template):
  ```bash
  cp services/data-simulator/.env.local.example services/data-simulator/.env.local
  ```
  (It points Postgres/Kafka at `localhost` — `.env.local.example:2-10`.)

## The script

`services/data-simulator/scripts/run_local.sh` (Linux/macOS) or
`scripts/run_local.ps1` (Windows). It:
1. `docker compose ... up -d postgres kafka` — infra only
   (`run_local.sh:20`).
2. Waits for Postgres readiness (`run_local.sh:24-28`).
3. Sources `.env.local` and runs `PYTHONPATH=. python src/main.py`
   (`run_local.sh:36-40`).

```bash
cd services/data-simulator
./scripts/run_local.sh
```

## First run: create schema + seed

The simulator emits nothing until the DB has `ACTIVE` bins
(`simulation_manager.py:44`). In another shell:
```bash
cd services/data-simulator
set -a; source .env.local; set +a
PYTHONPATH=. python src/create_tables.py
PYTHONPATH=. python src/seed.py --count 50
```
(See the `seed-db` command and the `table-creation` / `database-seeding`
breadcrumbs.)

## Full Docker alternative (no native Python)

Per `README.md:23-49`:
```bash
docker compose up -d --build
docker compose run --rm data_simulator python src/seed.py --count 50
docker compose restart data_simulator
```

## Verify / debug

- Logs: `docker logs data_simulator -f` (full-Docker), or the console + rotating
  `logs/simulator.log` (native, `logging_config.py:41-49`).
- Live Kafka stream (`README.md:70`):
  ```bash
  docker exec -it smartbin_kafka kafka-console-consumer \
    --bootstrap-server localhost:9092 --topic smartbin-telemetry-v1
  ```
- Toggle DEBUG logging on a running native process: `kill -USR1 <pid>`
  (`logging_config.py:55`).
