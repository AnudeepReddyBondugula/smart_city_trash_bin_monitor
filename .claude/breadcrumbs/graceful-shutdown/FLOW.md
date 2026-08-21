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

Cleanup runs from a `finally`, so it happens whether startup succeeded or not.
It previously sat after the shutdown wait, which never runs if startup raises -
a failed start therefore leaked the Kafka producer and the process died
complaining about that instead of about the real problem.

Each step is separately guarded, so one failing step cannot skip the ones after
it. A normal shutdown ends with `Shutdown complete`, no warnings, exit code 0.
