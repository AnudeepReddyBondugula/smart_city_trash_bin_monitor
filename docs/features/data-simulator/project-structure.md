# Project Structure

This document is an annotated map of the Data Simulator service and the
repository directories that support it. Every path below was verified against
the repository tree; unless noted otherwise, paths are relative to the repo
root.

---

## Repository top level

```text
smart_city_trash_bin_monitor/
├── docker-compose.yml            # Unified local stack: postgres + kafka + data_simulator
├── ruff.toml                     # Ruff linter config (line-length 125, E/F rules)
├── event.json                    # Sample GitHub PR event, used for local CI runs via `act`
├── README.md                     # Root project readme + quickstart
├── .github/workflows/            # CI pipelines (governance controller, feature policy, pytest)
├── docs/features/                # Per-feature documentation (this directory tree)
├── services/
│   └── data-simulator/           # The Data Simulator service (all runtime code)
└── binforge/                     # Legacy prototype — NOT git-tracked (see note below)
```

> **Note on `binforge/`:** `git ls-files binforge` returns nothing — the
> directory is not tracked by git. Only local, git-ignored `.env*` files remain
> on disk. It is the earlier prototype of this service; the maintained code now
> lives entirely under `services/data-simulator/`. Do not treat `binforge/` as
> part of the service. *(TODO: confirm with team whether `binforge/` should be
> deleted from working copies.)*

---

## The service: `services/data-simulator/`

```text
services/data-simulator/
├── Dockerfile                    # Multi-stage build: base → test → runtime
├── .dockerignore                 # Build-context excludes (keeps .env.docker in)
├── .env.docker                   # Runtime env for the Docker stack (git-IGNORED; local only)
├── .env.local.example            # Template env for running natively (git-tracked)
├── pytest.ini                    # pytest config (testpaths, pythonpath)
├── requirements.txt              # Runtime dependencies
├── requirements-dev.txt          # Dev/test dependencies (includes -r requirements.txt)
├── scripts/
│   ├── run_local.sh              # Start infra in Docker + run simulator natively (Linux/macOS)
│   └── run_local.ps1             # Same, for Windows PowerShell
├── src/                          # Application source (no __init__.py — flat module imports)
│   ├── main.py                   # Async entrypoint: orchestrates startup/shutdown
│   ├── config.py                 # Pydantic Settings; env-var loading + DATABASE_URL
│   ├── database.py               # Async SQLAlchemy engine, session factory, SmartBin ORM model
│   ├── create_tables.py          # One-off: creates tables via Base.metadata.create_all
│   ├── seed.py                   # CLI: seed mock bins into the DB (--count / --clear)
│   ├── kafka_producer.py         # AIOKafkaProducer wrapper (singleton `kafka_client`)
│   ├── logging_config.py         # Colored console + rotating file logging; SIGUSR1 toggle
│   ├── models/
│   │   └── bin.py                # `Bin` domain model (in-memory telemetry state)
│   └── simulator/
│       ├── __init__.py           # (empty)
│       ├── bin_simulator.py      # `BinSimulator`: per-bin async telemetry loop
│       └── simulation_manager.py # `SimulationManager`: registry of all BinSimulators
└── tests/                        # pytest suite (mirrors src/ layout)
    ├── conftest.py               # Dummy env vars + docstring-in-verbose-output hooks
    ├── test_config.py            # Settings / DATABASE_URL
    ├── test_database.py          # SmartBin ORM mapping
    ├── test_create_tables.py     # create_tables / main
    ├── test_seed.py              # seed_db behavior + safety guard
    ├── test_kafka_producer.py    # KafkaClient start/stop/send + retry logic
    ├── test_logging_config.py    # setup_logging + SIGUSR1 toggle
    ├── test_main.py              # main() startup/shutdown orchestration
    ├── models/
    │   └── test_bin.py           # Bin model
    └── simulator/
        ├── test_bin_simulator.py       # BinSimulator lifecycle + _simulate
        └── test_simulation_manager.py  # SimulationManager registry ops
```

### Module responsibilities (one line each)

| Module | Responsibility |
| --- | --- |
| `src/main.py` | Async entrypoint. Starts Kafka client + `SimulationManager`, installs SIGINT/SIGTERM handlers, awaits a stop event, then tears everything down with timeouts. |
| `src/config.py` | Defines the `Settings` pydantic model, reads env vars, exposes `get_settings()` (`lru_cache`) and a computed `DATABASE_URL`. |
| `src/database.py` | Declares the async engine, `AsyncSessionLocal` session factory, and the `SmartBin` SQLAlchemy ORM model (persisted bin metadata). |
| `src/create_tables.py` | Developer helper that creates all tables from ORM metadata. No migrations. |
| `src/seed.py` | Standalone CLI that inserts mock `SmartBin` rows using `Faker`. Caps at 500 rows. |
| `src/kafka_producer.py` | `KafkaClient` wrapping `AIOKafkaProducer` with connection retries; module-level singleton `kafka_client`. |
| `src/logging_config.py` | Configures root logging (color console + rotating file), suppresses noisy libs, registers a SIGUSR1 handler to toggle DEBUG/INFO at runtime. |
| `src/models/bin.py` | `Bin` — the in-memory domain object holding a bin's live fill/battery state and building the telemetry payload. Infrastructure-agnostic. |
| `src/simulator/bin_simulator.py` | `BinSimulator` — owns one `Bin`, runs the periodic simulate-and-publish asyncio task. |
| `src/simulator/simulation_manager.py` | `SimulationManager` — in-memory `dict[bin_id, BinSimulator]`; loads ACTIVE bins from the DB and manages simulator lifecycles. |

---

## Supporting directories

| Path | Purpose |
| --- | --- |
| `.github/workflows/` | CI: `pr-controller.yml` (governance router), `feature-policy.yml` (reusable scope check), `pr-pytest.yml` (test runner). See [ci-cd.md](ci-cd.md). |
| `docs/features/` | Feature docs. `docs/features/README.md` is the docs index; `docs/features/data-simulator/` is this service's docs. |
| `scripts/` (in service) | Local dev launchers that bring up infra in Docker and run the simulator on the host. |

---

## Related documents

- [architecture.md](architecture.md) — how these modules interact at runtime.
- [configuration.md](configuration.md) — the env vars each module reads.
- [contributing.md](contributing.md) — conventions and where to add new code.
