# Deployment

The Data Simulator is deployed with **Docker Compose**. There are no Kubernetes
manifests, Helm charts, or cloud/IaC files in the repository — the only
deployment artifacts are `docker-compose.yml` (repo root) and the service
`Dockerfile`. This document describes what those actually define.

> There is no automated deploy in CI. The GitHub Actions workflows run tests and
> policy checks only — they do **not** build or push images or deploy anywhere.
> See [ci-cd.md](ci-cd.md).

---

## The Docker stack (`docker-compose.yml`)

Three services plus one named volume:

| Service | Image / build | Container name | Ports (host:container) | Notes |
| --- | --- | --- | --- | --- |
| `postgres` | `postgres:15-alpine` | `smartbin_postgres` | `5433:5432` | `env_file: ./services/data-simulator/.env.docker`; healthcheck via `pg_isready`; data in named volume `postgres_data`. |
| `kafka` | `confluentinc/cp-kafka:7.4.1` | `smartbin_kafka` | `9092:9092`, `9093:9093` | KRaft mode (no ZooKeeper). Listeners: `kafka:29092` (internal), `localhost:9092` (host). See [kafka.md](kafka.md). |
| `data_simulator` | build `./services/data-simulator/Dockerfile` | `data_simulator` | none | `env_file: ./services/data-simulator/.env.docker`; `depends_on: postgres (service_healthy)`. |

Key details verified in `docker-compose.yml`:

- **Postgres is published on host port `5433`** (mapped to container `5432`) to
  avoid clashing with a local Postgres. Inside the compose network other
  services still reach it as `postgres:5432`.
- **`data_simulator` waits for Postgres health** (`condition:
  service_healthy`), but has **no `depends_on` for `kafka`**. The producer's own
  10× retry loop covers the case where Kafka is still coming up
  (see [kafka.md](kafka.md)).
- The Postgres healthcheck uses `POSTGRES_USER`/`POSTGRES_DB` (defaulting to
  `postgres` / `smart_city`) supplied from `.env.docker`.

---

## The image (`services/data-simulator/Dockerfile`)

Multi-stage build on `python:3.12-slim`:

```text
base     → installs gcc; sets PYTHONUNBUFFERED, PYTHONDONTWRITEBYTECODE, PYTHONPATH=/app
  ├─ test    → installs requirements-dev.txt, copies source, RUN pytest
  └─ runtime → installs requirements.txt, copies source, CMD ["python", "src/main.py"]
```

- `PYTHONPATH=/app` is what makes the flat imports in `src/` (e.g.
  `from config import get_settings`) resolve when the process runs
  `python src/main.py`.
- The `test` stage runs `pytest` **at build time** — building that target fails
  the build if tests fail. Compose builds the default (last) stage, which is
  `runtime`; to build/run the test stage explicitly:
  `docker build --target test services/data-simulator`.
- `.dockerignore` trims the build context (`.venv/`, `__pycache__/`, `logs/`,
  `.git`, most `.env.*`) but **keeps `.env.docker`** (`!.env.docker`).

---

## Environments

There are two documented run modes; there is **no separate staging/production
environment defined in the repo.**

### 1. Full Docker stack (everything in containers)

Uses `.env.docker` (`POSTGRES_HOST=postgres`, `KAFKA_BOOTSTRAP_SERVERS=kafka:29092`).
This is the mode `docker-compose.yml` is wired for.

### 2. Hybrid local (infra in Docker, simulator on host)

`scripts/run_local.sh` (Linux/macOS) and `scripts/run_local.ps1` (Windows):

- Bring up **only** `postgres` and `kafka`:
  `docker compose -f docker-compose.yml up -d postgres kafka`.
- Wait for Postgres via `docker exec smartbin_postgres pg_isready`.
- `source .env.local` (host values: `localhost:9092`, `localhost:5432` — note
  the script's `.env.local` still uses `5432`, whereas Docker publishes Postgres
  on **5433**; see the warning in [troubleshooting.md](troubleshooting.md)).
- Run `PYTHONPATH=. python src/main.py` on the host.

This mode is for debugging in an IDE without rebuilding images.

---

## Rollout / operational lifecycle

There is no blue-green, canary, or orchestrated rollout — deployment is
Compose lifecycle commands. Verified from the root `README.md` and
`docker-compose.yml`:

```bash
# 0. (First time) ensure the env file Compose reads actually exists — see warning below
# 1. Build + start the stack
docker compose up -d --build

# 2. Create schema + seed data (one-off container). The simulator emits nothing
#    until the DB has ACTIVE bins.
docker compose run --rm data_simulator python src/seed.py --count 50

# 3. Restart the simulator to pick up the seeded bins (it loads bins once, at boot)
docker compose restart data_simulator

# Stop
docker compose down

# Hard reset (also drops the postgres_data volume — wipes all bins)
docker compose down -v
```

Step 3 is required because `SimulationManager.initialize()` loads bins **once**
at startup; seeding after boot has no effect until a restart
(see [simulation-engine.md](simulation-engine.md)). Day-2 operations —
monitoring, scaling, restarts — are in [operations.md](operations.md).

> ### ⚠️ Required env file before first `up`
>
> `docker-compose.yml` reads `./services/data-simulator/.env.docker`, but that
> file is **git-ignored** and the README instead references `.env.docker.local`
> (which Compose does not use). On a fresh clone, create `.env.docker` first or
> `docker compose up` fails on the missing `env_file`:
>
> ```bash
> cp services/data-simulator/.env.local.example services/data-simulator/.env.docker
> # set POSTGRES_HOST=postgres and KAFKA_BOOTSTRAP_SERVERS=kafka:29092
> ```
>
> Full analysis of this discrepancy is in
> [configuration.md](configuration.md) and
> [troubleshooting.md](troubleshooting.md). *(TODO: confirm with team.)*

---

## Related documents

- [configuration.md](configuration.md) — env vars and env files.
- [operations.md](operations.md) — running, monitoring, scaling, resetting.
- [kafka.md](kafka.md) — broker/listener configuration.
- [ci-cd.md](ci-cd.md) — what CI does (and does not) do for deployment.
