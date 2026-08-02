# Testing

The service ships a `pytest` suite covering config, database model, table
creation, seeding, the Kafka client, logging, the entrypoint, and the
simulation engine. Tests are **fully mocked** — they require no running
Postgres or Kafka.

---

## Layout

`tests/` mirrors `src/`:

```text
tests/
├── conftest.py                       # dummy env vars + verbose-output docstring hooks
├── test_config.py                    # Settings / DATABASE_URL / validation
├── test_database.py                  # SmartBin ORM mapping (no DB — SQLAlchemy inspection)
├── test_create_tables.py             # create_tables() / main() with mocked engine
├── test_seed.py                      # seed_db(): create/clear/guard/dispose
├── test_kafka_producer.py            # KafkaClient: start/retry/send/stop
├── test_logging_config.py            # setup_logging + SIGUSR1 toggle
├── test_main.py                      # main() startup/shutdown orchestration
├── models/
│   └── test_bin.py                   # Bin model: init / update_location / to_payload
└── simulator/
    ├── test_bin_simulator.py         # BinSimulator lifecycle + _simulate math
    └── test_simulation_manager.py    # SimulationManager registry operations
```

---

## Configuration — `pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
pythonpath = . src
```

`pythonpath = . src` puts both the service root and `src/` on `sys.path`, which
is why tests can import both `from src.models.bin import Bin` **and**
`from database import SmartBin` (the same style `src/` modules use internally).

> **Import-identity caveat (documented in the code):** because `src/` has no
> `__init__.py`, `database.SmartBin` and `src.database.SmartBin` are two
> distinct class objects. `tests/test_seed.py:6-10` deliberately imports
> `SmartBin` the same way `seed.py` does (`from database import ...`) so
> `isinstance` / call-arg assertions match. Keep this in mind when adding tests
> that assert on classes crossing that boundary.

### `conftest.py`

Two responsibilities (`tests/conftest.py`):

1. **Dummy env vars** set at import time so `Settings()` constructs without a
   real environment (`POSTGRES_*`, `KAFKA_*` — see
   [configuration.md](configuration.md)).
2. **Verbose docstring reporting hooks** — `pytest_runtest_makereport` +
   `pytest_report_teststatus` append each test's first docstring line to the
   `-v` outcome (e.g. `PASSED  Test the successful startup...`). This is why the
   tests carry descriptive docstrings.

---

## Async testing

Async tests use `pytest-asyncio` via the `@pytest.mark.asyncio` decorator
(applied per-test, e.g. `test_kafka_producer.py`, `test_main.py`,
`test_simulation_manager.py`). External I/O is replaced with
`unittest.mock` (`AsyncMock` / `MagicMock` / `patch`):

- Kafka: `AIOKafkaProducer` is patched; retry/sleep behavior is asserted by
  patching `src.kafka_producer.asyncio.sleep`.
- Database: `AsyncSessionLocal`, `create_async_engine`, and
  `async_sessionmaker` are patched — **no real Postgres** is contacted.
- Signals/loop: `test_main.py` neutralizes real
  `loop.add_signal_handler` and makes `stop_event.wait()` resolve immediately so
  `main()` runs start→shutdown without hanging.

---

## Running the tests

### Locally (native)

From `services/data-simulator/`:

```bash
pip install -r requirements-dev.txt
PYTHONPATH=src pytest -v
```

`requirements-dev.txt` pulls in runtime deps (`-r requirements.txt`) plus
`pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `pre-commit`.

### Inside the running container (matches the root README)

```bash
docker exec -it data_simulator pip install -r requirements-dev.txt
docker exec -it data_simulator pytest -v
```

This runs the suite without rebuilding the image.

### At image-build time

The Dockerfile's `test` stage runs `pytest` during
`docker build --target test services/data-simulator` — a failing test fails the
build. See [deployment.md](deployment.md).

### As CI runs it (authoritative)

`.github/workflows/pr-pytest.yml` runs, from `services/data-simulator`:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
PYTHONPATH=src pytest -v          # env: PYTHONPATH=src
```

on Python 3.12. See [ci-cd.md](ci-cd.md).

---

## Coverage

`pytest-cov` is installed and a local `.coverage` file exists, but **coverage is
not enforced**: neither `pytest.ini`, the CI command, nor the Dockerfile passes
`--cov` or a threshold. To generate a report on demand:

```bash
PYTHONPATH=src pytest --cov=src --cov-report=term-missing
```

*(TODO: confirm with team whether a coverage gate is desired — it is listed as a
future enhancement in `pr-pytest-doc.md`.)*

---

## What is and isn't covered

**Covered (unit):** `Settings`/`DATABASE_URL`, `SmartBin` mapping, `create_tables`,
`seed_db` (including the 500-bin guard and finally-dispose), `KafkaClient`
(success, 10× retry-then-fail, retry-then-success, send success/failure/not-
started, stop), `setup_logging` (idempotence, levels, SIGUSR1 registration),
`_toggle_log_level`, `main()` orchestration order, `Bin`, `BinSimulator`
(lifecycle + fill/battery/clamp math), `SimulationManager` (initialize, add,
remove, update, stop, accessors).

**Not covered:** any real Postgres or Kafka integration (everything is mocked);
end-to-end "seed → run → observe on topic" flow; the hybrid `run_local.*`
scripts. There is **no integration-test suite** in the repo. *(TODO: confirm
with team whether integration tests are planned.)*

---

## Related documents

- [ci-cd.md](ci-cd.md) — how CI invokes these tests.
- [contributing.md](contributing.md) — conventions for adding tests.
