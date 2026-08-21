# Startup and Telemetry Generation — Debug Guide

Logs go to the color console and rotating `logs/simulator.log`. `SIGUSR1`
toggles debug logging for a native process.

| Symptom | Check |
|---|---|
| `Started 0 simulator(s)` | Query `smart_bins` for active rows and seed if empty. |
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
