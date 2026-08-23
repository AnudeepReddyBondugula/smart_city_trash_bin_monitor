# Fault Injection — Debug Guide

## Is it even on?

```bash
docker logs data_simulator 2>&1 | grep Injected
# Injected faults into 30 of 200 bin(s).
```

No line means `faulty_count` was zero. Either `FAULT_INJECTION_RATE=0`, the
fleet is too small for the rate to round up to one bin, or — the common one —
the container is running an image built before the change:

```bash
docker compose build data_simulator
docker compose up -d --force-recreate data_simulator
```

`restart` is not enough; it reuses the old image.

## Symptom routing

| Symptom | Check |
|---|---|
| No faults logged | See above. Rebuild before anything else. |
| One mode's detector never fires | With a small fleet, `int(len * rate)` may not reach that mode's index. Raise the count or the rate. |
| `SLA_BREACH_CRITICAL` / `SLA_BREACH_OVERFLOW` missing | Only `UNCOLLECTED` bins can breach, and only after `SLA_CRITICAL_MINUTES`. Hours on the default profile. |
| `LOW_BATTERY` missing | Battery has not drained to 20% yet. ~2 hours by default. |
| `FIRE_RISK` missing | A `HOT` bin must also be nearly full. If bins are collected before 80%, check `COLLECTION_THRESHOLD_PCT` is above 80. |
| Duplicates not being removed | The duplicate must carry the original timestamp. Confirm `_next_payload` is not regenerating the payload. |
| Bins missing from `bin_state_latest` | `SPIKE` bins sending an impossible fill level are dead-lettered. A `SPIKE` bin should still appear via its alternating temperature readings. |
| Bins never go critical | Fill rate versus `COLLECTION_THRESHOLD_PCT` — bins may be emptied before reaching 80%. |

## Which bins carry which fault

Fault mode is in-memory only and is not persisted, so it cannot be queried from
PostgreSQL. Assignment is deterministic by position in the fleet load order,
which the debug log reports:

```bash
docker logs data_simulator 2>&1 | grep -iE "silent|frozen|re-sending|emptied" | head -20
```

Enable debug logging first (`SIGUSR1` on a native process, or set the level in
`logging_config.py`). Otherwise, identify them by behaviour:

```bash
# SPIKE bins - the only ones in the dead-letter topic
docker exec smartbin_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 --topic smartbin-telemetry-dlq \
  --from-beginning --max-messages 200 --timeout-ms 30000 2>/dev/null \
  | grep -oE 'bin_id\\": \\"[A-Z0-9-]+' | sed 's/.*"//' | sort -u

# SILENT bins - the stalest last_seen
docker exec smartbin_postgres psql -U postgres -d smart_city -c \
  "SELECT bin_id, last_seen FROM bin_state_latest ORDER BY last_seen LIMIT 10;"

# HOT bins - at or near TEMP_FIRE_MAX
docker exec smartbin_postgres psql -U postgres -d smart_city -c \
  "SELECT bin_id, temperature, fill_pct FROM bin_state_latest
    WHERE temperature > 60 ORDER BY temperature DESC;"

# SPIKE bins with a nulled sensor, still tracked
docker exec smartbin_postgres psql -U postgres -d smart_city -c \
  "SELECT bin_id, sensor_faults FROM bin_state_latest
    WHERE sensor_faults IS NOT NULL;"
```

## Turning it off

`FAULT_INJECTION_RATE=0` in `.env.docker`, then rebuild-free restart is enough
since it is read from the environment:

```bash
docker compose up -d --force-recreate data_simulator
```

Existing alerts stay in `bin_alerts`; only new ones stop.
