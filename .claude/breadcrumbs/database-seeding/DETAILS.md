# Database Seeding — Detailed Trace

Paths relative to `services/data-simulator/`.

## 1. Entry point / arg parsing

**File**: `src/seed.py:51-59`
**Function**: `argparse` block
**Calls**: `asyncio.run(seed_db(args.count, args.clear))` (`:61`)

Key logic:
- Reads `--count` (default 50, `:53-55`) and `--clear` (flag, `:56-58`).

---

## 2. Safety guard

**File**: `src/seed.py:16-18`
Rejects `count > 500` and returns early.

---

## 3. Connect

**File**: `src/seed.py:21-22`
Builds its **own** engine + session factory from `settings.DATABASE_URL`
(`get_settings()` at `:11`). Note: creates a fresh engine rather than reusing
`database.engine`.

---

## 4. Optional clear

**File**: `src/seed.py:26-29`
If `--clear`, runs `delete(SmartBin)` and commits — wipes the table first.
Data layer touch: `smart_bins`.

---

## 5. Generate rows

**File**: `src/seed.py:31-42`
Loops `count` times, creating `SmartBin` rows with:
- `bin_id = f"BIN-{uuid4().hex[:8].upper()}-X"` (`:33`)
- `capacity = 100.0` (`:36`)
- random `latitude`/`longitude` via `Faker` (`:37-38`)
- `status = "ACTIVE"` (`:39`)

Each is `session.add(...)` (`:41`).

---

## 6. Commit

**File**: `src/seed.py:43-44`
One commit for all rows; logs count.

---

## 7. Cleanup

**File**: `src/seed.py:47-48`
`finally: await engine.dispose()`.
