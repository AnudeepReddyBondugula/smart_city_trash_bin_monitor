# `.claude/` — Onboarding and debugging index

This directory documents the implemented Smart City Trash Bin Monitor code.
Claims about future services in `docs/features/` are design intent, not runtime
behavior.

## Current implementation

- `services/data-simulator/` is a Python 3.12 AsyncIO application that loads
  static bin metadata from PostgreSQL and publishes simulated telemetry to
  Kafka. A share of bins misbehave on purpose so the detectors downstream have
  something to detect.
- `services/stream-processor/` is a Python **3.11** PySpark application that
  reads that topic and writes alerts, per-bin state and zone aggregates to
  PostgreSQL, plus a Parquet history. 3.11 rather than 3.12 because PySpark 3.5
  does not support 3.12.
- `contracts/telemetry-v1.json` is the payload agreement between them. Both
  sides assert against it, so a renamed field fails a test instead of silently
  reading as nulls downstream.
- `docker-compose.yml` runs PostgreSQL 15, Kafka in single-node KRaft mode, a
  one-shot topic creator, the simulator and the stream processor.
- Root `binforge/` content is ignored local scratch. The tracked implementation
  lives under `services/data-simulator/`.

## Start here

Full Docker:

```bash
test -f services/data-simulator/.env.docker || \
  cp services/data-simulator/.env.local.example services/data-simulator/.env.docker
docker compose up -d postgres kafka kafka_init
docker compose build data_simulator stream_processor
docker compose run --rm data_simulator alembic upgrade head
docker compose run --rm data_simulator python src/seed.py --count 200
docker compose up -d --force-recreate data_simulator stream_processor
```

`alembic upgrade head` names each revision it applies; only the two
`Context impl` lines means the database was already at head.

The Spark UI is at <http://localhost:4040> (batch job: 4041). Its Structured
Streaming tab is the fastest way to see whether the queries are consuming.

To verify the whole pipeline rather than just start it, use `/verify-pipeline`.

Hybrid local:

```bash
cd services/data-simulator
cp .env.local.example .env.local
pip install -r requirements-dev.txt
set -a; source .env.local; set +a
alembic upgrade head
PYTHONPATH=. python src/seed.py --count 50
./scripts/run_local.sh
```

Tests:

```bash
cd services/data-simulator   && pytest -q     # Python 3.12
cd services/stream-processor && pytest -q     # Python 3.11
```

## Skills

| Skill | Use it for |
|---|---|
| `follow-breadcrumb` | Trace an existing documented flow. |
| `breadcrumb-creator` | Add or repair a flow breadcrumb. |
| `simulation-engine` | Bin state, simulator tasks, manager, and telemetry. |
| `database` | SQLAlchemy, Alembic, `smart_bins`, and seeding. |
| `kafka` | Producer lifecycle, payloads, topics, and broker configuration. |
| `spark` | Structured Streaming, the alert rules, checkpoints, and rollups. |
| `config` | Settings, environment variables, and database URL construction. |
| `testing` | Pytest fixtures, mocks, and commands. |
| `ci-cd` | GitHub Actions and branch policy. |

## Commands

| Command | Purpose |
|---|---|
| `/run-tests` | Run the simulator test suite as CI does. |
| `/run-local` | Run Docker infrastructure with a native simulator process. |
| `/seed-db` | Upgrade the schema and seed bins. |
| `/debug-flow <flow>` | Follow a breadcrumb with verified source references. |
| `/trace-error <error>` | Locate an error using repository logging patterns. |
| `/new-test <path>` | Add a test matching existing conventions. |

## Breadcrumbs

- `startup-and-telemetry/`
- `graceful-shutdown/`
- `config-loading/`
- `schema-migrations/`
- `database-seeding/`
- `ci-pr-governance/`

See `breadcrumbs/_INDEX.md` for flow and symptom routing.

## Known intentional gaps

- `NUMBER_OF_BINS` is configured and tested but runtime fleet size comes from
  active database rows and `seed.py --count`.
- `SimulationManager.add_bin`, `remove_bin`, and `update_bin` are not connected
  to an API yet.
- PR scope enforcement currently runs only for `feature/` branches; the
  controller recognizes other prefixes but their policy jobs are commented out.
- CI targets pull requests to `develop`, while the GitHub default branch is
  `master`.
