# Smart City Trash Bin Monitor - BinForge 🏙️

Two services. The **Data Simulator** runs one asynchronous simulation per active
bin and publishes fill, battery, temperature, location, zone and timestamp
telemetry to Apache Kafka. The **Stream Processor** reads that topic with Spark
Structured Streaming and turns it into alerts, per-bin state and zone
aggregates in PostgreSQL, plus a Parquet event history.

## Architecture

- **Simulator**: Python 3.12 (AsyncIO)
- **Stream Processor**: Python 3.11, PySpark 3.5 (see note below)
- **Database**: PostgreSQL 15
- **Message Broker**: Apache Kafka (KRaft mode)

```
data-simulator ──▶ smartbin-telemetry-v1 ──▶ stream-processor ──▶ PostgreSQL
                                                    │                Parquet
                                                    └──▶ smartbin-telemetry-dlq
```

Both services read the same payload contract, `contracts/telemetry-v1.json`.
The producer asserts its payload against it and the consumer builds its Spark
schema from it, so a renamed field fails a test instead of silently reading as
nulls on the consumer side.

> **Python 3.11 for the stream processor.** PySpark 3.5 supports Python up to
> 3.11. On 3.12 its pandas operators fail at run time importing `distutils`,
> which that version removed. The image and CI pin 3.11; the simulator stays on
> 3.12.

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

Start PostgreSQL and Kafka, create the topics, then build the images:

```bash
docker compose up -d postgres kafka kafka_init
docker compose build data_simulator stream_processor
```

`kafka_init` creates `smartbin-telemetry-v1` with 12 partitions and
`smartbin-telemetry-dlq` with 3, and prints what it created. Twelve partitions
is what lets Spark spread the load; auto-creation would give one, pinning the
whole stream to a single task.

> If the topic already exists with the wrong partition count, `kafka_init`
> leaves it alone — adding partitions later would change which partition a
> bin's key hashes to and break the per-bin ordering the stateful query relies
> on. Delete it and let `kafka_init` recreate it:
>
> ```bash
> docker exec smartbin_kafka kafka-topics --bootstrap-server localhost:9092 \
>   --delete --topic smartbin-telemetry-v1
> docker compose up kafka_init
> ```

_(The simulator will not emit telemetry until the database is migrated and seeded.)_

### 3. Database Migration & Seeding

Apply all versioned migrations and seed mock data using one-off containers:

```bash
docker compose run --rm data_simulator alembic upgrade head
docker compose run --rm data_simulator python src/seed.py --count 50
```

The upgrade names every revision it applies:

```text
INFO  [alembic.runtime.migration] Running upgrade  -> 9b7a1e20a036, Create the initial smart_bins schema.
INFO  [alembic.runtime.migration] Running upgrade 9b7a1e20a036 -> 0002_add_zone, Add zone to smart_bins and backfill existing rows.
```

Only the two `Context impl` lines means the database was already at head.

List migration history and mark the database's current revision:

```bash
docker compose run --rm data_simulator alembic history --indicate-current
```

_(To reset the database later, append `--clear` to the seed command)._

Databases whose `alembic_version` is `9b7a1e20a036` can upgrade directly because
that revision is the baseline of the checked-in migration chain.

If the database has an existing table but no `alembic_version` entry, first
inspect it with `\d smart_bins` in `psql`. Only stamp the baseline when its
columns and constraints match revision `9b7a1e20a036`; stamping records a
version without changing or validating the schema:

```bash
docker compose run --rm data_simulator alembic stamp 9b7a1e20a036
docker compose run --rm data_simulator alembic upgrade head
```

To roll back only the zone migration on a disposable database:

```bash
docker compose run --rm data_simulator alembic downgrade 9b7a1e20a036
```

### 4. Start the Services

```bash
docker compose up -d --force-recreate data_simulator stream_processor
```

The stream processor applies `services/stream-processor/sql/schema.sql` on
startup — it is idempotent, so restarting never destroys accumulated history —
and then starts four streaming queries: `bin_events`, `dead_letters`,
`zone_metrics` and `bin_state`.

### The Spark UI

**<http://localhost:4040>** — and its **Structured Streaming** tab is the first
place to look when a query seems stalled. It reports per query: input rate,
processing rate, batch duration, watermark position and state store size. None
of that appears in the logs.

The nightly batch job runs alongside the streaming application and gets its own
port, **<http://localhost:4041>**, for as long as it runs. Both are bound
explicitly (`SPARK_UI_PORT`, `SPARK_BATCH_UI_PORT`) rather than left to Spark's
retry, so the address never moves.

---

## The Processing Layer

One Spark application, four queries, one nightly batch job.

| Query | Writes | Answers |
|---|---|---|
| `bin_events` | Parquet, partitioned by date | The history the nightly job reads |
| `dead_letters` | `smartbin-telemetry-dlq` | Messages that could not be parsed or believed |
| `zone_metrics` | `zone_metrics_5m` | Per-zone rollups, at every grain, by SQL |
| `bin_state` | `bin_alerts`, `bin_state_latest` | Eleven alert types from one per-bin state read |
| `batch/rollups.py` | `zone_hourly_profile`, `zone_daily_trend` | Peak hours and long-range trends |

Dashboard figures are the `city_kpi` and `zone_leaderboard` views over those
tables — no Spark job of their own.

Alert types: `CRITICAL_FILL`, `OVERFLOW`, `PREDICTED_OVERFLOW`, `FIRE_RISK`,
`LOW_BATTERY`, `OFFLINE`, `COLLECTED`, `ANOMALY_JUMP`, `SENSOR_STUCK`,
`SENSOR_FAULT`, `SLA_BREACH`.

### One bad sensor does not lose the bin

