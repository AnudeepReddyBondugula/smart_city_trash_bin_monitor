---
name: spark
description: >
  Load for the stream-processor service, PySpark Structured Streaming,
  the cleaning and dead-letter path, windowed zone aggregates, the stateful
  per-bin operator, checkpoints, or the batch rollups.
---

# Stream Processor

`services/stream-processor/` reads `smartbin-telemetry-v1` with Spark
Structured Streaming and writes alerts, per-bin state and zone aggregates to
PostgreSQL, plus a Parquet event history.

One application, four queries, plus a batch entry point that runs in its own
`rollups` container on a timer.

| Module | Role |
|---|---|
| `src/schema.py` | Builds the Spark schema from `contracts/telemetry-v1.json` |
| `src/session.py` | SparkSession and the Kafka source |
| `src/pipeline/clean.py` | Query 1 — parse, validate, repair, deduplicate |
| `src/pipeline/zone_metrics.py` | Query 3 — 5-minute windows per zone |
| `src/pipeline/bin_state.py` | Query 2 — the stateful operator, twelve alert types |
| `src/batch/rollups.py` | Scheduled batch job over the Parquet history |
| `src/sinks.py` | psycopg2 writes with conflict keys |
| `sql/schema.sql` | Output tables and the dashboard views |

## Non-obvious constraints

- **Python 3.11, not 3.12.** PySpark 3.5 supports up to 3.11; on 3.12 the pandas
  operator path fails importing `distutils`. The image and CI pin it.
- **Spark 3.5 exactly.** `dropDuplicatesWithinWatermark` needs ≥ 3.5,
  `applyInPandasWithState` needs ≥ 3.4. The Kafka connector jars are baked into
  the image and must match the Spark version.
- **Java 17, not 21.** Spark 3.5 supports 8, 11 and 17. The base image is pinned
  to bookworm because trixie dropped the 17 packages.
- **`ensure_worker_interpreter()` must run before any session is built.** Spark
  launches workers as bare `python3` otherwise, and they start without pandas.
- **No JDBC anywhere.** Writes go through psycopg2, because Spark's JDBC writer
  can only append or overwrite and every table here needs an upsert. That also
  keeps the Kafka connector as the only jars in the image.

## Rules that shaped the design

- **Every write is idempotent.** Spark retries a micro-batch after a failed
  write. Appending would double-count on every retry, so each table has a
  conflict key.
- **No join against `smart_bins`.** Zone and capacity travel on every event.
- **Validation is field-level, not message-level.** A field the pipeline needs
  (`TRACKING_FIELDS`) is fatal and the message is dead-lettered. A sensor that
  can fail alone (`REPAIRABLE_FIELDS`) is nulled and the reading kept, so a bin
  with a dead thermometer stays visible rather than disappearing from every
  figure and never arming an offline timeout.
- **Bounds come from the contract**, never restated in code. Too narrow a range
  would reject the readings a rule exists to catch — a bin above 70 °C is
  exactly what fire risk looks for. Exclusivity is carried through, not
  flattened: `capacity` is `exclusiveMinimum: 0`, and a zero admitted there
  divides to a null `fill_pct` that every fill rule then compares against a
  threshold — which raises in the worker and stops the application.
- **Fire-once flags clear on a collection and nothing else.** Clearing them
  whenever the level falls back under the threshold lets a bin oscillating
  around 80% re-alert on every crossing and restart its SLA clock each time.
- **Alert types are the database key.** `bin_alerts` is keyed on
  `(bin_id, alert_type, fired_at)`, so two conditions that can come due on the
  same reading need distinct types — which is why the SLA breach is
  `SLA_BREACH_CRITICAL` and `SLA_BREACH_OVERFLOW` rather than one type with a
  label in `detail`.
- **The dashboard views are built from the same settings as the rules.**
  `sinks.schema_sql()` fills the thresholds into `sql/schema.sql`, so
  `city_kpi` cannot disagree with the alerts — and `sql/schema.sql` cannot be
  run through `psql` directly, because it carries placeholders.

## The Spark UI

<http://localhost:4040>, published from the container. The **Structured
Streaming** tab is the one that matters: input and processing rate, batch
duration, watermark position and state store size per query, none of which the
logs report. Open it before guessing why a query looks stalled.

The batch job binds <http://localhost:4041> instead, because it runs alongside
the streaming application — only for the length of each run. Both are set explicitly with
`spark.ui.portMaxRetries=0`, so a bind failure is loud rather than a silent move
to another port.

## Testing

The rules are plain Python over dictionaries and pandas, so most of the suite
runs without a cluster in under a second. Only what pandas cannot reach —
deduplication, windowing, the state store round-trip — uses a real session.

```bash
cd services/stream-processor
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_bin_state.py -k fire -v
```

## Shutdown

`main.run()` waits on `awaitAnyTermination` **with a timeout** and loops. That is
not a style choice: Python runs a signal handler between bytecodes, so while the
main thread is inside an unbounded py4j call SIGTERM is never noticed and Docker
kills the container. The queries are then stopped by name so each finishes its
micro-batch and commits offsets, and the service carries `stop_grace_period: 60s`
because ten seconds is not enough for four of them.

A killed container loses nothing — checkpoints and idempotent writes cover it —
but it reports as exit 137, which is the wrong thing to leave in
`docker compose ps` for an ordinary stop.

## Checkpoints

`/data/checkpoints/<query>` holds every SLA clock, last-seen timestamp and
deduplication key. It is not a cache — deleting it erases the pipeline's memory
of the whole fleet. Changing `STATE_SCHEMA` makes the `bin_state` checkpoint
unreadable and it must be deleted.

See the `stream-processing` and `alert-detection` breadcrumbs for full traces.
