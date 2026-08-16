---
description: Scaffold a new pytest test matching this repo's conventions.
argument-hint: <src module path, e.g. src/simulator/bin_simulator.py>
---

# /new-test <src module path>

Scaffolds a new test file for a `src/` module in `services/data-simulator`,
following the exact conventions already used in `tests/`.

## Prerequisites

- The target lives under `services/data-simulator/src/`.
- `$ARGUMENTS` is the source module path (e.g.
  `src/simulator/simulation_manager.py`).

## Conventions to follow (verified against existing tests)

- **Location mirrors source:** `src/<pkg>/<mod>.py` → `tests/<pkg>/test_<mod>.py`
  (e.g. `tests/simulator/test_bin_simulator.py`).
- **Import via the `src.` prefix:** `from src.simulator.bin_simulator import
  BinSimulator` (works because `pytest.ini:6` has `pythonpath = . src`).
- **Async tests:** `@pytest.mark.asyncio` (see `tests/test_main.py:9`).
- **Mock external I/O** with `unittest.mock` (`AsyncMock`, `patch`) targeting the
  `src.` path — e.g. `@patch("src.main.kafka_client")` (`tests/test_main.py:13`).
  Never require a live Kafka/DB.
- **One-line docstring** at the top of each test — it's surfaced in `-v` output
  by `tests/conftest.py:15-56`.
- Use `caplog` to assert on log messages when relevant
  (`tests/simulator/test_bin_simulator.py:42`).

## Steps

1. Parse `$ARGUMENTS` into package + module; compute the mirrored test path under
   `tests/`. Create intermediate dirs if needed.
2. Read the target module to enumerate public functions/classes to cover.
3. Write `tests/.../test_<mod>.py` with the imports, an `@pytest.mark.asyncio`
   test per coroutine (plain `def` for sync), docstrings, and mocks for any
   Kafka/DB access.
4. If the module needs a required env var not already in
   `tests/conftest.py:6-12`, add it there.
5. Run it: `cd services/data-simulator && PYTHONPATH=src pytest <new file> -v`
   (see the `run-tests` command).

## Template

```python
import pytest
from unittest.mock import AsyncMock, patch

from src.<pkg>.<mod> import <Target>


@pytest.mark.asyncio
async def test_<behavior>():
    """One-line summary shown in verbose output."""
    ...
```

## Related

- `.claude/skills/testing/SKILL.md`.
