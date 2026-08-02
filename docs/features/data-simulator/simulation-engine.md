# Simulation Engine

The simulation engine is the core loop that turns static bin metadata into a
continuous stream of realistic-looking telemetry. It is built from three
collaborating pieces:

- `Bin` (`src/models/bin.py`) — the in-memory state of one bin.
- `BinSimulator` (`src/simulator/bin_simulator.py`) — the per-bin async loop.
- `SimulationManager` (`src/simulator/simulation_manager.py`) — the registry
  that owns all simulators.

Randomness is provided by `Faker` (`from faker import Faker; fake = Faker()`).

---

## Inputs and outputs

**Input:** each `ACTIVE` row in the `smart_bins` table — `bin_id`, `capacity`,
`latitude`, `longitude` (`SimulationManager.initialize`, loaded once at
startup).

**Output:** one JSON telemetry message per bin per `SIMULATION_INTERVAL`
seconds, published to Kafka keyed by `bin_id`. The payload shape comes from
`Bin.to_payload()` (`src/models/bin.py:75-91`):

```json
{
  "bin_id": "BIN-1A2B3C4D-X",
  "capacity": 100.0,
  "current_fill_level": 42.37,
  "battery_level": 98.61,
  "latitude": 40.1234,
  "longitude": -73.9876,
  "timestamp": "2026-08-02T12:34:56.789012+00:00"
}
```

`current_fill_level` and `battery_level` are rounded to 2 decimals; `timestamp`
is UTC ISO-8601 (`datetime.now(timezone.utc).isoformat()`).

---

## The per-bin loop (`BinSimulator._run`)

`src/simulator/bin_simulator.py:118-147`:

```text
while self._running:
    self._simulate()                                  # mutate in-memory state
    await kafka_client.send_telemetry(                # publish current state
        self.bin.bin_id, self.bin.to_payload()
    )
    await asyncio.sleep(settings.SIMULATION_INTERVAL) # wait one tick
```

Each bin runs this loop inside its own `asyncio.Task`, created in `start()`
(`self._task = asyncio.create_task(self._run())`, line 74). Because all tasks
share one event loop, thousands of bins are multiplexed cooperatively — while
one bin is `await`-ing Kafka or `asyncio.sleep`, others make progress. See
[decisions/001-asyncio.md](decisions/001-asyncio.md).

### Lifecycle

| Method | Behavior |
| --- | --- |
| `start()` | Idempotent: if already running, logs a warning and returns; otherwise sets `_running = True` and schedules `_run()` as a task (`bin_simulator.py:60-79`). |
| `stop()` | Sets `_running = False`, cancels the task if not done, and awaits it — swallowing the expected `asyncio.CancelledError`. No-op with a warning if already stopped (`bin_simulator.py:81-116`). |

---

## The telemetry model (`BinSimulator._simulate`)

`src/simulator/bin_simulator.py:149-190`. Each tick updates two quantities:

**Fill level** — with a 5% chance the bin is "emptied" (collection event),
resetting `current_fill_level` to `0`; otherwise it increases by a random
amount and is clamped to `capacity`:

```python
if fake.boolean(chance_of_getting_true=5):
    self.bin.current_fill_level = 0
else:
    increase = fake.pyfloat(min_value=0.5, max_value=5.0)
    self.bin.current_fill_level = min(
        self.bin.capacity,
        self.bin.current_fill_level + increase,
    )
```

**Battery level** — monotonically drains by a small random amount each tick,
clamped at a floor of `0`:

```python
self.bin.battery_level = max(
    0,
    self.bin.battery_level - fake.pyfloat(min_value=0.01, max_value=0.1),
)
```

Summary of the model:

| Quantity | Start | Per-tick change | Bound |
| --- | --- | --- | --- |
| `current_fill_level` | `0.0` | +0.5..5.0, or reset to 0 (5% chance) | clamped to `[0, capacity]` |
| `battery_level` | `100.0` | −0.01..0.1 | clamped at `0` floor |

These behaviors are pinned by tests: normal increase/drain, empty event,
capacity clamp, and battery floor (`tests/simulator/test_bin_simulator.py:61-157`).

> Note: because `battery_level` only drains and is never recharged, a
> long-running bin will trend toward 0. There is no low-battery alert or
> replacement logic in the current code.

---

## The registry (`SimulationManager`)

`src/simulator/simulation_manager.py`. Holds `_simulators: dict[str,
BinSimulator]` and manages their lifecycles.

| Method | Sync/async | Behavior |
| --- | --- | --- |
| `initialize()` | async | Opens a session, `select(SmartBin).where(status == "ACTIVE")`, builds a `Bin` + `BinSimulator` per row, starts each, registers it (`:34-65`). |
| `add_bin(bin)` | sync | Creates + starts a simulator for a new bin; warns if already present (`:68-91`). |
| `remove_bin(bin_id)` | async | Pops and `await`s `stop()` on the simulator; warns if absent (`:93-115`). |
| `update_bin(bin_id, lat, lon)` | sync | Delegates to `Bin.update_location`; warns if absent (`:117-153`). |
| `stop()` | async | Stops every simulator and clears the registry (`:155-169`). |
| `get_simulator` / `exists` / `simulators` | sync | Read-only registry accessors (`:171-208`). |

> **Only `initialize()` is currently invoked at runtime** (from `main.py`). The
> `add_bin` / `update_bin` / `remove_bin` methods are implemented and unit-
> tested but not wired to any external trigger. The source marks this as future
> work: "Add, update, delete - need to be implemented with Fast API in future"
> (`simulation_manager.py:67`).

---

## Extension points

If you extend the engine, these are the natural seams (all verified in code):

1. **Telemetry model** — change the math in `BinSimulator._simulate()` (add
   sensors, seasonal patterns, correlated failures). Keep it synchronous and
   side-effect-free except for mutating `self.bin`.
2. **Payload shape** — extend `Bin.to_payload()` and add the corresponding
   in-memory attributes in `Bin.__init__`. Downstream consumers depend on this
   schema — see [kafka.md](kafka.md).
3. **Tick interval** — governed by `SIMULATION_INTERVAL` (config), read fresh
   from settings on each loop iteration.
4. **Dynamic fleet management** — implement the trigger (e.g. the mentioned
   FastAPI layer) that calls `SimulationManager.add_bin` / `update_bin` /
   `remove_bin`, and add periodic DB reconciliation to pick up new rows.
5. **Sink** — telemetry publishing is isolated behind
   `kafka_client.send_telemetry(...)`; swap the sink there without touching the
   loop.

---

## Related documents

- [architecture.md](architecture.md) — how the engine fits the whole process.
- [kafka.md](kafka.md) — the delivery path and message schema.
- [database.md](database.md) — the source of bin metadata.
