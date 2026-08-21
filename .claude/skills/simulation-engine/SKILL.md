---
name: simulation-engine
description: >
  Load for Bin, BinSimulator, SimulationManager, telemetry state, or the async
  publish loop.
---

# Simulation Engine

`SimulationManager` loads active database rows once at startup and owns one
`BinSimulator` per bin. Each simulator updates its in-memory `Bin`, publishes a
payload, and sleeps for `SIMULATION_INTERVAL` seconds.

## State

- Static PostgreSQL metadata: ID, capacity, coordinates, zone, and status.
- Dynamic in-memory telemetry: fill level, battery level, and temperature.

Initial dynamic values are fill `0.0`, battery `100.0`, and temperature
`25.0 °C`.

Each tick:

- Fill has a 5% chance to reset to zero; otherwise it grows by `0.5..5.0` and
  is capped at capacity.
- Battery falls by `0.01..0.1` and is floored at zero.
- Temperature drifts by `-0.5..+0.5 °C` and is clamped to `20..35 °C`.

`Bin.to_payload()` emits `bin_id`, capacity, fill, battery, temperature,
coordinates, zone, and a UTC ISO-8601 timestamp. Numeric simulated values are
rounded to two decimals.

## Boundaries

- Keep simulation math in `BinSimulator._simulate()`, not the domain model.
- Keep `_simulate()` synchronous and free of blocking I/O.
- Cadence comes from settings; do not hard-code it.
- Fleet mutations exist but are not wired to an API. Restart/recreate the
  simulator after database changes.
- Kafka send failures are logged and dropped; there is no retry queue.
- `NUMBER_OF_BINS` does not control runtime fleet size; active database rows do.

## Fault injection

A share of bins misbehave on purpose (`FAULT_INJECTION_RATE`), because the
detectors downstream otherwise have nothing to detect. `FAULT_MODES` and
`assign_fault_modes()` are in `src/simulator/bin_simulator.py`; assignment
cycles rather than drawing per bin, so a small fleet cannot end up missing a
mode entirely.

State-level faults are applied in `_simulate()` — the bin really behaves that
way. Reporting-level faults are applied in `_next_payload()` — the bin is fine,
the telemetry is not. A broken sensor belongs in the second group.

## Pacing

Fill is a percentage of capacity per tick, so bins of every size cross
percentage thresholds at the same pace. `COLLECTION_THRESHOLD_PCT` must stay
above the consumer's critical threshold of 80, or bins are emptied on the way up
and never once register as critical.

Defaults are paced for a real bin (~75 minutes to critical). `.env.local.example`
carries a demo profile that compresses it to minutes.

See the `fault-injection` breadcrumb for the full trace.
