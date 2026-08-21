# Graceful Shutdown — Detailed Trace

- `src/main.py` creates an `asyncio.Event` and registers SIGINT and SIGTERM
  handlers that schedule `stop_event.set()` safely.
- `main()` waits on the event without polling.
- `SimulationManager.stop()` awaits every simulator stop and clears the registry.
- `BinSimulator.stop()` marks the simulator stopped, cancels its unfinished
  task, awaits it, and handles the expected `CancelledError`.
- Manager and Kafka shutdown each have independent five-second bounds. A
  failure is logged and later cleanup still runs.
- The shared SQLAlchemy engine is disposed last.
