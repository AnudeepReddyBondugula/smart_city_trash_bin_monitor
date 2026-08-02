# Smart City Trash Bin Monitor — BinForge 🏙️

**Data Simulator** is the data-generation service for the Smart City Trash Bin
Monitor. It simulates a fleet of IoT trash bins concurrently (one asyncio task
per bin) and publishes real-time telemetry — fill level, battery level,
location, timestamp — to Apache Kafka. Static bin metadata lives in PostgreSQL;
the dynamic telemetry state is generated in memory and streamed out.

## Stack

- **Simulator**: Python 3.12 (AsyncIO)
- **Database**: PostgreSQL 15 (bin metadata only)
- **Message Broker**: Apache Kafka (KRaft mode, no ZooKeeper)

📚 **Full documentation:** [`docs/features/data-simulator/`](docs/features/data-simulator/)
— start with [architecture.md](docs/features/data-simulator/architecture.md).

---

## Quick Start (Docker)

Run all commands from the repository root.

### 1. Environment configuration

Docker Compose reads `services/data-simulator/.env.docker`. That file is
git-ignored, so create it from the template on a fresh clone:

```bash
cp services/data-simulator/.env.local.example services/data-simulator/.env.docker
```

Set the Docker-network values inside it: `POSTGRES_HOST=postgres` and
`KAFKA_BOOTSTRAP_SERVERS=kafka:29092`.

> ⚠️ Compose reads **`.env.docker`** — not `.env.docker.local`. See
> [configuration.md](docs/features/data-simulator/configuration.md) for details.
> _(If you instead run the simulator natively, create `.env.local` with
> `localhost` values — see [deployment.md](docs/features/data-simulator/deployment.md).)_

### 2. Start the stack

```bash
docker compose up -d --build
```

_(The simulator emits no telemetry until the schema exists and ACTIVE bins are
seeded.)_

### 3. Create the schema and seed data

The schema is created from ORM metadata (there are no Alembic migrations), then
seeded with mock bins — both via one-off containers:

```bash
docker compose run --rm data_simulator python src/create_tables.py
docker compose run --rm data_simulator python src/seed.py --count 50
```

_(To reset later, add `--clear` to the seed command; max 500 bins per run.)_

### 4. Restart the simulator

Bins are loaded once at startup, so restart to pick up the seeded data:

```bash
docker compose restart data_simulator
```

---

## Verification & Debugging

**Simulator logs:**

```bash
docker logs data_simulator -f
```

**Postgres data:**

```bash
docker exec -it smartbin_postgres psql -U postgres -d smart_city \
  -c "SELECT bin_id, capacity, latitude, longitude, status FROM smart_bins LIMIT 10;"
```

**Live Kafka stream:**

```bash
docker exec -it smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 --topic smartbin-telemetry-v1
```

More: [operations.md](docs/features/data-simulator/operations.md) ·
[troubleshooting.md](docs/features/data-simulator/troubleshooting.md).

---

## Testing

A `pytest` suite covers the simulation logic, database model, and Kafka client
(all mocked — no live infra needed). Run it inside the running container without
rebuilding:

```bash
docker exec -it data_simulator pip install -r requirements-dev.txt
docker exec -it data_simulator pytest -v
```

Or locally from `services/data-simulator/`: `PYTHONPATH=src pytest -v`. See
[testing.md](docs/features/data-simulator/testing.md).

---

## CI/CD

GitHub Actions runs on pull requests to **`develop`**
(see [ci-cd.md](docs/features/data-simulator/ci-cd.md)):

- **Feature policy** — branches must be named `feature/<service>/<task>` and may
  modify only their own service (or, for a `docs` task, only
  `docs/features/<service>/**`).
- **PR Pytest** — installs deps and runs `pytest -v` on Python 3.12.

_CI runs tests and policy checks only — it does not lint, build, or deploy._
Ruff/mypy/pre-commit are configured for **local** use, not enforced in CI.

**Run the pipeline locally with [`act`](https://github.com/nektos/act):**

```bash
act pull_request -e event.json -W .github/workflows/pr-controller.yml
```

---

## Operations

- **Stop stack**: `docker compose down`
- **Hard reset (wipe all data)**: `docker compose down -v`

Runbook: [operations.md](docs/features/data-simulator/operations.md).
