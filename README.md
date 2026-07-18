# Smart City Trash Bin Monitor - BinForge 🏙️

BinForge is the data generation service for the Smart City Trash Bin Monitor. It simulates thousands of IoT trash bins concurrently and publishes real-time telemetry (fill levels, locations, timestamps) to Apache Kafka.

## Architecture
- **Simulator**: Python 3.12 (AsyncIO)
- **Database**: PostgreSQL 15
- **Message Broker**: Apache Kafka (KRaft mode)

## Quick Start (Docker)

### 1. Environment Configuration
The repository includes a template file. You must copy it to create your private `.env.docker.local` file inside the `binforge` directory:

```bash
cp binforge/.env.local.example binforge/.env.docker.local
```
*(Note: If you plan to run the Python script natively instead of via Docker, create a `.env.local` file instead).*

### 2. Start Infrastructure
Build and start the unified Docker stack:
```bash
docker compose up -d --build
```
*(The simulator will not emit telemetry until the database is migrated and seeded.)*

### 3. Database Migration & Seeding
Initialize the schema and seed mock data using a one-off container:
```bash
docker compose run --rm binforge_simulator alembic upgrade head
docker compose run --rm binforge_simulator python scripts/seed.py --count 50
```
*(To reset the database later, append `--clear` to the seed command).*

### 4. Restart Simulator
Restart the simulator to pick up the seeded data:
```bash
docker compose restart binforge_simulator
```

---

## Verification & Debugging

**View Simulator Logs:**
```bash
docker logs binforge_simulator -f
```

**Verify Postgres Data:**
```bash
docker exec -it smartbin_postgres psql -U postgres -d smart_city -c "SELECT bin_id, capacity, latitude, longitude, status FROM smart_bins LIMIT 10;"
```

**Consume Live Kafka Stream:**
```bash
docker exec -it smartbin_kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic smartbin-telemetry-v1
```

## Operations
- **Stop Stack**: `docker compose down`
- **Hard Reset (Wipe all data)**: `docker compose down -v`
