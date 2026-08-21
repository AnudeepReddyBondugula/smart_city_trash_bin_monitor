# `.claude/` — Onboarding and debugging index

This directory documents the implemented Smart City Trash Bin Monitor code.
Claims about future services in `docs/features/` are design intent, not runtime
behavior.

## Current implementation

- `services/data-simulator/` is the only implemented service. It is a Python
  3.12 AsyncIO application that loads static bin metadata from PostgreSQL and
  publishes simulated telemetry to Kafka.
- `docker-compose.yml` runs PostgreSQL 15, Kafka in single-node KRaft mode, and
  the simulator.
- Root `binforge/` content is ignored local scratch. The tracked implementation
  lives under `services/data-simulator/`.

## Start here

Full Docker:

```bash
test -f services/data-simulator/.env.docker || \
  cp services/data-simulator/.env.local.example services/data-simulator/.env.docker
docker compose up -d postgres kafka
docker compose build data_simulator
docker compose run --rm data_simulator alembic upgrade head
docker compose run --rm data_simulator python src/seed.py --count 50
docker compose up -d --force-recreate data_simulator
```

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
cd services/data-simulator
pytest -q
```

## Skills

| Skill | Use it for |
|---|---|
| `follow-breadcrumb` | Trace an existing documented flow. |
| `breadcrumb-creator` | Add or repair a flow breadcrumb. |
| `simulation-engine` | Bin state, simulator tasks, manager, and telemetry. |
| `database` | SQLAlchemy, Alembic, `smart_bins`, and seeding. |
| `kafka` | Producer lifecycle, payloads, and broker configuration. |
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
