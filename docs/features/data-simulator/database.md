# Database

The Data Simulator persists **only static bin metadata** in PostgreSQL. Dynamic
telemetry (fill level, battery) is never written back to the database — it lives
in memory and is emitted to Kafka. See
[architecture.md](architecture.md#state-what-is-stateful-vs-stateless).

- **Engine:** PostgreSQL 15 (`postgres:15-alpine`, `docker-compose.yml`).
- **Driver:** async `asyncpg` via SQLAlchemy's async engine
  (`postgresql+asyncpg://...`, see [configuration.md](configuration.md)).
- Rationale for PostgreSQL: [decisions/002-postgresql.md](decisions/002-postgresql.md).

---

## Schema: the `smart_bins` table

Defined by the `SmartBin` ORM model in `src/database.py:13-34`:

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `bin_id` | `String(50)` | **PRIMARY KEY** | Unique bin identifier (e.g. `BIN-1A2B3C4D-X`). |
| `capacity` | `Float` | `NOT NULL` | Maximum fill capacity. Seeded as `100.0`. |
| `latitude` | `Float` | `NOT NULL` | Geographic latitude. |
| `longitude` | `Float` | `NOT NULL` | Geographic longitude. |
| `status` | `String(20)` | `NOT NULL`, default `"ACTIVE"` | Only `ACTIVE` bins are simulated. |
| `created_at` | `DateTime` | `NOT NULL`, server default `now()` | Set by the DB on insert. |
| `updated_at` | `DateTime` | `NOT NULL`, server default `now()`, `onupdate=now()` | Refreshed by the DB on update. |

The table name (`"smart_bins"`), the bounded `String(50)` primary key, the
`"ACTIVE"` default, and the server-side timestamp defaults are all pinned by
`tests/test_database.py`.

> `status` has a **Python-side** default of `"ACTIVE"`
> (`default="ACTIVE"`), asserted in `tests/test_database.py:76-80`. The
> timestamp columns use **server-side** defaults (`server_default=func.now()`).

---

## How the schema is created — `create_tables.py` (no migrations)

`src/create_tables.py` creates all tables directly from ORM metadata:

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)   # CREATE TABLE IF NOT EXISTS ...
```

`Base.metadata.create_all` is idempotent — it only creates tables that do not
already exist and never alters existing ones. Run it as a one-off:

```bash
# inside the service directory, with env vars loaded and PYTHONPATH set
PYTHONPATH=src python src/create_tables.py
```

> ### Migrations approach: there are none (yet)
>
> `alembic` is listed in `requirements.txt`, and the alembic CLI is installed in
> the virtualenv, but **the service contains no `alembic/` directory,
> `alembic.ini`, or version scripts** (`find services -iname '*alembic*'`
> returns only virtualenv artifacts). The current schema-management strategy is
> the create-only `create_tables.py` above.
>
> Practical consequence: **schema changes to `SmartBin` are not migrated.**
> Adding/altering a column requires either dropping and recreating the table
> (e.g. `docker compose down -v`, then re-create + re-seed) or introducing
> Alembic. *(TODO: confirm with team whether Alembic is intended to be adopted;
> the dependency suggests it was planned.)*

Note also: nothing in `main.py`'s startup path calls `create_tables()`. The
schema must exist **before** the simulator boots, which is why the quickstart
seeds the DB in a separate step (see [operations.md](operations.md)).

---

## Seeding — `seed.py`

`src/seed.py` is a standalone CLI (`argparse`) that inserts mock bins using
`Faker`:

```bash
docker compose run --rm data_simulator python src/seed.py --count 50
# reset first, then seed:
docker compose run --rm data_simulator python src/seed.py --count 50 --clear
```

| Flag | Default | Effect |
| --- | --- | --- |
| `--count` | `50` | Number of bins to create. |
| `--clear` | off | `DELETE FROM smart_bins` before inserting (`delete(SmartBin)`). |

Each seeded row (`seed.py:32-41`):

- `bin_id = f"BIN-{uuid.uuid4().hex[:8].upper()}-X"`
- `capacity = 100.0`
- `latitude = float(fake.latitude())`, `longitude = float(fake.longitude())`
- `status = "ACTIVE"`

**Safety guard:** requests over 500 bins are rejected before any DB connection
is opened — "For safety, you cannot seed more than 500 bins at a time."
(`seed.py:16-18`, verified by `tests/test_seed.py:88-99`).

`seed.py` builds its **own** engine and session factory from `settings.DATABASE_URL`
rather than importing `database.engine`, and always `await engine.dispose()`s in
a `finally` block, even on error (`seed.py:21-48`).

> Note: `seed.py` inserts rows but assumes the `smart_bins` table already
> exists. It does **not** call `create_tables()`. If the table is missing,
> seeding fails — create tables first (see [operations.md](operations.md)).

---

## ORM / query patterns actually used

- **Async engine + session factory** (`src/database.py:37-43`):
  `create_async_engine(settings.DATABASE_URL, echo=False)` and
  `async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)`
  exported as `AsyncSessionLocal`.
- **Read (startup load)** — `SimulationManager.initialize`
  (`simulation_manager.py:40-46`):
  ```python
  async with AsyncSessionLocal() as session:
      result = await session.execute(
          select(SmartBin).where(SmartBin.status == "ACTIVE")
      )
      db_bins = result.scalars().all()
  ```
- **Write (seeding)** — `session.add(new_bin)` in a loop, then
  `await session.commit()` (`seed.py:41-43`).
- **Delete (clear)** — `await session.execute(delete(SmartBin))` then commit
  (`seed.py:26-29`).

`expire_on_commit=False` keeps ORM attributes accessible after commit without
triggering a refresh — relevant because the simulator copies bin fields into
in-memory `Bin` objects.

---

## Related documents

- [configuration.md](configuration.md) — `DATABASE_URL` construction.
- [simulation-engine.md](simulation-engine.md) — how loaded bins become simulators.
- [operations.md](operations.md) — create/seed/reset runbook.
- [decisions/002-postgresql.md](decisions/002-postgresql.md) — why PostgreSQL.
