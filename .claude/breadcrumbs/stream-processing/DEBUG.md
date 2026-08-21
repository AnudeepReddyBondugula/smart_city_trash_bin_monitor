# Stream Processing — Debug Guide

Logs go to the color console and rotating `logs/stream-processor.log`. `py4j` is
pinned to WARNING or it buries everything else. `SIGUSR1` toggles debug logging.

## The two that look like bugs and are not

**Empty `zone_metrics_5m`, no `OFFLINE` alerts.** Both are gated by the
watermark, not by how fast bins fill. A window is only written once the
watermark passes its end, and an offline timeout only fires once it passes the
bin's deadline. With the default `WATERMARK` of 10 minutes, expect ~15 minutes
before the first window lands. Lower `WATERMARK` for a demo. Everything else
appears within a minute or two.

**An offline timeout fires because *other* bins are still reporting.** The
watermark advances on stream progress. If the entire simulator stops, no
`OFFLINE` alert is produced at all, because Spark cannot distinguish "every bin
died" from "the stream ended". A liveness check on Kafka lag covers that case;
this pipeline cannot.

## Symptom routing

| Symptom | Check |
|---|---|
| `ModuleNotFoundError: distutils` | Python 3.12. PySpark 3.5 supports up to 3.11; the image pins it. Locally, `setuptools` restores the shim. |
| `ModuleNotFoundError` for `pandas`, `pyarrow`, or a project module, from inside a Spark stack trace | Spark's workers launched under a different interpreter. `ensure_worker_interpreter()` handles it; in tests `conftest.py` also sets `PYTHONPATH`. |
| Contract not found at startup | `config.CONTRACT_PATH` searches upward for `contracts/telemetry-v1.json`. The image copies it to `/app/contracts/`; the build context must be the repo root. |
| Every alert type but one is firing | Check fault injection is on — see [`fault-injection`](../fault-injection/DEBUG.md). |
| Bins missing from `bin_state_latest` | Their messages are being dead-lettered. Query the DLQ and compare bin IDs (below). |
| Rows duplicated in an output table | A conflict key is missing or wrong in `sql/schema.sql`. Retried micro-batches rely on it. |
| Query fails on restart after a code change | `STATE_SCHEMA` changed. Spark cannot restore state written under a different schema — delete the `bin_state` checkpoint. |
| `SparkUI could not bind on port ...` | Ports are now bound explicitly with no retry, so this means something else already holds it. Check for a second stream-processor container. |

## Start at the Spark UI

<http://localhost:4040>, **Structured Streaming** tab. Per query it reports
input rate, processing rate, batch duration, watermark position and state store
size — none of which appears in the logs, and all of which answers "is this
query stalled, starved, or just waiting for the watermark" faster than any
query against PostgreSQL.

The batch job is on <http://localhost:4041> while it runs.

If a query is missing from that tab it never started; check the logs for the
`Started 4 streaming quer(ies)` line.

## Checkpoints are not a cache

`/data/checkpoints` holds every SLA clock, last-seen timestamp and deduplication
key in the fleet. `docker compose down -v` erases the pipeline's memory, not its
scratch space. Delete one query's directory to reset only that query:

```bash
docker compose exec stream_processor rm -rf /data/checkpoints/bin_state
docker compose restart stream_processor
```

## Commands

```bash
# Which bins are being dead-lettered, and are therefore absent downstream
docker exec smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 --topic smartbin-telemetry-dlq \
  --from-beginning --max-messages 200 --timeout-ms 30000 2>/dev/null \
  | grep -oE 'bin_id\\": \\"[A-Z0-9-]+' | sed 's/.*"//' | sort -u

# Seeded bins that never reached the state store
docker exec smartbin_postgres psql -U postgres -d smart_city -c \
  "SELECT bin_id FROM smart_bins s WHERE NOT EXISTS
     (SELECT 1 FROM bin_state_latest b WHERE b.bin_id = s.bin_id);"

# Bins reporting a broken sensor but still tracked
docker exec smartbin_postgres psql -U postgres -d smart_city -c \
  "SELECT bin_id, sensor_faults, fill_pct FROM bin_state_latest
    WHERE sensor_faults IS NOT NULL;"

# Query health
docker logs stream_processor 2>&1 | grep -E "Started 4 streaming|ERROR"
```

Two independent implementations of "a collection" exist — the streaming rule and
the batch window function. Comparing them is a useful cross-check:

```bash
docker exec smartbin_postgres psql -U postgres -d smart_city -tAc \
  "SELECT (SELECT sum(collections) FROM zone_daily_trend),
          (SELECT count(*) FROM bin_alerts WHERE alert_type='COLLECTED');"
```

They should agree within the events in flight between the two queries' triggers.
A large gap means one of the two rules has drifted.
