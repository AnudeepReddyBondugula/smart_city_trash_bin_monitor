# Contributing

How to set up locally and the conventions this repo actually enforces. Where a
convention is only *evidenced* (config present) versus *enforced* (a check
fails), that distinction is called out.

---

## Local setup

Prerequisites: Python 3.12, Docker + Docker Compose.

```bash
# 1. Clone and enter the service
cd services/data-simulator

# 2. Create a virtualenv and install dev deps (includes runtime deps)
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 3. Create your env files (git-ignored)
cp .env.local.example .env.local           # for running natively
cp .env.local.example .env.docker          # for the Docker stack (Compose reads this)
#   .env.local  → POSTGRES_HOST=localhost, KAFKA_BOOTSTRAP_SERVERS=localhost:9092
#   .env.docker → POSTGRES_HOST=postgres,  KAFKA_BOOTSTRAP_SERVERS=kafka:29092
```

> Why create `.env.docker` by hand: it is git-ignored yet Compose requires it,
> and the README's `.env.docker.local` name is not the one Compose reads. See
> [configuration.md](configuration.md).

### Run it

- **Full stack in Docker:** `docker compose up -d --build` (from repo root),
  then seed + restart — see [deployment.md](deployment.md).
- **Hybrid (infra in Docker, app on host):** `scripts/run_local.sh` /
  `scripts/run_local.ps1`. If connecting the host app to the Dockerized
  Postgres, note the host port is **5433** (see
  [troubleshooting.md](troubleshooting.md)).

### Run the tests

```bash
PYTHONPATH=src pytest -v
```

See [testing.md](testing.md).

---

## Coding conventions

### Formatting / linting — Ruff

`ruff.toml` (repo root):

```toml
line-length = 125

[lint]
select = ["E", "F"]
ignore = []
```

Ruff (pycodestyle `E` + Pyflakes `F`) with a 125-char line limit. Run:

```bash
ruff check .        # lint
ruff format .       # format (if you use Ruff's formatter)
```

> **Ruff is not enforced in CI.** No workflow runs it (see
> [ci-cd.md](ci-cd.md)); it is a local/pre-commit gate only. Run it yourself
> before pushing. The root README's claim that `act`/CI "runs the Ruff linter"
> is inaccurate. *(TODO: confirm with team whether a Ruff CI step should be
> added.)*

### Type checking — mypy

`mypy` is in `requirements-dev.txt`, but there is **no `mypy.ini` /
`pyproject.toml` / `setup.cfg` mypy configuration** in the repo, and it does not
run in CI. Type hints are used throughout `src/`, but type checking is currently
ad-hoc. *(TODO: confirm with team whether mypy config/gating is intended.)*

### pre-commit

`pre-commit` is in `requirements-dev.txt`, but there is **no
`.pre-commit-config.yaml`** in the repo — so `pre-commit install` has nothing to
run yet. *(TODO: confirm with team whether a pre-commit config should be
committed; the installed tool suggests it was planned.)*

### Code style observed in `src/`

Follow the existing style when adding code:

- **Flat imports within `src/`** (e.g. `from config import get_settings`,
  `from database import engine`) — enabled by `PYTHONPATH=src`. There is
  intentionally no `__init__.py` in `src/`. Preserve this pattern; changing it
  affects both runtime and the test import setup.
- **Structured logging** via module-level `logger = logging.getLogger(__name__)`
  and `%`-style lazy args (`logger.info("Started %d simulator(s).", n)`).
- **Google-style docstrings** on classes/methods (see `models/bin.py`,
  `bin_simulator.py`). New tests get a short docstring — `conftest.py` surfaces
  its first line in `-v` output.
- **Type hints** on signatures and attributes (`Mapped[...]`, `dict[str,
  BinSimulator]`, `asyncio.Task | None`).
- **Async I/O only** — never introduce blocking I/O into the event loop; use the
  async engine / `aiokafka`.

---

## Branch naming & PR scope (enforced)

CI **enforces** branch naming and file scope on PRs to `develop`
(see [ci-cd.md](ci-cd.md)):

- Feature branches: `feature/<service>/<task>` (e.g.
  `feature/data-simulator/add-metrics`). The controller parses `<service>` and
  `<task>`; an unrecognized prefix **fails the PR**.
- A standard feature branch may modify **only** `services/<service>/**`.
- A branch whose task is exactly `docs` (`feature/<service>/docs`) may modify
  **only** `docs/features/<service>/**`.
- Other recognized prefixes: `devops/…`, `platform/…`, `bugfix/…` (routing for
  these is currently commented out in `pr-controller.yml`).

So: keep code changes inside your service directory, and put documentation
changes on a separate `.../docs` branch. Cross-cutting changes will be rejected
by the feature-policy check.

---

## PR / review process

- **Target branch:** open PRs against `develop` (that is what the workflows
  trigger on).
- **Required checks (intended):** **Feature Branch Policy** and **PR Pytest**
  must pass. `pr-pytest-doc.md` recommends configuring these as required status
  checks via branch protection.
- **No `CODEOWNERS`, no pull-request template, and no `CONTRIBUTING.md`** exist
  in the repo (verified). Review assignment/approval rules are therefore GitHub
  repo settings, not committed policy. *(TODO: confirm with team the actual
  review/approval requirements.)*

Update docs alongside behavior changes — the docs index
(`docs/features/README.md`) states documentation is treated as part of the
source and PRs changing behavior should update the relevant docs.

---

## Related documents

- [ci-cd.md](ci-cd.md) — the checks your PR must pass.
- [testing.md](testing.md) — writing and running tests.
- [project-structure.md](project-structure.md) — where new code belongs.
