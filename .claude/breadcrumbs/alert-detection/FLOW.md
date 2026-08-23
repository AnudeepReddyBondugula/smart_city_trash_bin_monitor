# Alert Detection

Trigger: the `bin_state` streaming query, started from `src/main.py`.

```text
clean_events
  → groupBy("bin_id").applyInPandasWithState(track_bin, EventTimeTimeout)
  → per bin, per batch:
        read state
        sort this batch's events by event_time
        fold each reading through evaluate_reading()
        write state
        arm timeout at last_event + OFFLINE_AFTER_MINUTES
  → emit alert rows + one state row (record_type discriminates)
  → foreachBatch splits them:
        ALERT → bin_alerts        (insert, on conflict do nothing)
        STATE → bin_state_latest  (upsert on bin_id)
```

Twelve alert types come out of one state read per event:

| Fires once, cleared by | Types |
|---|---|
| collection | `CRITICAL_FILL`, `OVERFLOW`, `PREDICTED_OVERFLOW`, `SLA_BREACH_CRITICAL` / `SLA_BREACH_OVERFLOW` |
| the condition ending | `LOW_BATTERY` |
| each newly named sensor | `SENSOR_FAULT` |
| crossing the threshold | `SENSOR_STUCK` |
| — (per event) | `COLLECTED`, `ANOMALY_JUMP` |
| repeats on an interval | `FIRE_RISK` |
| a timer, not a rule | `OFFLINE` |

`CRITICAL_FILL`, `LOW_BATTERY` and `FIRE_RISK` look like plain filters. They are
not: a bare filter re-fires for as long as the condition holds, so one bin stuck
at 88% produces an alert every few seconds forever. Firing once needs per-bin
memory, which is why they live here.

Thresholds are all in `src/config.py`, not scattered through the rules - and
the `city_kpi` and `zone_leaderboard` views are built from the same settings at
startup, so the dashboard cannot disagree with the alerts about what "critical"
or "offline" means.
