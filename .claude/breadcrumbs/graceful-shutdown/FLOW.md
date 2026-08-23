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

## The stream processor

Different shape, same requirement. `src/main.py` cannot simply block:

```text
SIGINT or SIGTERM
  → handle_shutdown sets stop_requested
  → run() notices it between polls of awaitAnyTermination(timeout=5)
  → query.stop() for each active query, by name
  → session.stop()
  → log shutdown complete
```

The timeout is the whole point. Python runs a signal handler between bytecodes,
so while the main thread sits inside an unbounded py4j call the handler never
runs — SIGTERM was ignored and Docker sent SIGKILL after ten seconds, making
every ordinary stop report as exit 137. The service also carries
`stop_grace_period: 60s`, because four queries need longer than the default to
finish their micro-batches.

Nothing is lost either way: checkpoints exist for a kill, and every write is
idempotent. What is lost is the ability to tell a crash from a stop.
