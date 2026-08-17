---
name: database
description: >
  Load when working on persistence — the SQLAlchemy async engine, the SmartBin
  ORM model, schema/table creation, or seeding mock bins. Covers the async engine
  setup, the smart_bins table, and the seed/create-tables scripts. Trigger words:
  database, Postgres, SQLAlchemy, SmartBin, smart_bins, engine, session, seed,
  migration, asyncpg.
---

# Database Layer

PostgreSQL 15 is the persistence layer for **static bin metadata only**. Dynamic
telemetry is not written here (it goes to Kafka). Access is fully async via
SQLAlchemy 2.0 + `asyncpg`.

All paths below are relative to `services/data-simulator/`.

## Key files

- `src/database.py` — the single source of the engine, session factory, and ORM
  base:
  - `Base = declarative_base()` (`:10`).
  - `SmartBin` model (`:13`) → table `smart_bins` (`:22`).
  - `engine = create_async_engine(settings.DATABASE_URL, echo=False)` (`:38`).
  - `AsyncSessionLocal = async_sessionmaker(...)` (`:41`), `expire_on_commit=False`.
- `src/create_tables.py` — creates tables via `Base.metadata.create_all`
  (`:5-13`). Idempotent ("if not exists"). Run as a script (`:23`).
- `src/seed.py` — CLI to insert mock bins using `Faker` (`:15`). See the
  `seed-db` command and the `database-seeding` breadcrumb.
- `src/config.py:19-27` — `DATABASE_URL` is a computed field:
  `postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB`.

## The `smart_bins` schema (`src/database.py:13-34`)

| Column       | Type         | Notes                                             |
| ------------ | ------------ | ------------------------------------------------- |
| `bin_id`     | String(50)   | Primary key (`:24`)                               |
| `capacity`   | Float        | Not null (`:25`)                                  |
| `latitude`   | Float        | Not null (`:26`)                                  |
| `longitude`  | Float        | Not null (`:27`)                                  |
| `status`     | String(20)   | Not null, default `"ACTIVE"` (`:28`)              |
| `created_at` | DateTime     | Server default `now()` (`:29-31`)                 |
| `updated_at` | DateTime     | Server default `now()`, `onupdate=now()` (`:32`)  |

`status` matters: `SimulationManager.initialize()` only loads
`status == "ACTIVE"` rows (`src/simulator/simulation_manager.py:44`).

## How to extend safely

- **New column:** add a `mapped_column` to `SmartBin`, then re-run
  `create_tables.py`. Note there are **no migrations** wired up in this service
  (see pitfalls) — `create_all` only *adds new tables*, it does **not** alter an
  existing table. Changing an existing column requires a manual migration or a DB
  reset (`docker compose down -v`).
- **New query:** use `async with AsyncSessionLocal() as session:` and
  `await session.execute(select(...))`, mirroring
  `simulation_manager.py:40-46`.
- **New standalone DB script:** import `engine`/`AsyncSessionLocal` from
  `database`, wrap work in `asyncio.run(...)`, and always `await engine.dispose()`
  in a `finally` (pattern in `create_tables.py:16-20` and `seed.py:47-48`).

## Pitfalls (evidence in code)

- `alembic` is listed in `requirements.txt:2` but there is **no** `alembic.ini`
  or migrations directory in the tracked service — schema is created purely via
  `create_tables.py` (`Base.metadata.create_all`). Treat schema evolution as
  manual for now. (An untracked `binforge/alembic/` scratch dir exists at repo
  root but is not part of this service.)
- Importing `src/database.py` **instantiates the engine at import time** (`:38`),
  which calls `get_settings()` → requires all `POSTGRES_*` env vars to be set, or
  it raises. This is why tests set dummy env in `tests/conftest.py:6-12` before
  importing.
- `seed.py` refuses counts over 500 as a safety guard
  (`src/seed.py:16-18`).
- Host port for Postgres is **5433** (mapped to container 5432) in
  `docker-compose.yml:8-9` — but the app connects over the Docker network on
  `5432` via `.env.docker`. Only external tooling on the host uses 5433.
