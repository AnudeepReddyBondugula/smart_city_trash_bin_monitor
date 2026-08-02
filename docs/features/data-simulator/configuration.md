# Configuration

All runtime configuration is supplied through environment variables and loaded
by a single pydantic `Settings` model in `src/config.py`. This document lists
every real config key, its purpose, default, and where it is read in code.

---

## How config is loaded

`src/config.py` defines:

```python
class Settings(BaseSettings):
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_TOPIC: str

    NUMBER_OF_BINS: int = 100
    SIMULATION_INTERVAL: int = 5
```

- `Settings` extends `pydantic_settings.BaseSettings`, so each field is read
  from the environment by matching name (case-sensitive to the names above).
- Fields without a default (`POSTGRES_*`, `KAFKA_*`) are **required** — a
  missing one raises `pydantic.ValidationError` at construction
  (`tests/test_config.py:46-56`).
- Settings are accessed through `get_settings()`, which is wrapped in
  `functools.lru_cache`, so the environment is read once per process and the
  same `Settings` instance is reused (`src/config.py:33-35`).
- There is **no `.env` auto-loading configured in `config.py`** (no
  `model_config`/`env_file`). Env vars must already be present in the process
  environment. Docker Compose injects them via `env_file`; the local scripts
  `source` an env file before launching (see [deployment.md](deployment.md)).

---

## Config keys

| Key | Type | Required | Default | Purpose | Read in |
| --- | --- | --- | --- | --- | --- |
| `POSTGRES_HOST` | str | ✅ | — | DB host | `config.py` → `DATABASE_URL` |
| `POSTGRES_PORT` | int | ✅ | — | DB port | `config.py` → `DATABASE_URL` |
| `POSTGRES_DB` | str | ✅ | — | DB name | `config.py` → `DATABASE_URL` |
| `POSTGRES_USER` | str | ✅ | — | DB user | `config.py` → `DATABASE_URL` |
| `POSTGRES_PASSWORD` | str | ✅ | — | DB password | `config.py` → `DATABASE_URL` |
| `KAFKA_BOOTSTRAP_SERVERS` | str | ✅ | — | Kafka bootstrap address(es) | `kafka_producer.py:24, 29, 43` |
| `KAFKA_TOPIC` | str | ✅ | — | Telemetry topic name | `kafka_producer.py:59` |
| `NUMBER_OF_BINS` | int | ❌ | `100` | *Declared but currently unused at runtime* — see note below | only referenced in `tests/test_config.py` |
| `SIMULATION_INTERVAL` | int | ❌ | `5` | Seconds each `BinSimulator` sleeps between telemetry emissions | `bin_simulator.py:141` |

### Derived value: `DATABASE_URL`

`DATABASE_URL` is a pydantic `@computed_field`, not an env var. It is assembled
from the five `POSTGRES_*` values (`src/config.py:19-27`):

```text
postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB}
```

The `postgresql+asyncpg://` scheme selects the async `asyncpg` driver. It is
consumed by `create_async_engine(...)` in `src/database.py:38` and
`src/seed.py:21`. Behavior is pinned by `tests/test_config.py:20-27`.

> **`NUMBER_OF_BINS` is dead config.** It is defined and tested, but no runtime
> module reads it (`grep -rn NUMBER_OF_BINS src/` returns only `config.py`). The
> number of simulated bins is determined by how many `ACTIVE` rows exist in the
> `smart_bins` table (`SimulationManager.initialize`), and seeding uses
> `seed.py --count`, not this value. Treat `NUMBER_OF_BINS` as reserved/unused
> until a future component wires it in. *(TODO: confirm with team whether this
> was intended to cap simulators or seed count.)*

---

## Config files in the repo

| File | Tracked in git? | Used by | Notes |
| --- | --- | --- | --- |
| `services/data-simulator/.env.local.example` | ✅ yes | template only | Values for running natively (`POSTGRES_HOST=localhost`, `KAFKA_BOOTSTRAP_SERVERS=localhost:9092`). Copy to `.env.local`. |
| `services/data-simulator/.env.docker` | ❌ **git-ignored** | `docker-compose.yml` (`env_file`) | Values for the Docker network (`POSTGRES_HOST=postgres`, `KAFKA_BOOTSTRAP_SERVERS=kafka:29092`). Exists locally but is **not** committed — see warning below. |
| `services/data-simulator/.env.local` | ❌ git-ignored | `scripts/run_local.sh` (`source .env.local`) | Created by copying the example. |

The `.gitignore` rule (repo root) is `.env*` with the single exception
`!.env*.example`, so `.env.docker` and `.env.local` are both excluded from
version control.

> ### ⚠️ Discrepancy: `.env.docker` vs. the README quickstart
>
> `docker-compose.yml` reads `./services/data-simulator/.env.docker`
> (`docker-compose.yml`, the `postgres` and `data_simulator` `env_file`
> entries). But that file is **git-ignored**, so a fresh clone does not have it,
> and the root `README.md` step 1 instead tells you to create
> **`.env.docker.local`** — a filename Compose never references.
>
> **What actually works today:** Compose needs `.env.docker`. Either the file
> already exists in your working copy (it does in this repo's local checkout),
> or you must create it before `docker compose up`:
>
> ```bash
> cp services/data-simulator/.env.local.example services/data-simulator/.env.docker
> # then edit POSTGRES_HOST=postgres and KAFKA_BOOTSTRAP_SERVERS=kafka:29092
> ```
>
> This is flagged again in [troubleshooting.md](troubleshooting.md) and
> [deployment.md](deployment.md). *(TODO: confirm with team which filename is
> canonical and align README + compose + `.dockerignore`.)*

Note: `.dockerignore` excludes all `.env.*` **except** `.env.docker`
(`!.env.docker`), so `.env.docker` is intentionally included in the Docker
build context even though it is git-ignored.

---

## Test-time configuration

`tests/conftest.py:6-12` sets dummy values for all required keys at import time
so that `Settings()` can be constructed without a real environment:

```text
POSTGRES_HOST=localhost   POSTGRES_PORT=5432   POSTGRES_DB=test_db
POSTGRES_USER=test_user   POSTGRES_PASSWORD=test_password
KAFKA_BOOTSTRAP_SERVERS=localhost:9092   KAFKA_TOPIC=simulated_telemetry
```

CI additionally sets `PYTHONPATH=src` when running pytest
(`.github/workflows/pr-pytest.yml:44`). See [testing.md](testing.md).

---

## Related documents

- [database.md](database.md) — how `DATABASE_URL` is consumed.
- [kafka.md](kafka.md) — how `KAFKA_*` values are consumed.
- [deployment.md](deployment.md) — where each env file is injected.
