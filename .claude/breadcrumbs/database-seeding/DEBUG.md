# Database Seeding — Debug Guide

## Log locations

Seed errors are `print`ed, not logged through `logging_config` — check the
CLI's stdout/stderr directly.

## What to search for

| Symptom | Where to look | Search term |
|---------|---------------|-------------|
| Seed crashes with DB error | `src/seed.py:45-46` | `except Exception` block, printed message |
| Table doesn't exist error | run `create_tables.py` first — see `../table-creation/DEBUG.md` | `relation "smart_bins" does not exist` |
| `count > 500` silently no-ops | `src/seed.py:16-18` | safety guard returns early, no rows inserted |
| No telemetry after seeding | confirm `status == "ACTIVE"` on rows, see `../startup-and-telemetry/DEBUG.md` | — |

## Quick commands

```bash
cd services/data-simulator
set -a; source .env.local; set +a
PYTHONPATH=. python src/seed.py --count 50
PYTHONPATH=. python src/seed.py --count 50 --clear   # wipe then reseed
```

## Env vars that affect this flow

| Variable | Effect | Default |
|----------|--------|---------|
| `POSTGRES_*` | forms `DATABASE_URL` seed.py connects with | none (required) |

`NUMBER_OF_BINS` (`src/config.py:16`) is declared but **not** read by
`seed.py` — fleet size comes only from `--count`.

## Common breakpoints

- `src/seed.py:16` safety guard — confirm `count` isn't being silently rejected.
- `src/seed.py:31` row-generation loop — confirm `status="ACTIVE"` is set.
- `src/seed.py:45` `except Exception` — catches and prints any DB error.

## Relationship to other flows

Table must already exist — run `create_tables.py` first (`../table-creation/`).
Seeding does not create the schema.
