# Stream Processing

Trigger: `python src/main.py` or the `stream_processor` container command.

```text
apply sql/schema.sql (idempotent)
  → build SparkSession (RocksDB state store, local[*])
  → readStream from KAFKA_TOPIC
  → clean_events: parse → watermark → dedupe → fill_pct → repair
  → start four queries, each with its own checkpoint:
      bin_events    → Parquet, partitioned by event_date
      dead_letters  → KAFKA_DLQ_TOPIC
      zone_metrics  → zone_metrics_5m      (5-minute windows per zone)
      bin_state     → bin_alerts, bin_state_latest
  → awaitAnyTermination
```

One application, one Kafka read, four queries over it. Cleaning is a plain
DataFrame transformation shared by all of them, not a hop through storage, so a
reading is parsed and deduplicated exactly once.

There is **no join against `smart_bins`**. Zone and capacity travel on every
event, so the stream needs no database read on the ingest path.

Separate checkpoint directories mean one query can be reset without disturbing
the others. The checkpoints are not a cache — see `DEBUG.md`.

The per-bin rules are documented in [`alert-detection`](../alert-detection/FLOW.md).
The batch rollup job reads the Parquet this flow writes.
