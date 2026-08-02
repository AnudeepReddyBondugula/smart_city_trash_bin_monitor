# CI/CD

CI is GitHub Actions. There are **three** workflow files, all under
`.github/workflows/`. CI runs **tests and governance checks only** — it does not
build images, publish artifacts, or deploy. This document describes the
pipeline exactly as the YAML defines it.

| File | Name | Trigger |
| --- | --- | --- |
| `pr-controller.yml` | PR Governance Controller | `pull_request` → `develop` |
| `feature-policy.yml` | Feature Branch Policy | `workflow_call` (reusable; invoked by the controller) |
| `pr-pytest.yml` | PR Pytest | `pull_request` → `develop` |

There are also two human-readable companion docs:
`feature-policy-doc.md` and `pr-pytest-doc.md`.

> **Trigger scope:** every workflow triggers on pull requests targeting
> **`develop`**. PRs to other branches (e.g. `master`) do not run these checks.
> *(TODO: confirm with team whether `master`/`main` should also be protected.)*

---

## 1. PR Governance Controller (`pr-controller.yml`)

Routes a PR to the right policy based on its **branch name** (`github.head_ref`).

`detect-branch` job parses the branch prefix (`pr-controller.yml:16-52`):

| Branch prefix | `type` | Extracted |
| --- | --- | --- |
| `devops/…` | `devops` | `task` |
| `platform/…` | `platform` | `task` |
| `feature/<service>/<task>` | `feature` | `service`, `task` |
| `bugfix/…` | `bugfix` | — |
| anything else | — | **fails** ("Unknown branch type", `exit 1`) |

Only the `feature` route is currently active — it calls the reusable
`feature-policy.yml` with `service` and `task` (`pr-controller.yml:69-75`). The
`devops`, `platform`, and `bugfix` routes are **commented out** in the YAML.

---

## 2. Feature Branch Policy (`feature-policy.yml`)

Reusable workflow (`on: workflow_call`) taking `service` and `task` inputs. It
enforces that a feature branch touches **only** files in its own scope, using
`tj-actions/changed-files@v44` to list changed files
(`feature-policy.yml:24-98`).

| Case | Allowed paths | Rule |
| --- | --- | --- |
| `task == "docs"` | `docs/features/<service>/**` | Docs-only branches may modify only that service's docs. |
| any other task | `services/<service>/**` | Standard feature branches may modify only their service directory. |

Any changed file outside the allowed prefix prints
`❌ Invalid change detected: <file>` and exits non-zero, failing the PR
(`feature-policy.yml:70-95`). On success: `✅ Feature policy passed`.

Concrete example (this very docs branch): a branch named
`feature/data-simulator/docs` may modify only
`docs/features/data-simulator/**`. See the companion `feature-policy-doc.md`
for worked allowed/rejected examples.

---

## 3. PR Pytest (`pr-pytest.yml`)

Runs the test suite. All steps run with
`working-directory: services/data-simulator` (`pr-pytest.yml:16-18`).

Steps (`pr-pytest.yml:20-45`):

1. `actions/checkout@v4`.
2. `actions/setup-python@v5` with Python **3.12**, `cache: pip`, keyed on
   `requirements.txt` + `requirements-dev.txt`.
3. `python -m pip install --upgrade pip`.
4. `pip install -r requirements.txt`.
5. `pip install -r requirements-dev.txt`.
6. `pytest -v` with env `PYTHONPATH: src`.

`permissions: contents: read` (`pr-pytest.yml:8-9`) — least-privilege token.

---

## What CI does NOT do (verified)

- **No linting or type-checking in CI.** No workflow runs `ruff`, `black`, or
  `mypy` (`grep -rn 'ruff\|black\|mypy' .github/workflows/` returns nothing) —
  even though `ruff`, `mypy`, and `pre-commit` are in `requirements-dev.txt` and
  a `ruff.toml` exists at the repo root. These are **local-only** quality gates.
  The `pr-pytest-doc.md` lists Ruff/Black/MyPy/coverage as *future* enhancements.

  > **Discrepancy:** the root `README.md` claims running `act` "validates the
  > feature policy, runs the Ruff linter, and executes the Pytest suite." The
  > actual workflows invoked on a PR run feature-policy + pytest **only** — no
  > Ruff step exists. Treat the README's Ruff claim as inaccurate.
  > *(TODO: confirm with team whether a Ruff CI step is intended.)*

- **No coverage gate.** `pytest-cov` is installed and a `.coverage` file exists
  locally, but the CI command is plain `pytest -v` — no `--cov` flag, no
  threshold.
- **No build/publish/deploy.** No `docker build`/`push`, no registry, no
  environment deploy. The Dockerfile's `test` stage does run `pytest` at image
  build time, but nothing in CI builds that image.

---

## Deploy gates

There is no deployment stage, so there are no deploy gates in the pipeline. The
effective merge gates (as intended) are the two required checks on `develop`:
**Feature Branch Policy** and **PR Pytest**. `pr-pytest-doc.md` recommends
configuring these as required status checks via branch protection; whether
branch protection is actually enabled on GitHub is a repo setting, not visible
in the code. *(TODO: confirm branch-protection settings with team.)*

---

## Running CI locally with `act`

From the root README, using the sample event `event.json` (which sets
`head.ref = feature/data-simulator/adding-pytests-for-simulation-flow`):

```bash
act pull_request -e event.json -W .github/workflows/pr-controller.yml
```

This runs the governance controller locally. (Per the discrepancy above, this
does not run Ruff.)

---

## Related documents

- [testing.md](testing.md) — the pytest suite CI executes.
- [contributing.md](contributing.md) — branch naming that the policy enforces.
- [deployment.md](deployment.md) — why there is no CD stage.
