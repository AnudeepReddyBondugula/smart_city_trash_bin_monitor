# Alert Detection — Debug Guide

## Symptom routing

| Symptom | Check |
|---|---|
| One alert type never fires | Its condition may not be reachable. Check the matching fault mode is being injected — see [`fault-injection`](../fault-injection/DEBUG.md). |
| `FIRE_RISK` never fires | Needs hot **and** nearly full together. A bin pinned hot while empty satisfies one half forever and the other never. |
| `OFFLINE` never fires | Watermark, not the rule — see [`stream-processing/DEBUG.md`](../stream-processing/DEBUG.md). Also: a bin that never published at all has no state and no timer. |
| `SLA_BREACH` never fires | Every healthy bin is collected well inside the allowance. Only an `UNCOLLECTED` bin breaches. |
| An alert fires on every reading | Its fire-once flag is not being set, or is cleared each time by the reading itself. |
| The same alert repeats after a restart | The checkpoint was deleted, so every bin looks new. |
| `COLLECTED` where no collection happened | Events processed out of order. `track_bin` sorts by `event_time`; check that sort survived an edit. |
| Alerts duplicated in `bin_alerts` | The `(bin_id, alert_type, fired_at)` conflict key is missing. Retried micro-batches rely on it. |
| Query fails on restart after editing rules | `STATE_SCHEMA` changed — delete the `bin_state` checkpoint. |

## Which conditions are currently reachable

```bash
docker exec smartbin_postgres psql -U postgres -d smart_city -c \
  "SELECT alert_type, severity, count(*), max(fired_at) AS latest
     FROM bin_alerts GROUP BY 1,2 ORDER BY 3 DESC;"
```

With fault injection on, all eleven types should appear given enough time.
`FIRE_RISK` and `OFFLINE` will have the smallest counts — only a few bins carry
those faults.

## Inspecting one bin

```bash
docker exec smartbin_postgres psql -U postgres -d smart_city -c \
  "SELECT alert_type, fired_at, fill_pct, temperature, detail
     FROM bin_alerts WHERE bin_id = 'BIN-XXXXXXXX-X' ORDER BY fired_at;"

docker exec smartbin_postgres psql -U postgres -d smart_city -c \
  "SELECT * FROM bin_state_latest WHERE bin_id = 'BIN-XXXXXXXX-X';"
```

Every alert carries a `detail` string with the numbers that triggered it, which
is usually faster than reasoning about the rule.

## Reproducing a rule without the stack

The rules are plain Python. To check one by hand:

```bash
cd services/stream-processor
PYTHONPATH=src .venv/bin/python -c "
from pipeline.bin_state import EMPTY_STATE, evaluate_reading
memory = dict(EMPTY_STATE)
reading = dict(zone='CENTRAL', capacity=100.0, current_fill_level=85.0,
               fill_pct=85.0, temperature=25.0, battery_level=80.0,
               latitude=17.4, longitude=78.5, sensor_faults=None,
               event_ms=1755000000000)
print([a['alert_type'] for a in evaluate_reading(memory, reading, 'BIN-1')])
"
```

Or run the suite for one rule:

```bash
cd services/stream-processor && .venv/bin/python -m pytest tests/test_bin_state.py -k fire -v
```
