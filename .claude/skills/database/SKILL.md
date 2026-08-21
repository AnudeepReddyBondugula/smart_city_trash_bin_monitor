---
name: database
description: >
  Load for PostgreSQL, SQLAlchemy, SmartBin, Alembic migrations, async sessions,
  or database seeding.
---

# Database Layer

PostgreSQL 15 stores static bin metadata. Dynamic fill, battery, and temperature
state is kept in memory and published to Kafka.

Paths are relative to `services/data-simulator/`.

## Sources of truth

- `src/database.py`: async engine, session factory, `Base`, and `SmartBin`.
- `alembic/env.py`: async Alembic environment using `settings.DATABASE_URL` and
  `Base.metadata`.
- `alembic/versions/`: ordered schema history.
- `src/seed.py`: mock fleet creation.

## Current schema

| Column | Type | Constraint |
|---|---|---|
| `bin_id` | `String(50)` | Primary key |
| `capacity` | `Float` | Not null |
| `latitude` | `Float` | Not null |
| `longitude` | `Float` | Not null |
| `zone` | `String(20)` | Not null |
| `status` | `String(20)` | Not null; Python default `ACTIVE` |
| `created_at` | `DateTime` | Not null; server default `now()` |
| `updated_at` | `DateTime` | Not null; server default `now()` |

Only `ACTIVE` rows are loaded by `SimulationManager.initialize()`.

## Schema changes

1. Update `SmartBin`.
2. Generate an Alembic revision: `alembic revision --autogenerate -m "..."`.
3. Review generated upgrade and downgrade operations.
4. Run `alembic upgrade head`, then `alembic check`.
5. Test fresh upgrade and upgrade from the previous revision on disposable
   PostgreSQL data.

The baseline revision is intentionally `9b7a1e20a036` for compatibility with
databases created by the former `binforge/` layout. Do not replace it with a new
root revision.

Docker source is copied into the image, so rebuild before executing newly added
migrations. Never stamp a database until its schema is verified to match the
target revision.

## Operational details

- Importing `database.py` creates the engine and requires all settings.
- Tests provide dummy environment variables in `tests/conftest.py`.
- PostgreSQL is exposed on host port 5433 and reached inside Compose on 5432.
- `seed.py` refuses counts over 500 and always disposes its private engine.
