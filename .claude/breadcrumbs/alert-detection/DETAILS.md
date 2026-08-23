# Alert Detection — Detailed Trace

All in `services/stream-processor/src/pipeline/bin_state.py`.

## Entry

`evaluate()` wires `track_bin` into `applyInPandasWithState` with
`OUTPUT_SCHEMA`, `STATE_SCHEMA`, append output and `EventTimeTimeout`.

`track_bin(key, pdfs, state)`:

1. `read_state(state)` returns the remembered values, or `EMPTY_STATE` for a bin
   never seen before.
2. If `state.hasTimedOut`, emit `OFFLINE` from the remembered values and return.
   State is kept, not removed, so a bin that starts reporting again is
   recognised as the same bin.
3. Otherwise sort each frame by `event_time` and fold every row through
   `evaluate_reading()`. **Spark makes no ordering promise within a batch**, and
   every rule compares against the previous reading — out of order, a rise reads
   as a drop and a collection is invented that never happened.
4. `write_state(state, memory)` stores the tuple in `STATE_FIELDS` order.
5. `state.setTimeoutTimestamp(max(last_event + offline_window, watermark + 1))`.
   The clamp matters: Spark rejects a timeout already behind the watermark,
   which is exactly what a late-arriving event asks for.
6. Yield the alerts plus one `state_record`, as a single pandas frame.

## The rules, in order

`evaluate_reading(memory, reading, bin_id)` updates `memory` in place first, so
every rule below describes the bin as it now is.

| Rule | Condition | State touched |
|---|---|---|
| `COLLECTED` | previous ≥ `COLLECTION_DROP_FROM_PCT` and now < `COLLECTION_DROP_TO_PCT` | clears both SLA clocks and every fire-once flag |
| `ANOMALY_JUMP` | rise ≥ `ANOMALY_JUMP_PCT` since the previous reading | none |
| `SENSOR_STUCK` | `unchanged_count` **equals** `STUCK_READING_COUNT`, below 100% | `unchanged_count` |
| `CRITICAL_FILL` | ≥ `CRITICAL_FILL_PCT` and not already fired | `critical_fired`, `critical_since_ms` |
| `OVERFLOW` | ≥ `OVERFLOW_FILL_PCT` and not already fired | `overflow_fired`, `overflow_since_ms` |
| `PREDICTED_OVERFLOW` | projected full within 60 min, still below critical | `predicted_fired` |
| `FIRE_RISK` | temp > `FIRE_RISK_TEMP_C` **and** fill > `FIRE_RISK_FILL_PCT` | `last_fire_risk_ms` |
| `LOW_BATTERY` | < `LOW_BATTERY_PCT` and not already fired | `low_battery_fired` |
| `SENSOR_FAULT` | `sensor_faults` names a sensor not in `reported_faults` | `reported_faults` |
| `SLA_BREACH_CRITICAL` / `SLA_BREACH_OVERFLOW` | a clock has run past its allowance | `sla_*_fired` |

Notes that are easy to get wrong:

- `SENSOR_STUCK` uses `==`, not `>=`, so a permanently frozen sensor produces
  one alert rather than one per reading afterwards.
- `SENSOR_STUCK` does not count readings at 100%, and **does** count them at 0%.
  The two look symmetric and are not. Fill is clamped at capacity, so a bin
  waiting for a truck reports exactly 100% every tick and identical readings
  there say nothing about the sensor. Nothing clamps a bin at empty - waste
  accumulates - so a bin repeating 0% has a sensor that stopped, which is what
  the `FROZEN` fault produces. Excluding zero as well suppressed the alert for
  every frozen bin in the fleet, because bins are seeded empty; an end-to-end
  run caught that and the unit tests did not.
- `CRITICAL_FILL` and `OVERFLOW` clear **only** on a collection. Clearing them
  whenever the level fell back under the threshold looked equivalent and was
  not - a bin wobbling around 80% re-alerted on every crossing and restarted
  its SLA clock each time, so a bin nobody collected stayed inside its SLA
  indefinitely.
- `SENSOR_FAULT` compares fault *names*, not "any fault at all". A single
  boolean meant a bin whose thermometer was already broken could lose its
  battery reading with nobody told. Recovery needs no branch: the remembered
  set is replaced by whatever the reading says.
- `COLLECTED` and `ANOMALY_JUMP` are mutually exclusive (`elif`) — a collection
  is a large change, and reporting it as an anomaly too would be noise.
- `FIRE_RISK` needs both halves. A hot empty bin is a warm day; a full cool bin
  is just a full bin. It is the only rule that re-fires while true, rate limited
  by `FIRE_RISK_REPEAT_MINUTES`.
- The two SLA breaches are separate alert types on purpose. Both clocks can
  come due on the same reading, and `bin_alerts` keys on
  `(bin_id, alert_type, fired_at)` - under one shared type the second row
  collided with the first and was silently dropped on insert.
- `fill_projection()` returns `(None, None)` from a single reading and a null
  `minutes_to_full` whenever the rate is not positive — a bin that just emptied
  has a negative rate, which would project to a nonsensical time.

## State

`STATE_SCHEMA` is a positional tuple. `read_state`/`write_state` zip it against
`STATE_FIELDS`, so a field added to the schema without a matching `EMPTY_STATE`
entry shifts every value one place. `test_state_survives_a_round_trip_through_storage`
guards that.

Changing `STATE_SCHEMA` makes existing checkpoints unreadable. Delete the
`bin_state` checkpoint after any change to it.

Roughly 200 bytes per bin, about a megabyte for a 5,000-bin city.

## Testing

`tests/test_bin_state.py` drives the rules with plain dictionaries and a
`FakeGroupState` — no Spark session, 47 tests in under a second. Every rule has
a positive case and a must-not-fire case.

`tests/test_streaming.py::test_the_stateful_operator_runs_under_spark` covers
only what the fast tests cannot: that the state schema round-trips through
Spark's state store and the emitted frames match `OUTPUT_SCHEMA`.
