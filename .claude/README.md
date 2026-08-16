# `.claude/` — Onboarding & debugging index

This directory helps Claude Code sessions (and humans) onboard fast and debug the
**Smart City Trash Bin Monitor**. Every claim in these files is backed by a file
that was actually read; non-trivial claims cite `path:line`.

## What this repo actually is (today)

- **One implemented service:** `services/data-simulator/` — a Python 3.12 AsyncIO
  app that simulates a fleet of IoT trash bins and publishes telemetry to Kafka.
  Static bin metadata lives in PostgreSQL.
- **Infra:** `docker-compose.yml` at the repo root runs Postgres 15, Kafka
  (KRaft, single node), and the simulator.
- **Docs:** `docs/features/` contains a *planned* multi-service architecture
  (BinVault storage, Spark processing, APIs, dashboards). **Only the
  data-simulator exists in code so far** — treat the rest of `docs/features/` as
  design intent, not implemented behavior.
- **`binforge/` at repo root is untracked local scratch** (only env files +
  empty `__pycache__` dirs; `git ls-files binforge/` is empty). Ignore it — the
  real code is under `services/data-simulator/`. The README's "BinForge" name is
  the project's branding for the simulator.

## Start here

**Run the app (hybrid local — infra in Docker, app native):**
```bash
cd services/data-simulator
cp .env.local.example .env.local          # first time only
pip install -r requirements.txt
./scripts/run_local.sh
```
Then, first time, create schema + seed bins (the simulator emits nothing without
`ACTIVE` bins):
```bash
set -a; source .env.local; set +a
PYTHONPATH=. python src/create_tables.py
PYTHONPATH=. python src/seed.py --count 50
```
Full-Docker alternative: `docker compose up -d --build` then seed (see
`README.md` at repo root, lines 23-49). More detail: `commands/run-local.md`.

**Run tests (same as CI):**
```bash
cd services/data-simulator
PYTHONPATH=src pytest -v
```
More: `commands/run-tests.md`.

**Where things live:**
- Config / env vars: `services/data-simulator/src/config.py` +
  `.env.local.example` / `.env.docker`. The app does **not** load `.env` itself —
  run scripts / Docker do. See `skills/config/SKILL.md`.
- Logs: console (color) + rotating `services/data-simulator/logs/simulator.log`
  (`src/logging_config.py:41-46`). `SIGUSR1` toggles DEBUG at runtime
  (`src/logging_config.py:55`).
- Entry point: `services/data-simulator/src/main.py`.

## Skills (`.claude/skills/<name>/SKILL.md`, registry: `skills/index.md`)

| Skill | Load it when… |
| ----- | ------------- |
| `follow-breadcrumb` | Understanding an existing flow — reads the breadcrumb index before exploring code. |
| `breadcrumb-creator` | Documenting a flow that isn't covered yet — writes the FLOW/DETAILS/DEBUG triad. |
| `simulation-engine` | Working on `Bin`, `BinSimulator`, `SimulationManager`, the tick loop, or telemetry generation. |
| `database` | Working on the SQLAlchemy async engine, `SmartBin`/`smart_bins`, schema creation, or seeding. |
| `kafka` | Working on the `KafkaClient` producer, message format/keys, retries, or the broker config. |
| `config` | Working on `Settings`/`get_settings()`, env vars, `DATABASE_URL`, or `.env` files. |
| `testing` | Writing/running/debugging pytest tests, fixtures, mocks, or the docstring hooks. |
| `ci-cd` | Working on GitHub Actions, branch naming, or the PR governance/scope rules. |

## Commands (`.claude/commands/<name>.md`)

| Command | Does |
| ------- | ---- |
| `/run-tests` | Runs the pytest suite exactly as CI does (`PYTHONPATH=src pytest -v`). |
| `/run-local` | Starts Dockerized Postgres+Kafka and runs the simulator natively. |
| `/seed-db` | Creates the schema (`create_tables.py`) and seeds mock bins (`seed.py`). |
| `/debug-flow <flow>` | Walks a named flow hop-by-hop with `file:line`, via the breadcrumbs. |
| `/trace-error <err>` | Locates an error's source using this repo's logging patterns. |
| `/new-test <src path>` | Scaffolds a pytest test mirroring existing conventions. |

## Breadcrumbs (`.claude/breadcrumbs/<flow>/{FLOW,DETAILS,DEBUG}.md`)

Step-by-step, `file:line`-verified traces. Index + symptom lookup:
`breadcrumbs/_INDEX.md`.

| Flow | Folder |
| ---- | ------ |
| Startup → per-bin simulation → Kafka publish | `startup-and-telemetry/` |
| SIGINT/SIGTERM graceful shutdown & cleanup | `graceful-shutdown/` |
| Env → `get_settings()` → `DATABASE_URL` | `config-loading/` |
| `seed.py` CLI → `smart_bins` rows | `database-seeding/` |
| `create_tables.py` → `metadata.create_all` | `table-creation/` |
| PR → branch detect → feature-policy / pytest | `ci-pr-governance/` |

## Unverified / flagged for human confirmation

These were noted while writing the docs; a maintainer should confirm intent:

1. **`alembic` is a dependency without migrations.** Listed in
   `requirements.txt:2` but there is no `alembic.ini` or migrations dir in the
   tracked service — schema is created only by `create_tables.py`. Is Alembic
   intended to be adopted, or should it be dropped? (An untracked
   `binforge/alembic/` scratch dir exists but isn't part of the service.)
2. **`NUMBER_OF_BINS` is declared but unused at runtime.** `src/config.py:16`,
   tested in `tests/test_config.py`, but no runtime code reads it — fleet size
   comes from `ACTIVE` DB rows and `seed.py --count`. Intentional placeholder?
3. **`SimulationManager.add_bin`/`remove_bin`/`update_bin` are never called.**
   The `#!` comment at `src/simulator/simulation_manager.py:67` says they await a
   future FastAPI layer. Confirmed dead-until-then, not a bug.
4. **Governance only enforces `feature/` branches.** `devops`/`platform`/`bugfix`
   job calls are commented out in `pr-controller.yml:55-82`, so those branch
   types get scope-detected but not scope-enforced. Confirm this is intended.
5. **CI targets `develop`, not `master`.** Both PR workflows trigger only on PRs
   to `develop` (`pr-pytest.yml:5`, `pr-controller.yml:5`); the default branch is
   `master`. Confirm the intended integration branch.
6. **README seeding vs. schema creation.** `README.md` seeds directly and doesn't
   mention `create_tables.py`; on a truly empty DB you generally need
   `create_tables.py` first. Confirm whether something else creates the schema in
   the Docker path.
