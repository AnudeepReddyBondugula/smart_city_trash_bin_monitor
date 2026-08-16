# Configuration Loading

Trigger: any module importing `config` and calling `get_settings()`.
End state: a cached, validated `Settings` instance shared by the whole process.

Paths relative to `services/data-simulator/`.

## Flow

```
env vars placed in environment (app does NOT read .env itself)
  Docker: docker-compose.yml:7,49  env_file: .env.docker
  Local:  scripts/run_local.sh:36-38  set -a; source .env.local; set +a
  Tests:  tests/conftest.py:6-12  os.environ[...] set directly

first consumer imports config                  src/database.py:6
  settings = get_settings()                     src/database.py:8
  (other consumers: kafka_producer.py:8, simulator/bin_simulator.py:10, seed.py:11)

get_settings()                                  src/config.py:33-35
  @lru_cache → constructs Settings() once per process, caches thereafter

Settings() validation                           src/config.py:6-17
  required: POSTGRES_*, KAFKA_* → ValidationError if missing
  optional: NUMBER_OF_BINS=100, SIMULATION_INTERVAL=5 (defaults)

DATABASE_URL (computed)                         src/config.py:19-27
  assembled lazily from POSTGRES_* into postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB
  consumed at src/database.py:38, src/seed.py:21
```
