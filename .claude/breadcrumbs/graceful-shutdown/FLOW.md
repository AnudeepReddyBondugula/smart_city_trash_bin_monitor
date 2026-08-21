# Graceful Shutdown

```text
SIGINT or SIGTERM
  → handle_shutdown sets stop_event
  → manager.stop() with a five-second timeout
      cancel and await every BinSimulator task
      clear the simulator registry
  → kafka_client.stop() with a five-second timeout
  → engine.dispose()
  → log shutdown complete
```

Windows uses `signal.signal`; other platforms use event-loop signal handlers.
