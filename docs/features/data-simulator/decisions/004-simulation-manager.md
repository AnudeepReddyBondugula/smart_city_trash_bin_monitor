# ADR 004: Centralize simulator lifecycles in a SimulationManager

- **Status:** Accepted (reflects current implementation)
- **Source note:** *Inferred from the codebase, not an original design record.*
  Reconstructed from code, docstrings, and inline comments; code-tied points are
  cited.

---

## Context

The service runs many independent per-bin simulators concurrently
(see [ADR 001](001-asyncio.md)). Something has to:

- create one simulator per `ACTIVE` bin at startup,
- keep a registry so bins can be looked up, added, updated, and removed,
- and shut every simulator down cleanly on exit.

Left to `main()`, this orchestration would sprawl. A three-layer separation
already exists in the code:

- `Bin` (`models/bin.py`) — pure state + payload, no infrastructure.
- `BinSimulator` (`simulator/bin_simulator.py`) — the async loop for **one**
  bin.
- A coordinator for **all** bins — the gap this ADR fills.

## Decision

Introduce **`SimulationManager`** (`simulator/simulation_manager.py`) as the
single owner of all `BinSimulator` instances, backed by an in-memory
`dict[str, BinSimulator]` keyed by `bin_id`.

Evidence in code:

- `_simulators: dict[str, BinSimulator]` registry (`simulation_manager.py:32`).
- `initialize()` loads ACTIVE bins and starts a simulator per bin
  (`:34-65`); `main()` calls exactly this at startup (`main.py:29-30`).
- Lifecycle API: `add_bin`, `remove_bin`, `update_bin`, `stop`,
  `get_simulator`, `exists`, `simulators` (`:68-208`).
- `main()` delegates shutdown to `manager.stop()` (`main.py:54`), which stops
  every simulator and clears the registry (`:155-169`).
- The domain model is deliberately infrastructure-free, keeping the manager the
  only place that touches the DB for bin loading (`Bin` docstring,
  `models/bin.py:6-18`).

## Consequences

**Positive**

- **Single source of truth** for which bins are simulating — clean lookups
  (`get_simulator`/`exists`) and a clean teardown path.
- **Clear layering:** state (`Bin`) vs. per-bin loop (`BinSimulator`) vs.
  fleet coordination (`SimulationManager`). Each is unit-tested in isolation
  (`tests/models/`, `tests/simulator/`).
- **Extensible:** `add_bin`/`update_bin`/`remove_bin` give a ready CRUD surface
  for a future control plane.
- Keeps `main()` thin — orchestration lives in the manager, not the entrypoint.

**Negative / trade-offs**

- **In-memory, single-process registry.** State is not shared across processes,
  so it reinforces the single-instance constraint — a second instance would
  duplicate the whole fleet (see [operations.md](../operations.md#scaling)).
- **Startup-only population.** `initialize()` loads bins **once**; there is no
  reconciliation loop, so DB changes after boot are invisible until restart.
- **CRUD API is dormant.** `add_bin`/`update_bin`/`remove_bin` are implemented
  and tested but **not wired to any trigger** — the code marks this explicitly:
  "Add, update, delete - need to be implemented with Fast API in future
  involving DB interaction" (`simulation_manager.py:67`). Until that control
  plane exists, these methods are latent.
- **No persistence of runtime state.** Losing the process loses the registry and
  all in-memory bin state (rebuilt from the DB on next start) — acceptable given
  telemetry is streamed, not stored.

## Related

- [simulation-engine.md](../simulation-engine.md#the-registry-simulationmanager),
  [architecture.md](../architecture.md), [ADR 001](001-asyncio.md).
