# Startup and Telemetry Generation — Detailed Trace

Paths are relative to `services/data-simulator/`.

1. `src/main.py` configures logging and awaits `kafka_client.start()`.
2. `SimulationManager.initialize()` selects only `SmartBin.status == "ACTIVE"`.
3. Each database row becomes a `Bin` carrying ID, capacity, coordinates, and
   zone. `assign_fault_modes()` marks a share of the fleet, then a
   `BinSimulator` task is started per bin and registered by ID.
4. `BinSimulator._run()` calls `_simulate()`, then `_next_payload()`, and
   publishes only if that returned something. It sleeps for the configured
   interval.
5. `_simulate()` delegates to `_simulate_fill()`, `_simulate_battery()` and
   `_simulate_temperature()`.
   - Fill rises by a percentage of capacity (`FILL_RATE_PCT_MIN/MAX`), so bins
     of every size cross percentage thresholds at the same pace. A bin is
     emptied only above `COLLECTION_THRESHOLD_PCT`, which sits above the
     consumer's critical threshold — below it, bins would be emptied on the way
     up and never register as critical.
   - Battery drains by `BATTERY_DRAIN_MIN/MAX` and never goes below zero.
   - Temperature drifts within `TEMP_NORMAL_MIN..TEMP_NORMAL_MAX`, unless the
     bin carries the `HOT` fault, which scales it up to `TEMP_FIRE_MAX`.
6. `Bin.to_payload()` emits capacity, dynamic readings, coordinates, zone, and
   an aware UTC timestamp. `Bin.fill_pct` is available but is not published;
   consumers derive it from level and capacity.
   `_next_payload()` then applies the reporting-level faults — suppressing the
   message, re-sending the previous one verbatim, or corrupting a field.
   The published shape is asserted against `contracts/telemetry-v1.json` by
   `tests/test_contract.py`.
7. `KafkaClient.send_telemetry()` JSON-serializes the payload and publishes it
   to `KAFKA_TOPIC` with the UTF-8 bin ID as key.

Per-message send failures are logged and dropped; the simulator loop continues.
The process then waits for a shutdown signal. See the shutdown breadcrumb for
cleanup order.
