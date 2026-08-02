# Operations

Runbook for operating the Data Simulator via Docker Compose. All commands are
verified against `docker-compose.yml`, the root `README.md`, and the service
source.

> Scope note: this service has **no HTTP endpoint, no metrics endpoint, and no
> configured alerting**. "Monitoring" today means logs and manual data checks.
> Anything requiring infrastructure that does not exist in the repo is marked
> **TODO: confirm with team**.

---

## Start / stop

```bash
# Build + start the whole stack
docker compose up -d --build

# Start infra only (for hybrid local dev), then run the simulator on the host
services/data-simulator/scripts/run_local.sh      # Linux/macOS
services/data-simulator/scripts/run_local.ps1     # Windows

# Stop the stack (keeps data)
docker compose down

# Stop + wipe all data (drops the postgres_data volume)
docker compose down -v
```

First-run prerequisite: the `.env.docker` file must exist — see the warning in
[deployment.md](deployment.md) and [configuration.md](configuration.md).

---

## First-run data setup

The simulator emits nothing until the `smart_bins` table exists and has `ACTIVE`
rows. `seed.py` inserts rows but does **not** create the table
(see [database.md](database.md)).

```bash
# (if the table doesn't exist yet) create schema
docker compose run --rm data_simulator python src/create_tables.py

# seed mock bins (max 500)
docker compose run --rm data_simulator python src/seed.py --count 50

# reset + reseed
docker compose run --rm data_simulator python src/seed.py --count 50 --clear

# apply the new bins (simulator loads bins only at startup)
docker compose restart data_simulator
```

> The root README's quickstart runs `seed.py` directly and relies on the table
> already existing. If seeding fails with an "undefined table" error, run
> `create_tables.py` first.

---

## Monitoring

### Logs

Logging is configured in `src/logging_config.py`:

- **Console:** colorized (`colorlog`), format
  `%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`.
- **File:** `logs/simulator.log`, a `RotatingFileHandler` — **20 MB per file, 5
  backups** (`logging_config.py:41-45`). Inside the container this is
  `/app/logs/simulator.log`; it is **not** a mounted volume, so it lives in the
  container's writable layer and is lost when the container is removed.
- Default level **INFO**; `aiokafka.cluster` is pinned to CRITICAL to reduce
  noise (`logging_config.py:52`).

```bash
# follow container stdout/stderr (console handler)
docker logs data_simulator -f

# tail the rotating file inside the container
docker exec -it data_simulator tail -f logs/simulator.log
```

Healthy startup logs (from `src/main.py`): `Initializing Data Simulator` →
`Kafka Client Started Successfully` → `Simulation Manager Started Successfully`,
followed by `Started N simulator(s).` from the manager.

### Toggle DEBUG at runtime (no restart)

`setup_logging` registers a **SIGUSR1** handler that flips the root level
between INFO and DEBUG (`logging_config.py:55, 60-71`). At DEBUG you get
per-bin `Sending telemetry` / `Simulated bin ... | Fill: .. | Battery: ..`
lines.

```bash
# send SIGUSR1 to PID 1 (the python process) in the container
docker exec data_simulator kill -USR1 1
```

Send it again to go back to INFO. *(Linux/macOS only — SIGUSR1 does not exist on
Windows.)*

### Verify the database

```bash
docker exec -it smartbin_postgres psql -U postgres -d smart_city \
  -c "SELECT bin_id, capacity, latitude, longitude, status FROM smart_bins LIMIT 10;"
```

(Host access: Postgres is published on `localhost:5433`.)

### Verify the Kafka stream

```bash
docker exec -it smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 --topic smartbin-telemetry-v1
```

You should see one JSON telemetry message per bin roughly every
`SIMULATION_INTERVAL` (default 5s). See [kafka.md](kafka.md).

---

## Restart

```bash
docker compose restart data_simulator
```

The container handles **SIGTERM** gracefully: `main.py` cancels all simulators,
stops the Kafka producer (flush), and disposes the DB engine, each under a 5s
timeout (`src/main.py:52-68`). Compose's default stop grace period (10s) is
comfortably above that. Restarting is also the supported way to pick up newly
seeded bins.

---

## Scaling

**Vertical (more bins, same process):** seed more `ACTIVE` bins and restart.
Concurrency is asyncio on a single event loop, so a single container simulates
many bins cheaply (each bin is one lightweight task). Practical ceilings:

- `seed.py` caps a single seed run at **500 bins** (`seed.py:16-18`). Run it
  multiple times, or raise the guard, for more.
- CPU/throughput ceiling is undocumented — no load test exists in the repo.
  *(TODO: confirm with team the tested upper bound on bins per container.)*

**Horizontal (multiple simulator containers):** **not supported as-is.** Every
instance would call `SimulationManager.initialize()` and load the **same** set
of `ACTIVE` bins from the shared DB, producing duplicate telemetry for every
bin. There is no sharding/partitioning of bins across instances. Do not scale
`data_simulator` to replicas > 1 without adding bin-partitioning logic.
*(TODO: confirm with team if horizontal scale is on the roadmap.)*

`NUMBER_OF_BINS` does **not** control scale — it is unused
(see [configuration.md](configuration.md)).

---

## Alerts

**None configured.** There is no metrics endpoint, no Prometheus/Grafana, and no
alerting wired in the repo. Operational awareness is currently manual (logs +
DB/topic checks above). *(TODO: confirm with team whether alerting/metrics are
planned — a candidate first metric is "telemetry send failures", already logged
as `Failed to send telemetry for <bin_id>`.)*

Failure signals to watch for in logs:

| Log line | Meaning |
| --- | --- |
| `Kafka not ready yet (...), retrying... (i/10)` | Producer still connecting; normal at boot, a problem if it repeats past ~30s. |
| `Could not connect to Kafka ... after multiple retries` | Producer gave up after 10 attempts → the process raises and exits. |
| `Kafka producer is not started; dropping telemetry for <bin>` | Telemetry produced before the client started. |
| `Failed to send telemetry for <bin>: ...` | A publish was dropped (best-effort delivery). |
| `Started 0 simulator(s).` | No ACTIVE bins in the DB — seed data. |

More symptom→cause→fix mappings: [troubleshooting.md](troubleshooting.md).

---

## Related documents

- [deployment.md](deployment.md) — stack topology and lifecycle.
- [database.md](database.md) — schema, create, seed, reset.
- [troubleshooting.md](troubleshooting.md) — failure modes.
