# Stream Processing — Detailed Trace

Paths are relative to `services/stream-processor/`.

1. `src/main.py` calls `setup_logging()`, then `sinks.apply_schema()` executes
   `sql/schema.sql` through psycopg2. The file is `CREATE ... IF NOT EXISTS`
   throughout, so a restart never destroys accumulated history.
2. `session.build_session()` calls `ensure_worker_interpreter()` first, which
   points `PYSPARK_PYTHON` at `sys.executable`. Without it Spark launches its
   workers as bare `python3` and pandas operators fail on a missing import.
3. The session sets `RocksDBStateStoreProvider` with changelog checkpointing,
   `spark.sql.shuffle.partitions=12`, and UTC as the session time zone.
4. `session.read_telemetry()` opens the Kafka source with `startingOffsets`,
   `maxOffsetsPerTrigger` and `failOnDataLoss=false`. It returns the raw
   records, not parsed ones, because the dead-letter path needs the original
   bytes.
5. `pipeline.clean.parse()` casts `value` to string, applies
   `schema.telemetry_schema()` — built from `contracts/telemetry-v1.json`, not
   restated in code — and derives `event_time` from the ISO `timestamp` field.
6. `pipeline.clean.split_valid_and_rejected()` computes two columns:
   - `rejection_reason` covers only `TRACKING_FIELDS` plus the cross-field check
     `current_fill_level > capacity`. These make a message unusable.
   - `sensor_fault_reason` covers `REPAIRABLE_FIELDS`. These are nulled by
     `repair()` and the reading is kept, so a bin with one failed sensor stays
     tracked instead of vanishing from monitoring.
   Bounds for both come from the contract via `schema.range_rules()`.
7. `clean_events()` applies the watermark, then
   `dropDuplicatesWithinWatermark(["bin_id", "event_time"])`, then computes
   `fill_pct = current_fill_level / capacity * 100` guarded against a
   non-positive capacity.
8. Four queries start, each with `settings.checkpoint_for(<name>)`:
   - `bin_events` writes Parquet partitioned by `event_date`.
   - `dead_letters` writes to `KAFKA_DLQ_TOPIC`; the envelope is built with
     `to_json(struct(...))` so an unparseable payload cannot corrupt it.
   - `zone_metrics` aggregates 5-minute windows per zone, append mode, upserted
     on `(window_start, zone)`.
   - `bin_state` runs the stateful operator; see the alert-detection breadcrumb.
9. `sinks.write_batch()` collects each micro-batch to the driver and writes with
   `execute_values`. Every table has a conflict key, because Spark retries a
   micro-batch after a failed write and an append would double-count.
10. `session.streams.awaitAnyTermination()` blocks, so a failed query surfaces
    instead of leaving the process alive around a dead one.

`src/batch/rollups.py` is a separate entry point over the Parquet history and
does not participate in this flow.

## Output tables

| Table | Written by | Conflict key | Mode |
|---|---|---|---|
| `bin_alerts` | `bin_state` | `(bin_id, alert_type, fired_at)` | do nothing |
| `bin_state_latest` | `bin_state` | `bin_id` | update |
| `zone_metrics_5m` | `zone_metrics` | `(window_start, zone)` | update |
| `zone_hourly_profile` | `batch/rollups.py` | `(zone, hour_of_day)` | update |
| `zone_daily_trend` | `batch/rollups.py` | `(zone, day)` | update |

`city_kpi` and `zone_leaderboard` are views over those tables. No Spark job
computes dashboard figures.
