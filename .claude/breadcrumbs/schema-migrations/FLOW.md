# Schema Migrations

Trigger: `alembic upgrade head` from `services/data-simulator/`.

End state: PostgreSQL matches the SQLAlchemy model at revision
`0002_add_zone`.

```text
alembic.ini
  → alembic/env.py loads settings.DATABASE_URL and Base.metadata
  → Alembic reads the database's alembic_version
  → 9b7a1e20a036 creates the original smart_bins schema on fresh databases
  → 0002_add_zone adds zone, backfills UNASSIGNED, and enforces NOT NULL
```

`9b7a1e20a036` is the checked-in root revision. A database carrying that marker
can upgrade directly through this graph.

Related flow: run migrations before [`database-seeding`](../database-seeding/FLOW.md).
