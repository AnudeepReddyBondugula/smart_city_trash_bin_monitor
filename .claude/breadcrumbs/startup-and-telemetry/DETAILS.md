# Startup and Telemetry Generation — Detailed Trace

Paths are relative to `services/data-simulator/`.

1. `src/main.py` configures logging and awaits `kafka_client.start()`.
2. `SimulationManager.initialize()` selects only `SmartBin.status == "ACTIVE"`.
3. Each database row becomes a `Bin` carrying ID, capacity, coordinates, and
   zone, then a `BinSimulator` task is started and registered by ID.
4. `BinSimulator._run()` calls `_simulate()`, publishes `Bin.to_payload()`, and
   sleeps for the configured interval.
5. `_simulate()` updates fill, battery, and temperature. Fill and battery use
   Faker; signed temperature drift uses `random.uniform` and stays within
   `20..35 °C`.
6. `Bin.to_payload()` emits capacity, dynamic readings, coordinates, zone, and
   an aware UTC timestamp.
7. `KafkaClient.send_telemetry()` JSON-serializes the payload and publishes it
   to `KAFKA_TOPIC` with the UTF-8 bin ID as key.

Per-message send failures are logged and dropped; the simulator loop continues.
The process then waits for a shutdown signal. See the shutdown breadcrumb for
cleanup order.
