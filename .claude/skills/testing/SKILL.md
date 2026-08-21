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
