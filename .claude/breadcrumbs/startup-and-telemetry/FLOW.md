# Startup and Telemetry Generation

Trigger: `python src/main.py` or the data-simulator container command.

```text
setup logging
  → start Kafka producer
  → create SimulationManager
  → SELECT active SmartBin rows
  → build Bin with capacity, coordinates, and zone
  → start one BinSimulator asyncio task per row
  → each tick updates fill, battery, and temperature
  → Bin.to_payload adds static metadata and UTC timestamp
  → publish JSON to KAFKA_TOPIC keyed by bin_id
  → sleep SIMULATION_INTERVAL
```

The manager loads the database once. Seeded or edited rows require a process
restart; after rebuilding a Docker image, use `docker compose up -d
--force-recreate data_simulator` rather than `restart`.

Shutdown is documented in [`graceful-shutdown`](../graceful-shutdown/FLOW.md).
