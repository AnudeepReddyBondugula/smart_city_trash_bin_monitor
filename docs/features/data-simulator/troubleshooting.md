# Troubleshooting

Common failure modes, keyed to real error handling and log messages in the
source. Each entry: **symptom → likely cause → fix**.

---

## `docker compose up` fails: env file not found

**Symptom:** Compose errors immediately with something like
`env file .../services/data-simulator/.env.docker not found`.

**Cause:** `docker-compose.yml` reads `./services/data-simulator/.env.docker`,
but that file is **git-ignored** and absent on a fresh clone. The root
`README.md` tells you to create `.env.docker.local` instead — a name Compose
never references. (See [configuration.md](configuration.md) for the full
discrepancy.)

**Fix:**

```bash
cp services/data-simulator/.env.local.example services/data-simulator/.env.docker
# then set, in that file:
#   POSTGRES_HOST=postgres
#   KAFKA_BOOTSTRAP_SERVERS=kafka:29092
```

---

## Simulator logs `Started 0 simulator(s).` and no telemetry appears

**Symptom:** startup succeeds but the Kafka topic stays empty; log shows
`Started 0 simulator(s).`

**Cause:** the `smart_bins` table has no `ACTIVE` rows.
`SimulationManager.initialize()` only loads bins `where status == "ACTIVE"`
(`simulation_manager.py:43-45`), so with an empty/unsimulated DB there is
nothing to emit.

**Fix:** seed data, then restart to reload:

```bash
docker compose run --rm data_simulator python src/seed.py --count 50
docker compose restart data_simulator
```

Remember the simulator loads bins **once at startup** — seeding without a
restart does nothing.

---

## Seeded bins, but still no telemetry

**Symptom:** `smart_bins` has rows (confirmed via `psql`), but the topic is
still empty.

**Cause:** the simulator was already running when you seeded; it never re-reads
the DB.

**Fix:** `docker compose restart data_simulator`. Confirm the log now says
`Started N simulator(s).` with N > 0. (See
[simulation-engine.md](simulation-engine.md) on the one-shot load.)

---

## Repeated `Kafka not ready yet (...), retrying... (i/10)`

**Symptom:** startup loops on this warning
(`kafka_producer.py:33-35`).

**Cause:** the broker is not reachable at `KAFKA_BOOTSTRAP_SERVERS`. Normal for
a few seconds at boot (the simulator has **no** `depends_on: kafka`), but a
problem if it persists. Usual reasons:

- Wrong address for the context: containers must use `kafka:29092`; host
  processes must use `localhost:9092` (see [kafka.md](kafka.md)).
- Kafka container unhealthy/not started.

**Fix:** verify the value matches where you're running (`.env.docker` =
`kafka:29092`, `.env.local` = `localhost:9092`); check `docker ps` /
`docker logs smartbin_kafka`.

---

## `Could not connect to Kafka ... after multiple retries` then the process exits

**Symptom:** after 10 attempts (~30s) the producer raises and `main()` never
starts the manager; the container exits.

**Cause:** Kafka was unreachable for the full retry window
(`kafka_producer.py:42-44`).

**Fix:** ensure Kafka is up and the bootstrap address is correct, then restart
`data_simulator`. Increase the retry budget only if your broker is legitimately
slow to start (edit the `retries`/sleep in `KafkaClient.start`).

---

## `Kafka producer is not started; dropping telemetry for <bin>`

**Symptom:** this error is logged and payloads are lost
(`kafka_producer.py:52-56`).

**Cause:** `send_telemetry` was called before `kafka_client.start()` completed.
In normal operation `main()` starts the client before the manager, so seeing
this suggests a startup-order regression or a partially failed start.

**Fix:** check that `Kafka Client Started Successfully` appears **before**
`Started N simulator(s).` in the logs; if not, investigate the start sequence in
`src/main.py`.

---

## `Failed to send telemetry for <bin>: <error>`

**Symptom:** intermittent per-message errors; telemetry has gaps
(`kafka_producer.py:61-62`).

**Cause:** a `send_and_wait` failed (broker hiccup, timeout). Delivery is
best-effort — the failed message is **dropped, not retried**
(see [kafka.md](kafka.md#delivery-guarantees-as-actually-configured)).

**Fix:** usually self-heals on the next tick (a fresh full snapshot is sent). If
frequent, investigate broker health; for stronger guarantees add producer
`acks="all"` + `enable_idempotence=True` + retries.

---

## DB connection errors / `An error occurred while seeding: ...`

**Symptom:** the simulator can't reach Postgres at startup, or `seed.py` prints
`An error occurred while seeding: <error>` (`seed.py:45-46`).

**Cause:** wrong `POSTGRES_*` values or Postgres not ready/healthy. Note the
**host port is 5433** (`docker-compose.yml`), while the containers and the
`.env.local` template use **5432**.

- From another container: host `postgres`, port `5432`.
- From the host machine (e.g. a psql client, or the hybrid `run_local` mode
  connecting to the published port): `localhost:5433`.

**Fix:** align `POSTGRES_HOST`/`POSTGRES_PORT` with where the client runs. Note
`data_simulator` waits for Postgres health (`condition: service_healthy`), so
startup DB failures usually indicate bad credentials/DB name rather than
readiness.

> **Known port mismatch:** `scripts/run_local.sh` sources `.env.local`, whose
> template still has `POSTGRES_PORT=5432`, but Docker publishes Postgres on the
> host as **5433**. If you run the simulator natively against the Dockerized
> Postgres, set `POSTGRES_PORT=5433` in your `.env.local`. *(TODO: confirm with
> team and align the template.)*

---

## Seeding refuses more than 500 bins

**Symptom:** `Error: For safety, you cannot seed more than 500 bins at a time.`

**Cause:** intentional guard in `seed.py:16-18`.

**Fix:** run `seed.py` multiple times, or raise the guard if you genuinely need
more (and see [operations.md](operations.md#scaling) on scale limits).

---

## Table does not exist when seeding/running

**Symptom:** a "relation smart_bins does not exist" style error.

**Cause:** nothing in the startup path or `seed.py` creates the schema — only
`create_tables.py` does, and there are no Alembic migrations (see
[database.md](database.md)).

**Fix:**

```bash
docker compose run --rm data_simulator python src/create_tables.py
```

---

## Duplicate telemetry for every bin

**Symptom:** each `bin_id` appears multiple times per interval on the topic.

**Cause:** more than one `data_simulator` instance is running; each loads the
same `ACTIVE` bins. Horizontal scaling is not supported as-is
(see [operations.md](operations.md#scaling)).

**Fix:** run a single simulator instance.

---

## Tests fail to import (`ModuleNotFoundError`)

**Symptom:** `pytest` can't import `src...` or `database`/`config`.

**Cause:** missing path setup. Tests rely on `pythonpath = . src` from
`pytest.ini`; CI additionally sets `PYTHONPATH=src`.

**Fix:** run from `services/data-simulator/` (so `pytest.ini` is picked up), or
`PYTHONPATH=src pytest -v`. See [testing.md](testing.md).

---

## Related documents

- [operations.md](operations.md) — monitoring and the log signals table.
- [configuration.md](configuration.md) — env vars and the env-file discrepancy.
- [kafka.md](kafka.md) / [database.md](database.md) — subsystem specifics.
