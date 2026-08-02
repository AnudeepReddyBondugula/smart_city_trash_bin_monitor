# ADR 002: Use PostgreSQL for bin metadata

- **Status:** Accepted (reflects current implementation)
- **Source note:** *Inferred from the codebase, not an original design record.*
  Reconstructed from code, config, and dependencies; code-tied points are cited.

---

## Context

The simulator needs durable storage for the **static identity and metadata** of
each bin — `bin_id`, `capacity`, `latitude`, `longitude`, `status`, timestamps
(`SmartBin`, `src/database.py:13-34`). This data is:

- Read once at startup to spawn simulators
  (`SimulationManager.initialize`, `simulation_manager.py:40-46`).
- Relational and well-structured (fixed columns, a natural primary key
  `bin_id`), with a `status` field used to filter which bins are active.

Crucially, **dynamic telemetry is not stored here** — it is in-memory and
streamed to Kafka (`Bin` docstring, `database.py:14-20`). So the datastore's job
is a modest, mostly-read metadata catalog, not a high-write time-series sink.

## Decision

Use **PostgreSQL 15** as the metadata store, accessed via SQLAlchemy's async
ORM over the `asyncpg` driver.

Evidence in code / config:

- `postgres:15-alpine` in `docker-compose.yml` (service `postgres`,
  `smartbin_postgres`).
- `DATABASE_URL = postgresql+asyncpg://...` computed in `config.py:19-27`;
  `create_async_engine(...)` in `database.py:38`.
- Declarative ORM model `SmartBin` mapping to table `smart_bins`
  (`database.py:13-34`).
- `asyncpg` + `SQLAlchemy` in `requirements.txt`.

## Consequences

**Positive**

- Strong relational schema with constraints (non-null columns, bounded
  `String(50)` PK, server-side timestamp defaults) — enforced by the DB and
  verified in `tests/test_database.py`.
- Async driver (`asyncpg`) fits the asyncio architecture
  (see [ADR 001](001-asyncio.md)) without blocking the event loop.
- Ubiquitous, well-understood, easy to run locally via the Alpine image and
  inspect with `psql`.
- Clean separation of concerns: durable *identity* in Postgres, ephemeral
  *state* in memory, durable *stream* in Kafka
  (see [architecture.md](../architecture.md#state-what-is-stateful-vs-stateless)).

**Negative / trade-offs**

- **Schema evolution is unmanaged.** There are no Alembic migrations despite
  `alembic` being a dependency; tables are created with
  `Base.metadata.create_all` via `create_tables.py`, which never alters existing
  tables (see [database.md](../database.md)). Column changes require a manual
  drop/recreate today. *(TODO: confirm with team whether Alembic adoption is
  intended.)*
- **Single-node, RF-agnostic.** The compose setup is one Postgres node with a
  local volume — no HA/replication. Fine for simulation, not production-grade.
- Operational cost of a full relational DB for what is currently a small,
  read-mostly catalog — justified by the relational fit and room to grow (the
  commented-out CRUD/FastAPI plans in `simulation_manager.py:67` imply future
  read/write use).

## Alternatives considered (inferred)

- **SQLite / a flat file:** simpler, but weaker concurrency story and a poor fit
  for the intended future networked CRUD layer.
- **A NoSQL/document store:** unnecessary — the data is naturally tabular with a
  clear primary key and a filterable `status`.

## Related

- [database.md](../database.md), [configuration.md](../configuration.md).
