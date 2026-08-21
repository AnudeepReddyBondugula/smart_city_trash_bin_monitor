# Database Seeding — Detailed Trace

Paths are relative to `services/data-simulator/`.

- `src/seed.py` defines Hyderabad center coordinates and per-zone offsets.
- `seed_db(count, clear)` rejects counts above 500 before opening a connection.
- The script creates its own async engine and session factory from
  `settings.DATABASE_URL`.
- `--clear` executes `delete(SmartBin)` and commits before inserting; it is
  destructive to existing bin rows.
- Each new `SmartBin` receives a UUID-derived ID, capacity `100.0`, one of five
  zones, coordinates inside that zone, and status `ACTIVE`.
- One final commit writes the batch and `finally` disposes the engine.

Schema setup is separate: run `alembic upgrade head` first. See
[`schema-migrations`](../schema-migrations/FLOW.md).
