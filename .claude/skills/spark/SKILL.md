---
name: spark
description: >
  Load for the stream-processor service, PySpark Structured Streaming,
  the cleaning and dead-letter path, windowed zone aggregates, the stateful
  per-bin operator, checkpoints, or the nightly batch rollups.
---

# Stream Processor

`services/stream-processor/` reads `smartbin-telemetry-v1` with Spark
Structured Streaming and writes alerts, per-bin state and zone aggregates to
PostgreSQL, plus a Parquet event history.

One application, four queries, one separate batch entry point.

| Module | Role |
|---|---|
| `src/schema.py` | Builds the Spark schema from `contracts/telemetry-v1.json` |
| `src/session.py` | SparkSession and the Kafka source |
| `src/pipeline/clean.py` | Query 1 — parse, validate, repair, deduplicate |
| `src/pipeline/zone_metrics.py` | Query 3 — 5-minute windows per zone |
| `src/pipeline/bin_state.py` | Query 2 — the stateful operator, eleven alert types |
| `src/batch/rollups.py` | Nightly job over the Parquet history |
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
  exactly what fire risk looks for.

## Testing

The rules are plain Python over dictionaries and pandas, so most of the suite
runs without a cluster in under a second. Only what pandas cannot reach —
deduplication, windowing, the state store round-trip — uses a real session.

```bash
cd services/stream-processor
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_bin_state.py -k fire -v
```

## Checkpoints

`/data/checkpoints/<query>` holds every SLA clock, last-seen timestamp and
deduplication key. It is not a cache — deleting it erases the pipeline's memory
of the whole fleet. Changing `STATE_SCHEMA` makes the `bin_state` checkpoint
unreadable and it must be deleted.

See the `stream-processing` and `alert-detection` breadcrumbs for full traces.
