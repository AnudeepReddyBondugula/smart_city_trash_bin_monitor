# Configuration Loading — Detailed Trace

Paths relative to `services/data-simulator/`.

## 1. Env vars placed in the environment

The app does NOT read `.env` files itself:
- Docker: `docker-compose.yml:7`/`:49` load `.env.docker` via `env_file`.
- Local: `scripts/run_local.sh:36-38` `set -a; source .env.local; set +a`.
- Tests: `tests/conftest.py:6-12` set `os.environ[...]` directly.

---

## 2. First consumer imports config

**File**: `src/database.py:6`
`from config import get_settings`, then `settings = get_settings()` (`:8`).
Other entry consumers: `src/kafka_producer.py:8`,
`src/simulator/bin_simulator.py:10`, `src/seed.py:11`.

---

## 3. `get_settings()`

**File**: `src/config.py:33-35`
**Function**: `get_settings()`, decorated `@lru_cache`

Key logic:
- Constructs `Settings()` once per process, returns the cached instance
  thereafter. Because of `@lru_cache`, changing env vars after the first call
  has **no effect** in that process.

---

## 4. `Settings()` validation

**File**: `src/config.py:6-17`

Key logic:
- pydantic-settings reads required fields from the environment (`POSTGRES_*`,
  `KAFKA_*`); missing → `ValidationError`.
- Optional fields default (`NUMBER_OF_BINS=100`, `SIMULATION_INTERVAL=5`).

---

## 5. Computed `DATABASE_URL`

**File**: `src/config.py:19-27`

Key logic:
- Assembled lazily from the `POSTGRES_*` fields into
  `postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB`.
- Consumed at `src/database.py:38` and `src/seed.py:21`.
- The deliberate lazy pattern (comment at `src/config.py:30`) exists precisely
  so importing modules under pytest doesn't crash before `conftest.py` sets
  dummy env.
