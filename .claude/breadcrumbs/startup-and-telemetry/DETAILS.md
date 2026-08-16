# Startup & Telemetry Generation — Detailed Trace

Paths relative to `services/data-simulator/`.

## 1. Entry point

**File**: `src/main.py`
**Function**: `main()` (invoked via `asyncio.run(main())` at `:71`)
**Called by**: process start
**Calls**: `setup_logging()`, `kafka_client.start()`, `SimulationManager.initialize()`

Key logic:
- Logging is configured once at import time (`src/main.py:12`, calls
  `setup_logging()` from `src/logging_config.py:12`).

---

## 2. Start Kafka

**File**: `src/kafka_producer.py`
**Function**: `KafkaClient.start()` (`:15`)
**Called by**: `src/main.py:23` `await kafka_client.start()`
**Calls**: builds an `AIOKafkaProducer`

Key logic:
- Retries up to 10x / 3s (`:16-41`).
- Raises after exhausting retries (`:42-44`) — crashes `main()`.

---

## 3. Create manager

**File**: `src/simulator/simulation_manager.py`
**Function**: `SimulationManager.__init__` (`:26`), `initialize()` (`:34-46`)
**Called by**: `src/main.py:29-30` `manager = SimulationManager()` then
`await manager.initialize()`

---

## 4. Load bins from DB

**File**: `src/simulator/simulation_manager.py:34-46`
**Function**: `SimulationManager.initialize()`
**Calls**: `AsyncSessionLocal()`, `select(SmartBin).where(SmartBin.status == "ACTIVE")` (`:43-44`)

Data layer touch: table `smart_bins` (`src/database.py:22`).

Data out: list of `SmartBin` rows with `status == "ACTIVE"`.

---

## 5. Spin up one simulator per bin

**File**: `src/simulator/simulation_manager.py:48-60`
**Calls**:
- builds a `Bin` (`src/models/bin.py:48`)
- wraps it in `BinSimulator` (`src/simulator/bin_simulator.py:46`)
- `simulator.start()` (`bin_simulator.py:60` — creates an `asyncio.Task` running `_run`)
- registers it in `_simulators` (`simulation_manager.py:60`)

Key logic:
- No `ACTIVE` bins → loop runs zero times, log line "Started 0 simulator(s)."
  (`simulation_manager.py:62-65`).

---

## 6. The per-bin loop

**File**: `src/simulator/bin_simulator.py`
**Function**: `_run()` (`:118`)
**Calls**: `_simulate()`, `Bin.to_payload()`, `kafka_client.send_telemetry()`

Key logic:
- `_simulate()` (`:132-149`) mutates fill (5% chance empty, else +0.5–5.0 capped
  at capacity) and drains battery 0.01–0.1.
- Builds payload via `Bin.to_payload()` (`src/models/bin.py:75`).
- Side effect / external call: `await kafka_client.send_telemetry(...)`
  (`bin_simulator.py:134-137` → `src/kafka_producer.py:51`) publishes to topic
  `settings.KAFKA_TOPIC`, key = `bin_id` (`kafka_producer.py:58-60`).
- `await asyncio.sleep(settings.SIMULATION_INTERVAL)` (`bin_simulator.py:140`,
  default 5s).
- Per-tick send failure is caught & logged inside `send_telemetry`
  (`kafka_producer.py:61-62`) — the loop keeps running, message is dropped.

---

## 7. Idle / exit

**File**: `src/main.py:50`
**Function**: `main()` blocks on `await stop_event.wait()` until a shutdown
signal arrives. See `../graceful-shutdown/DETAILS.md` for teardown.
