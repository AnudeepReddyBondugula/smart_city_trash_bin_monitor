# Graceful Shutdown — Debug Guide

## Log locations

| Layer | Log file | What's in it |
|-------|----------|---------------|
| data-simulator | console (color) + `logs/simulator.log` | shutdown signal, per-step warnings, "Shutdown complete" |

## What to search for

| Symptom | Where to look | Search term |
|---------|---------------|-------------|
| Process hangs on shutdown | `main.py:53-66` timeouts | should self-bound at 5s per step |
| Simulator task warning on cancel | `bin_simulator.py:108-111` | `"already stopped"` / cancellation warning |
| Cleanup step failed but process still exited | `main.py:53-66` | warning log per try/except block |

## Quick commands

```bash
# Send SIGTERM and watch shutdown sequence
kill -TERM <pid>
tail -f services/data-simulator/logs/simulator.log
```

## Env vars that affect this flow

None — shutdown timeouts (5.0s) are hardcoded in `src/main.py`.

## Common breakpoints

- `src/main.py:38` `handle_shutdown` — confirm the signal was actually received.
- `src/simulator/simulation_manager.py:155` `stop()` — confirm all simulators are iterated.
- `src/simulator/bin_simulator.py:81` `BinSimulator.stop()` — per-bin cancellation.
