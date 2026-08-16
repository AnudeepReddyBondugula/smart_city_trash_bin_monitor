---
name: simulation-engine
description: >
  Load when working on the telemetry simulation logic — the Bin domain model,
  per-bin BinSimulator asyncio task, or the SimulationManager registry. Covers
  how bins are loaded, how fill/battery are simulated, and how the loop publishes
  to Kafka. Trigger words: simulator, simulation, BinSimulator, SimulationManager,
  Bin model, fill level, battery, telemetry loop.
---

# Simulation Engine

The simulation engine is the core of the `data-simulator` service. It models a
fleet of IoT smart trash bins in memory and, on a fixed interval, mutates each
bin's state and publishes telemetry to Kafka.

All paths below are relative to `services/data-simulator/`.

## What it does & why

Only **static** bin metadata (id, capacity, location, status) lives in
PostgreSQL. All **dynamic** state (fill level, battery level) is held in memory
by the running simulators — see the docstring at `src/database.py:14-20` and
`src/models/bin.py:7-18`. This keeps the DB write-light; telemetry goes to Kafka,
not back to Postgres.

## Key files

- `src/models/bin.py` — `Bin` domain model. Pure data + two helpers:
  `update_location()` (`src/models/bin.py:63`) and `to_payload()`
  (`src/models/bin.py:75`). Deliberately has **no** knowledge of Kafka, the DB,
  or the simulator (`src/models/bin.py:14-18`). `current_fill_level` starts at
  `0.0`, `battery_level` at `100.0` (`src/models/bin.py:60-61`).
- `src/simulator/bin_simulator.py` — `BinSimulator`. Owns exactly one `Bin` and
  runs one background `asyncio.Task`.
  - `start()` (`:60`) — idempotent; sets `_running` and creates the task.
  - `stop()` (`:81`) — cancels the task and awaits it, swallowing
    `CancelledError`.
  - `_run()` (`:118`) — the loop: `_simulate()` → `kafka_client.send_telemetry()`
    → `asyncio.sleep(settings.SIMULATION_INTERVAL)`.
  - `_simulate()` (`:149`) — the state model (see below).
- `src/simulator/simulation_manager.py` — `SimulationManager`. In-memory registry
  mapping `bin_id -> BinSimulator` (`:32`).
  - `initialize()` (`:34`) — loads bins from the DB and starts a simulator for
    each. **Only bins with `status == "ACTIVE"` are loaded** (`:44`).
  - `stop()` (`:155`) — stops every simulator and clears the registry.
  - `add_bin` / `remove_bin` / `update_bin` (`:68`, `:93`, `:117`) — registry
    mutators. See pitfall below — these are **not wired to anything yet**.

## The simulated state model (`src/simulator/bin_simulator.py:149`)

Each tick:
- 5% chance the bin is "emptied" → `current_fill_level = 0`
  (`:157`, `fake.boolean(chance_of_getting_true=5)`).
- Otherwise fill increases by a random `0.5–5.0`, capped at `capacity`
  (`:165-174`).
- Battery always drains by a random `0.01–0.1`, floored at `0`
  (`:176-183`).

The payload published is built by `Bin.to_payload()` (`src/models/bin.py:75`):
`bin_id, capacity, current_fill_level, battery_level, latitude, longitude,
timestamp` (UTC ISO-8601). Fill and battery are rounded to 2 dp.

## How to extend safely

- **Add a new simulated metric** (e.g. temperature): add the attribute to `Bin`
  (`src/models/bin.py:__init__`), include it in `to_payload()`, and mutate it in
  `BinSimulator._simulate()`. Keep `Bin` logic-free — the *how* of simulation
  belongs in `_simulate()`, not the model.
- **Change cadence:** it's driven by `settings.SIMULATION_INTERVAL`
  (`bin_simulator.py:141`), default `5` seconds (`src/config.py:17`). Don't
  hard-code it.
- **New lifecycle op on the fleet:** add a method to `SimulationManager` and
  mirror the existing logging + "already exists / not found" guard style
  (`simulation_manager.py:76-81`, `:103-108`).

## Pitfalls (evidence in code)

- `SimulationManager.add_bin` / `remove_bin` / `update_bin` exist but are
  **never called at runtime** — there is no API layer yet. The `#!` comment at
  `src/simulator/simulation_manager.py:67` states they "need to be implemented
  with Fast API in future involving DB interaction." Today the fleet is fixed at
  `initialize()` time from the DB snapshot.
- `_simulate()` is **synchronous** and runs inside the async loop; keep it cheap
  (no blocking I/O) or it will stall the event loop.
- If Kafka is down, telemetry is silently dropped (see the `kafka` skill), not
  retried — the simulation loop keeps running regardless.
- `NUMBER_OF_BINS` in `src/config.py:16` does **not** control the fleet size at
  runtime — the fleet is whatever `ACTIVE` bins exist in the DB. Seed count is
  controlled by `seed.py --count` instead. (Declared + tested, but unused by the
  engine.)
