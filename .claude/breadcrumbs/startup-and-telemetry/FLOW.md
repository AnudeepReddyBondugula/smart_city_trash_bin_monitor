# Startup & Telemetry Generation

Trigger: `python src/main.py` (Docker CMD `Dockerfile:45`, or `scripts/run_local.sh:40`).
End state: one `asyncio.Task` per `ACTIVE` bin, each publishing telemetry to
Kafka on a timer, until a shutdown signal arrives.

Paths relative to `services/data-simulator/`.

## Flow

```
src/main.py :: main()  (asyncio.run at :71)
  → setup_logging()                            src/logging_config.py:12
  → await kafka_client.start()                 src/kafka_producer.py:15
      retries up to 10x/3s, raises on exhaustion
  → manager = SimulationManager()               src/simulator/simulation_manager.py:26
  → await manager.initialize()                  src/simulator/simulation_manager.py:34-46
      SELECT smart_bins WHERE status='ACTIVE'   src/database.py:22
      → for each row: build Bin                 src/models/bin.py:48
        wrap in BinSimulator                    src/simulator/bin_simulator.py:46
        simulator.start()                       src/simulator/bin_simulator.py:60
          → asyncio.Task running _run()
  → await stop_event.wait()                     src/main.py:50  (blocks until shutdown)

BinSimulator._run()                              src/simulator/bin_simulator.py:118
  loop:
    _simulate()                                  src/simulator/bin_simulator.py:132-149
      → mutates fill/battery
    Bin.to_payload()                             src/models/bin.py:75
    await kafka_client.send_telemetry(...)        src/kafka_producer.py:51
      → publish to settings.KAFKA_TOPIC, key=bin_id
    await asyncio.sleep(settings.SIMULATION_INTERVAL)   default 5s
```

## Sub-flows

Shutdown teardown from the `await stop_event.wait()` step is documented
separately — see `../graceful-shutdown/FLOW.md`.
