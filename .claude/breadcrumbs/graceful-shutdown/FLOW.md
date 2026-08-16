# Graceful Shutdown

Trigger: SIGINT/SIGTERM delivered to the running process.
End state: all simulators stopped, Kafka producer stopped, DB engine
disposed, process exits cleanly.

Paths relative to `services/data-simulator/`.

## Flow

```
src/main.py :: main()
  register signal handlers                     src/main.py:35-48
    Windows: signal.signal(...)                 :42-45
    else:    loop.add_signal_handler(...)       :46-48
  await stop_event.wait()                       :50   (blocks)

  [signal received]
  handle_shutdown()                             :38-40
    → loop.call_soon_threadsafe(stop_event.set)
    → unblocks stop_event.wait()

  await manager.stop()  (timeout=5.0)            :53-56
    → simulation_manager.py:155 stop()
      for each simulator: simulator.stop()      :164-165
        BinSimulator.stop()                     src/simulator/bin_simulator.py:81
          _running = False                      :100
          cancel task, await, swallow CancelledError  :103-111
      clear registry                            :167

  await kafka_client.stop()  (timeout=5.0)       src/main.py:58-61
    → src/kafka_producer.py:46

  await engine.dispose()                        src/main.py:63-66
    → src/database.py:38

  exit: log "Shutdown complete"                 src/main.py:68
```
