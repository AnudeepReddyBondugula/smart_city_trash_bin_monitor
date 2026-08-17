# Configuration Loading — Debug Guide

## Log locations

Config errors surface as an uncaught exception at import time, not a log
line — check whichever runner's stdout/stderr invoked the process.

## What to search for

| Symptom | Where to look | Search term |
|---------|---------------|-------------|
| Crash before `main()` starts | traceback top frame | pydantic `ValidationError` |
| Env var change has no effect | `src/config.py:33-35` | `@lru_cache` — settings cached after first call |
| Wrong `DATABASE_URL` | `src/config.py:19-27` | check `POSTGRES_*` values it was assembled from |

## Quick commands

```bash
# Print resolved settings for the current env
cd services/data-simulator
set -a; source .env.local; set +a
PYTHONPATH=. python -c "from config import get_settings; print(get_settings())"
```

## Env vars that affect this flow

| Variable | Effect | Default |
|----------|--------|---------|
| `POSTGRES_*` (USER/PASSWORD/HOST/PORT/DB) | required, assembled into `DATABASE_URL` | none (`ValidationError` if missing) |
| `KAFKA_*` | required | none (`ValidationError` if missing) |
| `NUMBER_OF_BINS` | optional, declared but unused at runtime | 100 |
| `SIMULATION_INTERVAL` | optional, seconds between ticks | 5 |

## Common breakpoints

- `src/config.py:33` `get_settings()` — first call per process, where
  `ValidationError` would raise.
- `src/config.py:19` `DATABASE_URL` property — wrong connection string.
