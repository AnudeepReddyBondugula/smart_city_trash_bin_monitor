# Graceful Shutdown — Detailed Trace

Paths relative to `services/data-simulator/`.

## 1. Signal registration

**File**: `src/main.py:35-48`
**Function**: `main()` (setup section)
**Calls**: `signal.signal` (Windows) or `loop.add_signal_handler` (else)

Key logic:
- After startup, `main()` gets the running loop and creates an `asyncio.Event`
  (`:35-36`).
- Defines `handle_shutdown` (`:38-40`) which schedules `stop_event.set()`
  thread-safely.
- Windows: registered via `signal.signal` for SIGINT/SIGTERM (`:42-45`).
- Otherwise: `loop.add_signal_handler` for SIGINT/SIGTERM (`:46-48`).

---

## 2. Block until signal

**File**: `src/main.py:50`
**Function**: `main()` — `await stop_event.wait()`

---

## 3. Signal received

**File**: `src/main.py:38`
**Function**: `handle_shutdown`

Key logic:
- Logs "Shutdown signal received" and sets the event via
  `loop.call_soon_threadsafe` (`:40`), unblocking step 2.

---

## 4. Stop all simulators

**File**: `src/main.py:53-56`
**Calls**: `await asyncio.wait_for(manager.stop(), timeout=5.0)` →
`src/simulator/simulation_manager.py:155`

Key logic:
- Iterates every registered simulator calling `await simulator.stop()`
  (`:164-165`) then clears the registry (`:167`).
- Each `BinSimulator.stop()` (`src/simulator/bin_simulator.py:81`) sets
  `_running = False` (`:100`), cancels the task (`:103`), and awaits it,
  swallowing `CancelledError` (`:105-111`).
- Bounded by `asyncio.wait_for(..., timeout=5.0)` — a hung simulator does not
  block shutdown forever.

---

## 5. Stop Kafka

**File**: `src/main.py:58-61`
**Calls**: `await asyncio.wait_for(kafka_client.stop(), timeout=5.0)` →
`src/kafka_producer.py:46`

---

## 6. Dispose DB engine

**File**: `src/main.py:63-66`
**Calls**: `await engine.dispose()` (`src/database.py:38`)

---

## 7. Exit

**File**: `src/main.py:68`
Logs "Shutdown complete"; `main()` returns and `asyncio.run` finishes.

## Error handling

Each cleanup step (4, 5, 6) is wrapped in its own try/except with a 5s
timeout; failures log a warning and do **not** abort the remaining steps
(`src/main.py:53-66` — three independent try/except blocks). Cancellation of
each per-bin task logs a warning (`src/simulator/bin_simulator.py:108-111`).
