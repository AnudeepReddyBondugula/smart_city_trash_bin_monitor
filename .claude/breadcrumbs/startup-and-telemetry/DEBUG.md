# Startup and Telemetry Generation — Debug Guide

Logs go to the color console and rotating `logs/simulator.log`. `SIGUSR1`
toggles debug logging for a native process.

### The two ways startup fails

Migrations are a deliberate manual step, so both bad states are ordinary and
both now answer themselves:

- **Not migrated** — `The 'smart_bins' table does not exist.` followed by the
  commands to run. The process exits 1 after releasing the Kafka producer and
  the engine. A raw SQLAlchemy traceback here instead means the image is stale.
- **Migrated but unseeded** — a warning naming the seed command. Not fatal; the
  process keeps running and publishes nothing.

### A healthy simulator logs nothing

Per-tick telemetry is DEBUG. `docker logs data_simulator -f` showing no output
after `Started N simulator(s).` means it is working. Confirm activity from
Kafka or `bin_state_latest` rather than the log, or raise the level with
`SIGUSR1`.

| Symptom | Check |
|---|---|
| `No ACTIVE bins found` | Seed the database; the message carries the command. |
| `The 'smart_bins' table does not exist` | Run `alembic upgrade head` first. |
| Raw SQLAlchemy traceback on startup | Stale image. `docker compose build data_simulator`. |
| `Unclosed AIOKafkaProducer` | Cleanup was skipped on an error path. Should not happen — startup and shutdown both run cleanup in a `finally`. |
| Kafka connection retries | Verify `KAFKA_BOOTSTRAP_SERVERS` for Docker versus native execution. |
| Send failures | Search logs for `Failed to send telemetry`. Messages are dropped, not retried. |
| Payload lacks zone or temperature | Rebuild and force-recreate the simulator container; do not judge new format with `--from-beginning`. |
| Pydantic validation error before startup | A required PostgreSQL or Kafka environment variable is missing. |

```bash
docker exec smartbin_postgres psql -U postgres -d smart_city \
  -c "SELECT status, COUNT(*) FROM smart_bins GROUP BY status;"

docker compose build data_simulator
docker compose up -d --force-recreate data_simulator

docker exec smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic smartbin-telemetry-v1 \
  --max-messages 2 --timeout-ms 20000
```

Runtime fleet size comes from active rows, not `NUMBER_OF_BINS`.

Some bins are silent, frozen or publishing impossible values on purpose. Before
treating that as a bug, check [`fault-injection`](../fault-injection/DEBUG.md).
