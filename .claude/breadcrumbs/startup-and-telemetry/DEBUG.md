# Startup & Telemetry Generation — Debug Guide

## Log locations

| Layer | Log file | What's in it |
|-------|----------|---------------|
| data-simulator | console (color) + `logs/simulator.log` | startup, per-tick send, retries (`src/logging_config.py:37-49`) |

`SIGUSR1` toggles DEBUG at runtime (`src/logging_config.py:55,60`).

## What to search for

| Symptom | Where to look | Search term |
|---------|---------------|-------------|
| No telemetry published at all | `simulation_manager.py:62-65` log line | `"Started 0 simulator"` |
| Kafka unreachable at startup | `kafka_producer.py:33-44` | `"Kafka not ready yet"` |
| Per-tick send silently dropped | `kafka_producer.py:61-62` | `"Failed to send telemetry"` |
| Crash before `main()` starts | any consumer module import | pydantic `ValidationError` |

## Quick commands

```bash
# Confirm ACTIVE bins exist (root cause of "no telemetry")
cd services/data-simulator && PYTHONPATH=. python -c "
import asyncio
from database import AsyncSessionLocal
from models.smart_bin import SmartBin
from sqlalchemy import select
async def main():
    async with AsyncSessionLocal() as s:
        r = await s.execute(select(SmartBin).where(SmartBin.status == 'ACTIVE'))
        print(len(r.scalars().all()), 'active bins')
asyncio.run(main())
"

# Tail the log for send failures
tail -f services/data-simulator/logs/simulator.log | grep -i "kafka\|telemetry"
```

## Env vars that affect this flow

| Variable | Effect | Default |
|----------|--------|---------|
| `KAFKA_TOPIC` | topic telemetry is published to | — (required) |
| `SIMULATION_INTERVAL` | seconds between per-bin ticks | 5 |
| `NUMBER_OF_BINS` | declared but unused at runtime (see `../database-seeding/DEBUG.md`) | 100 |

## Common breakpoints

- `src/kafka_producer.py:15` `KafkaClient.start()` — Kafka connectivity issues.
- `src/simulator/simulation_manager.py:34` `initialize()` — no/zero bins loaded.
- `src/simulator/bin_simulator.py:118` `_run()` — per-tick simulation/publish logic.
