---
name: testing
description: >
  Load when writing or debugging tests — pytest layout, async tests, the env-var
  bootstrap in conftest, mocking Kafka/DB, and the custom docstring reporting
  hooks. Covers how to run tests exactly as CI does. Trigger words: test, pytest,
  conftest, fixture, mock, AsyncMock, pytest-asyncio, coverage, caplog.
---

# Testing

The `data-simulator` service uses `pytest` with `pytest-asyncio`. Tests live in
`services/data-simulator/tests/` and mirror the `src/` layout.

All paths below are relative to `services/data-simulator/`.

## Key files

- `pytest.ini` — config. `testpaths = tests` (`:2`); crucially
  `pythonpath = . src` (`:6`) puts **both** the service root and `src/` on
  `sys.path`.
- `tests/conftest.py` — sets dummy `POSTGRES_*` / `KAFKA_*` env vars in
  `os.environ` (`:6-12`) **at import time**, before any `src` module is imported.
  Required because importing `src/config.py`-consumers triggers `get_settings()`.
- Test modules mirror source:
  - `tests/test_main.py`, `tests/test_config.py`, `tests/test_database.py`,
    `tests/test_kafka_producer.py`, `tests/test_logging_config.py`,
    `tests/test_create_tables.py`, `tests/test_seed.py`
  - `tests/models/test_bin.py`
  - `tests/simulator/test_bin_simulator.py`,
    `tests/simulator/test_simulation_manager.py`

## Conventions (verified against existing tests)

- **Import style:** tests import via the `src.` prefix, e.g.
  `from src.main import main` (`tests/test_main.py:6`),
  `from src.models.bin import Bin` (`tests/simulator/test_bin_simulator.py:3`).
  This works because `.` is on `pythonpath`. (Source modules themselves use bare
  imports like `from kafka_producer import ...` because `src` is *also* on the
  path.)
- **Async tests:** decorate with `@pytest.mark.asyncio`
  (`tests/test_main.py:9`, `tests/simulator/test_bin_simulator.py:10`).
- **Mocking:** use `unittest.mock` — `AsyncMock` for awaitables, `patch` targeting
  the `src.` path (e.g. `@patch("src.main.kafka_client")` in
  `tests/test_main.py:13`). Kafka and the DB engine are always mocked; tests do
  **not** require a live broker or database.
- **Docstrings are meaningful:** every test's first docstring line is surfaced in
  verbose (`-v`) output by custom hooks in `tests/conftest.py:15-56`
  (`pytest_runtest_makereport` + `pytest_report_teststatus`). Write a one-line
  summary docstring at the top of each test.
- **Log assertions:** use the `caplog` fixture to assert on warnings/messages
  (e.g. `tests/simulator/test_bin_simulator.py:42`).

## Running the tests

See the `run-tests` command for exact invocations. Summary:

- **Exactly as CI does** (`.github/workflows/pr-pytest.yml:42-45`):
  ```bash
  cd services/data-simulator
  PYTHONPATH=src pytest -v
  ```
- **Simplest local run** (relies on `pytest.ini` `pythonpath`):
  ```bash
  cd services/data-simulator
  pytest
  ```
- **With coverage** (`pytest-cov` is installed): add `--cov=src`.
- The Docker `test` stage runs `pytest` at image build time
  (`Dockerfile:31`).

## How to add a test

1. Create `tests/<mirror-of-src-path>/test_<module>.py`.
2. Import the target via the `src.` prefix.
3. Add `@pytest.mark.asyncio` for coroutines.
4. Mock external I/O (`kafka_client`, `engine`, `AsyncSessionLocal`) with
   `AsyncMock`/`patch` on the `src.` path.
5. Give each test a one-line docstring (it shows up in `-v`).

## Pitfalls

- Don't rely on real env vars — `conftest.py` provides dummies. If you add a new
  required setting to `Settings`, add it to `conftest.py:6-12` too or import-time
  will fail across the suite.
- Because `pythonpath = . src`, a module name that exists both at root and under
  `src/` could shadow — keep test imports on the `src.` prefix for clarity.