Validation is field-level, not message-level. A field the pipeline needs — bin,
zone, capacity, fill level, timestamp — is fatal and the message is
dead-lettered whole. A sensor that can fail on its own — temperature, battery,
coordinates — is **nulled and the reading kept**, and the bin raises
`SENSOR_FAULT` naming what failed.

That distinction matters more than it looks. Rejecting the whole message for an
impossible temperature meant the bin never reached the state store, so it
vanished from every dashboard figure *and* never armed an offline timeout — a
bin publishing every five seconds became completely invisible, with the DLQ as
its only trace. The loudest possible sensor failure produced the quietest
possible outcome.

Nulled rather than clamped, because clamping 150 °C to 120 °C invents a
plausible number no sensor reported and then averages it into the zone
temperature as though it were real.

`city_kpi.faulty_sensor_bins` counts these. They stay in every other figure too,
which is the point.

### Fault injection

A share of bins (`FAULT_INJECTION_RATE`, default 12%) misbehave on purpose, so
every detector has something to detect. Without them the offline, stuck-sensor,
duplicate, sensor-fault, fire-risk and SLA rules can be written but never
observed working.

| Mode | Behaviour | Proves |
|---|---|---|
| `SILENT` | reports for a while, then stops | `OFFLINE` |
| `FROZEN` | repeats one reading forever | `SENSOR_STUCK` |
| `SPIKE` | alternates an impossible temperature and an impossible fill level | `SENSOR_FAULT` and dead-lettering |
| `DUPLICATE` | re-sends the previous event verbatim | deduplication |
| `HOT` | runs hot in proportion to how full it is | `FIRE_RISK` |
| `JUMP` | one large but legal fill jump | `ANOMALY_JUMP` |
| `UNCOLLECTED` | the truck never comes | `SLA_BREACH` |

Modes are assigned by cycling rather than drawing per bin, so a small fleet
cannot end up with no hot bin and therefore no fire alert anywhere in the run.

### Pacing, and the demo profile

The defaults are paced for a real bin: about an hour and a quarter to a critical
level, two hours to a battery alert. That is deliberate — the SLA rules allow
two hours to collect a critical bin, and at a faster rate a bin overflows dozens
of times before one SLA clock expires.

To see everything in minutes instead, uncomment the demo profile in
`.env.local.example` and copy those values into `.env.docker`. The fire-risk
temperature ramp scales with fill level, so it needs no adjusting.

Two things stay slow regardless, and both are the watermark rather than the
pacing: `zone_metrics_5m` rows only appear once the watermark passes the end of
a window, and `OFFLINE` only fires once it passes a bin's timeout. With the
default `WATERMARK` of 10 minutes, expect roughly 15 minutes before the first
window lands. Lower `WATERMARK` for a faster demo.

---

## Verification & Debugging

**View Simulator Logs:**

```bash
docker logs data_simulator -f
```

**Spark UI:** <http://localhost:4040> — the Structured Streaming tab shows what
each query is actually doing.

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

**Verify the processing layer:**

```bash
# What fired, and how much of it
docker exec -it smartbin_postgres psql -U postgres -d smart_city \
  -c "SELECT alert_type, severity, count(*) FROM bin_alerts GROUP BY 1,2 ORDER BY 3 DESC;" \
  -c "SELECT * FROM city_kpi;" \
  -c "SELECT * FROM zone_leaderboard;" \
  -c "SELECT * FROM zone_metrics_5m ORDER BY window_start DESC LIMIT 5;"

# Messages Spark refused, with the reason and the original payload
docker exec smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 --topic smartbin-telemetry-dlq \
  --from-beginning --max-messages 2 --timeout-ms 30000

# The Parquet history, partitioned by date
docker exec stream_processor ls /data/bin_events

# The nightly rollups, on demand
docker compose exec stream_processor python src/batch/rollups.py
```

With fault injection on, all eleven alert types should appear in that first
query, and `city_kpi.total_bins` should equal the number you seeded. If it is
short, some bins are being dead-lettered — compare the DLQ bin IDs against
`bin_state_latest`.

> `/data` on the stream processor is a named volume holding the checkpoints. It
> is not a cache: it holds every SLA clock, last-seen timestamp and
> deduplication key in the fleet. `docker compose down -v` erases the
> pipeline's memory, not its scratch space.
>
> Changing `STATE_SCHEMA` in `bin_state.py` makes existing checkpoints
> unreadable — Spark cannot restore state written under a different schema.
> Delete `/data/checkpoints/bin_state` after any such change.

## Testing

The data simulator has pytest coverage for its models, simulation behavior,
fault injection, configuration, migration chain, database mapping, lifecycle,
and Kafka client. The stream processor covers the payload contract, the
validation and dead-letter rules, all ten detection rules, the batch rollups,
and the streaming behaviour that batch tests cannot reach — deduplication and
the stateful operator running under a real Spark session.

The detection rules are plain Python over a dictionary, so they run without a
cluster in under a second. Each is tested both for firing when it should and
staying quiet when it should not; a rule that fires on everything looks
identical to a correct one if only the first case is checked.

Run tests locally:

```bash
cd services/data-simulator   && pytest -v
cd services/stream-processor && pytest -v
```

Or reproduce the Docker test stages:

```bash
docker build --target test \
  -t smart-city-data-simulator-test services/data-simulator
docker build --target test -f services/stream-processor/Dockerfile \
  -t smart-city-stream-processor-test .
```

_(The stream processor builds from the repository root so the shared contract is
in the build context.)_

## CI/CD Pipeline

GitHub Actions detects supported branch prefixes, enforces file scope for
`feature/` branches, and runs one pytest job per service on pull requests to
`develop`. Each service in the matrix carries its own Python version, since the
two do not agree on one.

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
