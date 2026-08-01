# Smart City Trash Bin Monitor - BinForge 🏙️

Data Simulator is the data generation service for the Smart City Trash Bin Monitor. It simulates thousands of IoT trash bins concurrently and publishes real-time telemetry (fill levels, locations, timestamps) to Apache Kafka.

## Architecture

- **Simulator**: Python 3.12 (AsyncIO)
- **Database**: PostgreSQL 15
- **Message Broker**: Apache Kafka (KRaft mode)

## Quick Start (Docker)

### 1. Environment Configuration

The repository includes a template file. You must copy it to create your private `.env.docker.local` file inside the `services/data-simulator` directory:

```bash
cp services/data-simulator/.env.local.example services/data-simulator/.env.docker.local
```

_(Note: If you plan to run the Python script natively instead of via Docker, create a `.env.local` file instead)._

### 2. Start Infrastructure

Build and start the unified Docker stack:

```bash
docker compose up -d --build
```

_(The simulator will not emit telemetry until the database is migrated and seeded.)_

### 3. Database Migration & Seeding

Initialize the schema and seed mock data using a one-off container:

```bash
docker compose run --rm data_simulator python src/seed.py --count 50
```

_(To reset the database later, append `--clear` to the seed command)._

### 4. Restart Simulator

Restart the simulator to pick up the seeded data:

```bash
docker compose restart data_simulator
```

---

## Verification & Debugging

**View Simulator Logs:**

```bash
docker logs data_simulator -f
```

**Verify Postgres Data:**

```bash
docker exec -it smartbin_postgres psql -U postgres -d smart_city -c "SELECT bin_id, capacity, latitude, longitude, status FROM smart_bins LIMIT 10;"
```

**Consume Live Kafka Stream:**

```bash
docker exec -it smartbin_kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic smartbin-telemetry-v1
```

## Testing

The data simulator comes with a comprehensive `pytest` suite that tests all the core simulation logic, database schema, and Kafka integrations.

To run the tests locally inside the running Docker container:

```bash
docker exec -it data_simulator pip install -r requirements-dev.txt
docker exec -it data_simulator pytest -v
```

_(This allows you to test instantly without having to rebuild the Docker image.)_

## CI/CD Pipeline

We enforce a strict CI/CD pipeline using GitHub Actions to ensure code quality and prevent regressions.

**Feature Policy:**
When creating a feature branch, you must name it `feature/<service>/<task>` (e.g. `feature/data-simulator/add-tests`).
The pipeline enforces that a feature branch only modifies files within its own service directory (e.g., `services/data-simulator/`).

**Local Testing with `act`:**
You can test the GitHub Actions CI pipeline locally before pushing your code using `act`:

```bash
act pull_request -e event.json -W .github/workflows/pr-controller.yml
```

This spins up a local GitHub runner, validates the feature policy, runs the Ruff linter, and executes the Pytest suite inside the CI Docker environment.

## Operations

- **Stop Stack**: `docker compose down`
- **Hard Reset (Wipe all data)**: `docker compose down -v`
