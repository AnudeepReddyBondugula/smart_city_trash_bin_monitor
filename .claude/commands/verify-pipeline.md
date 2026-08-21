---
description: Bring up the full stack and check every Spark output end to end.
---

# /verify-pipeline

Runs simulator and stream-processor together against real Postgres and Kafka,
then checks that every output is populated. Use this after changing anything in
the processing layer — the unit suites cannot catch image, contract-path,
checkpoint or topic problems.

## Clean slate

State from a previous run makes a broken pipeline look healthy, and a changed
`STATE_SCHEMA` makes old checkpoints unreadable:

```bash
docker compose down -v
```

`-v` removes the Postgres volume **and** `/data`, which holds the checkpoints
and Parquet history.

## Demo profile

Without it the first critical bin is ~75 minutes away. Append to
`services/data-simulator/.env.docker` (gitignored):

```bash
FILL_RATE_PCT_MIN=1.0
FILL_RATE_PCT_MAX=6.0
BATTERY_DRAIN_MIN=1.0
BATTERY_DRAIN_MAX=3.0
FAULT_INJECTION_RATE=0.15
STUCK_READING_COUNT=5
SLA_CRITICAL_MINUTES=1
SLA_OVERFLOW_MINUTES=1
OFFLINE_AFTER_MINUTES=1
WATERMARK=2 minutes
```

`WATERMARK` is the one that matters most: windowed output and offline alerts are
gated by it, not by fill rate. At the 10-minute default the first zone window is
~15 minutes away regardless of how fast bins fill.

## Bring it up

```bash
docker compose build data_simulator stream_processor
docker compose up -d postgres kafka kafka_init
docker compose run --rm data_simulator alembic upgrade head
docker compose run --rm data_simulator python src/seed.py --count 200 --clear
docker compose up -d data_simulator stream_processor
```

`alembic upgrade head` names each revision it applies. Only the two
`Context impl` lines means the database was already at head.

Always `build` before `up`. A stale image is the most common cause of "the
change did nothing".

## Check startup

```bash
docker logs data_simulator   2>&1 | grep -E "Injected|Started .* simulator"
docker logs stream_processor 2>&1 | grep -E "Started 4 streaming|schema applied"
```

`Injected faults into N of M bin(s).` must appear, or no detector will fire.

Then open the Spark UI at <http://localhost:4040> and check the **Structured
Streaming** tab lists all four queries with a non-zero input rate. That is the
fastest confirmation the pipeline is actually consuming, and it is quicker than
waiting on any table.

## Check the outputs

```bash
docker exec -it smartbin_postgres psql -U postgres -d smart_city \
  -c "SELECT alert_type, severity, count(*) FROM bin_alerts GROUP BY 1,2 ORDER BY 3 DESC;" \
  -c "SELECT * FROM city_kpi;" \
  -c "SELECT * FROM zone_leaderboard;" \
  -c "SELECT count(*) FROM zone_metrics_5m;"
```

Expect all eleven alert types given enough time. Rough ordering:

| Wait | Appears |
|---|---|
| ~30s | `PREDICTED_OVERFLOW`, `SENSOR_FAULT` |
| 1–3 min | `CRITICAL_FILL`, `OVERFLOW`, `COLLECTED`, `ANOMALY_JUMP`, `SENSOR_STUCK`, `FIRE_RISK` |
| 3–5 min | `SLA_BREACH`, `LOW_BATTERY` |
| watermark | `OFFLINE`, `zone_metrics_5m` |

`total_bins` in `city_kpi` should equal the seeded count. If it is short, some
bins are being dead-lettered — see `stream-processing/DEBUG.md`.

## Check the rest

```bash
# Partition count - must be 12, not 1
docker exec smartbin_kafka kafka-topics --bootstrap-server localhost:9092 \
  --describe --topic smartbin-telemetry-v1 | head -1

# Dead letters carry reason, provenance and the original payload
docker exec smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 --topic smartbin-telemetry-dlq \
  --from-beginning --max-messages 2 --timeout-ms 30000

# Parquet history, date-partitioned
docker exec stream_processor ls /data/bin_events

# Nightly rollups
docker compose exec stream_processor python src/batch/rollups.py
docker exec -it smartbin_postgres psql -U postgres -d smart_city \
  -c "SELECT * FROM zone_hourly_profile ORDER BY avg_fill_rate_pct_hour DESC NULLS LAST LIMIT 5;" \
  -c "SELECT * FROM zone_daily_trend;"
```

## Cross-check

The streaming rule and the batch window function compute collections
independently. They should agree within the events in flight:

```bash
docker exec smartbin_postgres psql -U postgres -d smart_city -tAc \
  "SELECT (SELECT sum(collections) FROM zone_daily_trend),
          (SELECT count(*) FROM bin_alerts WHERE alert_type='COLLECTED');"
```

## Tear down

```bash
docker compose down          # keeps data
docker compose down -v       # erases checkpoints and history too
```

Restore `.env.docker` afterwards if you appended the demo profile.
