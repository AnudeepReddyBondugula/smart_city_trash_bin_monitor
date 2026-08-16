# Table Creation (Schema Init) — Detailed Trace

Paths relative to `services/data-simulator/`.

## 1. Entry point

**File**: `src/create_tables.py:23`
`asyncio.run(main())`.

---

## 2. `main()`

**File**: `src/create_tables.py:16-20`
Calls `create_tables()` then, in `finally`, `await engine.dispose()`.

---

## 3. `create_tables()`

**File**: `src/create_tables.py:5-13`
Opens `async with engine.begin() as conn:` (`:10`) and runs
`await conn.run_sync(Base.metadata.create_all)` (`:11`).

Key logic:
- `engine` and `Base` are imported from `database` (`src/create_tables.py:1`);
  `Base.metadata` knows the `SmartBin` table (`src/database.py:13-34`).

---

## 4. Result

Creates all mapped tables **if they don't already exist** (idempotent);
prints confirmation (`:13`).

**Important limitation**: `create_all` only creates *missing* tables. It does
**not** alter columns on an existing table — there are no Alembic migrations
wired in (see `.claude/skills/database/SKILL.md`). Schema changes to an
existing table require a manual migration or a full reset
(`docker compose down -v`).
