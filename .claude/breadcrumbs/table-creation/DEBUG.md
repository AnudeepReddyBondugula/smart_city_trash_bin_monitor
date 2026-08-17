# Table Creation (Schema Init) — Debug Guide

## Log locations

Confirmation/errors print to stdout/stderr of the CLI invocation, not
`logging_config`.

## What to search for

| Symptom | Where to look | Search term |
|---------|---------------|-------------|
| Connection/permission error | `create_tables.py:5-13` `engine.begin()` | aborts before the print confirmation |
| Column change not applied | `create_tables()` only creates missing tables | `create_all` does not alter existing columns |
| `relation "smart_bins" does not exist` on seed/query | run this flow first | see `../database-seeding/DEBUG.md` |

## Quick commands

```bash
cd services/data-simulator
set -a; source .env.local; set +a
PYTHONPATH=. python src/create_tables.py
```

## Env vars that affect this flow

| Variable | Effect | Default |
|----------|--------|---------|
| `POSTGRES_*` | forms `DATABASE_URL` the engine connects with | none (required) |

## Common breakpoints

- `src/create_tables.py:10` `engine.begin()` — connection failures.
- `src/create_tables.py:11` `run_sync(Base.metadata.create_all)` — schema mismatch.
