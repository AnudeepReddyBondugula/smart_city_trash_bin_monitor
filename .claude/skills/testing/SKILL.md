---
name: testing
description: >
  Load for pytest, async tests, fixtures, mocks, Alembic revision checks,
  coverage, or CI reproduction.
---

# Testing

Tests live under `services/data-simulator/tests/`. `pytest.ini` adds the service
root and `src/` to Python's import path. `tests/conftest.py` installs dummy
settings before imports and adds docstring summaries to verbose output.

- Import application modules through `src.` in tests.
- Mark coroutine tests with `@pytest.mark.asyncio`.
- Use `AsyncMock` for awaited calls and patch the name used by the module.
- Mock Kafka and database I/O in unit tests.
- Give each test a short docstring.
- `tests/test_migrations.py` guards the linear Alembic revision chain.

```bash
cd services/data-simulator
pytest -q
pytest -v --cov=src
ruff check .
docker build --target test -t smart-city-data-simulator-test .
```

CI installs both requirements files and runs `pytest -v`. Adding a required
setting also requires a dummy value in `tests/conftest.py`.

## Two services, two suites

`services/data-simulator/` runs on Python 3.12. `services/stream-processor/`
runs on **3.11** — PySpark 3.5 does not support 3.12 and its pandas operators
fail at run time importing `distutils`. CI runs one job per service with its own
Python version.

```bash
cd services/data-simulator   && .venv/bin/python -m pytest -q
cd services/stream-processor && .venv/bin/python -m pytest -q
```

The stream-processor suite starts a real local SparkSession, shared session-wide
by the `spark` fixture. Prefer testing transformations as plain DataFrame
functions on batch data — they behave identically on a stream — and reserve the
streaming fixture for what batch cannot reach: watermarks, deduplication,
windowing, and the state store round-trip.

The per-bin rules are plain Python over dictionaries with a `FakeGroupState`
stand-in, so they need no cluster at all. Every rule has both a positive case
and a must-not-fire case; a rule that fires on everything and a correct one look
identical if only the first is tested.
