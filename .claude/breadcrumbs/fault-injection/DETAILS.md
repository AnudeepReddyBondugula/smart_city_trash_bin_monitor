# Fault Injection — Detailed Trace

Paths are relative to `services/data-simulator/`.

`FAULT_MODES` and `assign_fault_modes()` live in
`src/simulator/bin_simulator.py`. `Bin.fault_mode` is only a label — the bin
holds no logic, in keeping with the rest of that class.

## Assignment

`SimulationManager.initialize()` builds every `Bin` first, calls
`assign_fault_modes(bins)` on the whole list, then starts the simulators.
Fleet-wide rather than per bin, so both the share of faulty bins and the spread
of modes are known rather than left to chance. `int(len(bins) * rate)` bins are
marked, cycling `FAULT_MODES` by index.

## Two kinds of fault

**State-level**, in `_simulate()` — the bin really behaves this way:

- `FROZEN` returns before any state changes, so every reading repeats.
- `JUMP` sets the increase to `capacity * 0.4`. Large but still a level the bin
  could hold, so it passes validation and must be caught by comparing against
  the previous reading.
- `UNCOLLECTED` is excluded from the collection check, so it is never emptied.
- `HOT` replaces the ambient drift with
  `TEMP_NORMAL_MAX + (TEMP_FIRE_MAX - TEMP_NORMAL_MAX) * fill_pct / 100`.
  Scaling with fill is what makes fire risk reachable: the rule needs hot **and**
  nearly full together, so a bin pinned hot while empty would satisfy one half
  forever and the other never. It also needs no retuning when capacity or fill
  rate change.

**Reporting-level**, in `_next_payload()` — the bin is fine, the telemetry is
not:

- `SILENT` publishes normally for `SILENCE_AFTER_READINGS` readings, then stops.
  It must report at least once: dead-device detection arms a timer when a bin
  reports, so a bin never heard from is not detected as dead, it is simply never
  known about.
- `DUPLICATE` re-sends `_last_payload` **verbatim, original timestamp
  included**. Deduplication keys on `(bin_id, event_time)`, so a regenerated
  timestamp makes it a distinct event that passes straight through. It
  alternates, so the bin still makes progress.
- `SPIKE` calls `_corrupt()`, which copies the payload and alternates between
  `temperature = IMPOSSIBLE_TEMPERATURE` (150 °C) and
  `current_fill_level = capacity * 1.5`. The bin's own state is untouched, which
  is what a broken sensor actually is — and what keeps the bin worth tracking.

The two `SPIKE` corruptions are treated differently downstream, which is why it
alternates: an impossible temperature is nulled and the reading kept, while an
impossible fill level leaves nothing usable and is dead-lettered whole.

## Pacing interacts with faults

`SLA_BREACH_CRITICAL` / `SLA_BREACH_OVERFLOW` needs a bin uncollected past `SLA_CRITICAL_MINUTES`, so on the
default profile it is hours away. `LOW_BATTERY` needs the battery to drain to
20%. The demo profile in `.env.local.example` compresses both. See
`src/config.py` for what each knob does and why the default is what it is.

`COLLECTION_THRESHOLD_PCT` must stay **above** the consumer's critical threshold
of 80. Below it, bins are emptied on the way up and never once register as
critical — no collection list, no SLA clock, and no fire risk, since that rule
needs a nearly full bin.

## Testing

`tests/simulator/test_faults.py` asserts each mode produces the condition its
detector looks for, not merely that a flag was set — a fault that never produces
its condition and a detector that never fires are indistinguishable in a demo.
It also covers assignment: full coverage of modes at a high rate, the configured
share at the default, and nothing at zero.
