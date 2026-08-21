# Smart City Trash Bin Monitor - BinForge 🏙️

Data Simulator is the data generation service for the Smart City Trash Bin
Monitor. It runs one asynchronous simulation per active bin and publishes fill,
battery, temperature, location, zone, and timestamp telemetry to Apache Kafka.

## Architecture

- **Simulator**: Python 3.12 (AsyncIO)
- **Database**: PostgreSQL 15
- **Message Broker**: Apache Kafka (KRaft mode)

## Quick Start (Docker)

### 1. Environment Configuration

The repository includes a template file. Copy it to the `.env.docker` path used
by Docker Compose:

```bash
test -f services/data-simulator/.env.docker || \
  cp services/data-simulator/.env.local.example services/data-simulator/.env.docker
```

_(Note: If you plan to run the Python script natively instead of via Docker, create a `.env.local` file instead)._

### 2. Start Infrastructure

Start PostgreSQL and Kafka, then build the simulator image:

```bash
docker compose up -d postgres kafka
docker compose build data_simulator
```

_(The simulator will not emit telemetry until the database is migrated and seeded.)_

### 3. Database Migration & Seeding

Apply all versioned migrations and seed mock data using one-off containers:

```bash
docker compose run --rm data_simulator alembic upgrade head
docker compose run --rm data_simulator python src/seed.py --count 50
```

_(To reset the database later, append `--clear` to the seed command)._

Databases migrated by the earlier `binforge` service can upgrade directly; its
original `9b7a1e20a036` revision remains the baseline of this migration chain.

If the database has the existing table but no `alembic_version` entry, mark its
schema as that baseline before upgrading. This preserves its rows while adding
the new columns:

```bash
docker compose run --rm data_simulator alembic stamp 9b7a1e20a036
docker compose run --rm data_simulator alembic upgrade head
```

To roll back only the zone migration on a disposable database:

```bash
docker compose run --rm data_simulator alembic downgrade 9b7a1e20a036
```

### 4. Recreate Simulator

Recreate the simulator to pick up the rebuilt image and seeded data:

```bash
docker compose up -d --force-recreate data_simulator
```

---

## Verification & Debugging

**View Simulator Logs:**

```bash
docker logs data_simulator -f
```

**Verify Postgres Data:**

```bash
docker exec -it smartbin_postgres psql -U postgres -d smart_city -c "SELECT bin_id, capacity, latitude, longitude, zone, status FROM smart_bins LIMIT 10;"
```

**Consume two newly produced Kafka messages:**

```bash
docker exec smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic smartbin-telemetry-v1 \
  --max-messages 2 --timeout-ms 20000
```

Do not add `--from-beginning` when validating the current payload schema; it
also replays historical records created before newer fields existed.

## Testing

The data simulator has pytest coverage for its models, simulation behavior,
configuration, migration chain, database mapping, lifecycle, and Kafka client.

Run tests locally:

```bash
cd services/data-simulator
pytest -v
```

Or reproduce the Docker test stage:

```bash
docker build --target test \
  -t smart-city-data-simulator-test services/data-simulator
```

## CI/CD Pipeline

GitHub Actions detects supported branch prefixes, enforces file scope for
`feature/` branches, and runs the data-simulator pytest suite on pull requests
to `develop`.

**Feature Policy:**
When creating a feature branch, you must name it `feature/<service>/<task>` (e.g. `feature/data-simulator/add-tests`).
The pipeline enforces that a feature branch only modifies files within its own service directory (e.g., `services/data-simulator/`).

**Local governance check with `act`:**

This command runs the PR governance workflow only:

```bash
act pull_request -e event.json -W .github/workflows/pr-controller.yml
```

Run pytest and Ruff separately when needed; the current GitHub workflows do not
run Ruff.

## Operations

- **Stop Stack**: `docker compose down`
- **Hard Reset (Wipe all data)**: `docker compose down -v`
