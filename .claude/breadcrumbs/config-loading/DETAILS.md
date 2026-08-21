# Configuration Loading — Detailed Trace

- `src/config.py` defines required PostgreSQL and Kafka values plus default
  `NUMBER_OF_BINS=100` and `SIMULATION_INTERVAL=5`.
- `Settings.DATABASE_URL` returns
  `postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB`.
- `get_settings()` is cached with `lru_cache`, so environment changes made after
  its first call do not affect that process.
- `src/database.py` creates the async engine at import time.
- `alembic/env.py` uses the same settings and ORM metadata.
- `docker-compose.yml` loads `.env.docker` for PostgreSQL and the simulator.
- `scripts/run_local.sh` and `.ps1` load `.env.local` before starting Python.

`NUMBER_OF_BINS` is currently unused by runtime fleet creation; active database
rows determine the number of simulators.
