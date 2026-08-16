---
name: config
description: >
  Load when working on configuration, environment variables, or settings — the
  pydantic-settings Settings class, get_settings(), DATABASE_URL, or the various
  .env files and how they map to Docker vs local runs. Trigger words: config,
  settings, environment variable, env, pydantic, get_settings, DATABASE_URL,
  .env.docker, .env.local.
---

# Configuration

Config is centralized in one pydantic-settings model. Values come from
environment variables (loaded from `.env` files by the run scripts / Docker,
**not** by the app itself).

All paths below are relative to `services/data-simulator/` unless noted.

## Key files

- `src/config.py` — the `Settings` model (`:6`) and `get_settings()` (`:33`).
- `.env.local.example` — template for a native/local run; copy to `.env.local`.
- `.env.docker` — values used by Docker Compose (`docker-compose.yml:7`, `:49`).
- `../../docker-compose.yml` — injects `.env.docker` via `env_file`.

## Settings (`src/config.py:6-27`)

**Required (no default — missing → validation error):**
`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`.

**Optional (with defaults):**
`NUMBER_OF_BINS = 100` (`:16`), `SIMULATION_INTERVAL = 5` (`:17`).

**Computed:** `DATABASE_URL` (`:19-27`) — assembled as
`postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB`.

## The lazy `get_settings()` pattern (important)

`Settings()` is **not** instantiated at module import. Instead
`get_settings()` (`src/config.py:33`) is `@lru_cache`-wrapped and called on
demand. The inline comment at `src/config.py:30` explains why: a module-level
`settings = Settings()` "will crash when they are ran by test cases" because the
env vars aren't present. Consumers call `get_settings()`:
- `src/database.py:8`, `src/kafka_producer.py:8`,
  `src/simulator/bin_simulator.py:10`, `src/seed.py:11`.

Because of `@lru_cache`, settings are read **once per process** and cached — env
changes after first call are not picked up.

## Where env values come from at runtime

- **Docker:** `docker-compose.yml` loads `.env.docker` into each container
  (`:7`, `:49`). Postgres host is `postgres`, Kafka is `kafka:29092`.
- **Local hybrid run:** `scripts/run_local.sh:36-38` does `set -a; source
  .env.local; set +a` before launching. Postgres/Kafka point at `localhost`.
- **Tests:** `tests/conftest.py:6-12` sets dummy values directly in
  `os.environ` before any `src` import.

## How to extend safely

- **Add a setting:** add a typed field to `Settings`. If it must always be
  provided, give it no default (fail-fast); if it has a sane default, provide one.
  Then add it to `.env.local.example`, `.env.docker`, and — if tests import the
  consuming module — `tests/conftest.py`.
- Read settings via `get_settings()`, never by constructing `Settings()`
  directly (keeps the cache + test-safety intact).

## Pitfalls (evidence in code)

- The app does **not** call `load_dotenv()` — `.env` files are only loaded by the
  run scripts / Docker `env_file`. Running `python src/main.py` without sourcing
  an env file first will raise a pydantic validation error.
- `NUMBER_OF_BINS` (`:16`) is declared and covered by `tests/test_config.py` but
  is **not consumed** by any runtime logic — fleet size comes from ACTIVE DB rows,
  not this value. Don't assume changing it changes bin count.
- `.gitignore` ignores all `.env*` except `*.example`
  (`.gitignore` "environment files" block) — real env files are never committed.
