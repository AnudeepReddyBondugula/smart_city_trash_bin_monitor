---
description: Run the data-simulator pytest suite the way CI does.
---

# /run-tests

Runs the `pytest` suite for the `data-simulator` service. Use this to verify a
change locally before pushing (CI runs the same command on PRs to `develop`).

## Prerequisites

- Python 3.12 (matches `pr-pytest.yml:24-27` and `Dockerfile:4`).
- Dev deps installed:
  ```bash
  cd services/data-simulator
  pip install -r requirements-dev.txt   # pulls in requirements.txt too
  ```
- No live Postgres/Kafka needed — tests mock them, and `tests/conftest.py`
  provides dummy env vars.

## Commands

**Exactly as CI runs it** (`.github/workflows/pr-pytest.yml:42-45`):
```bash
cd services/data-simulator
PYTHONPATH=src pytest -v
```

**Shortest form** (relies on `pythonpath = . src` in `pytest.ini:6`):
```bash
cd services/data-simulator
pytest
```

**With coverage** (`pytest-cov` is in `requirements-dev.txt`):
```bash
cd services/data-simulator
PYTHONPATH=src pytest -v --cov=src
```

**A single file / test:**
```bash
cd services/data-simulator
PYTHONPATH=src pytest tests/simulator/test_bin_simulator.py -v
```

## Notes

- In `-v` mode each test prints its docstring's first line (custom hooks in
  `tests/conftest.py:15-56`).
- The Docker image also runs `pytest` at build time in the `test` stage
  (`Dockerfile:31`), so `docker compose build` exercises the suite too.
- See the `testing` skill for conventions when adding tests.
