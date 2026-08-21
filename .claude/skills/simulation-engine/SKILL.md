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
