---
name: ci-cd
description: >
  Load when working on CI/CD, GitHub Actions, branch naming, or PR governance —
  the pr-controller/feature-policy/pr-pytest workflows and the branch-scope rules
  they enforce. Trigger words: CI, CD, GitHub Actions, workflow, pipeline, branch
  policy, feature branch, pr-controller, feature-policy, act.
---

# CI/CD & PR Governance

CI runs on GitHub Actions and enforces two things on pull requests targeting
`develop`: (1) the change stays within its declared scope, and (2) the pytest
suite passes.

All workflow paths are under `.github/workflows/`.

## Key files

- `pr-controller.yml` — **PR Governance Controller**. Entry workflow, triggers on
  `pull_request` → `develop` (`:3-5`). Job `detect-branch` (`:8`) parses
  `github.head_ref` and classifies the branch into `devops/`, `platform/`,
  `feature/`, or `bugfix/` (`:23-52`); unknown prefixes fail the build (`:50-51`).
  Only the `feature` path is currently active — it calls `feature-policy.yml`
  (`:69-75`). The `devops`/`platform`/`bugfix` calls are commented out
  (`:55-82`).
- `feature-policy.yml` — **Feature Branch Policy**. A reusable workflow
  (`workflow_call`, `:6`) taking `service` and `task` inputs (`:7-22`). It uses
  `tj-actions/changed-files` (`:39`) then enforces scope (`:43-98`):
  - If `task == "docs"`: changes may **only** touch
    `docs/features/<service>/**` (`:65-76`).
  - Otherwise: changes may **only** touch `services/<service>/**` (`:84-95`).
  - Any file outside scope → `exit 1`.
- `pr-pytest.yml` — **PR Pytest**. Triggers on `pull_request` → `develop`
  (`:3-6`). Sets up Python 3.12, installs `requirements.txt` +
  `requirements-dev.txt`, and runs `pytest -v` with `PYTHONPATH: src` in
  `services/data-simulator` (`:16-45`).
- `feature-policy-doc.md`, `pr-pytest-doc.md` — human-readable notes on the
  above (companion docs, not executed).
- `event.json` (repo root) — a sample `pull_request` event for local `act` runs
  (gitignored per `.gitignore`).

## Branch naming (enforced)

`detect-branch` (`pr-controller.yml:37-44`) parses feature branches as:

```
feature/<service>/<task>
        └service┘ └─task─┘   (task = everything after the 2nd slash, :40)
```

Example: `feature/data-simulator/adding-pytests-for-simulation-flow`
→ service=`data-simulator`, task=`adding-pytests-for-simulation-flow`.

So a feature branch may **only** modify files under `services/data-simulator/`
(or, if the task is literally `docs`, under `docs/features/data-simulator/`).

## Running CI locally with `act`

Per `README.md:94-99`:
```bash
act pull_request -e event.json -W .github/workflows/pr-controller.yml
```

## How to extend safely

- **New branch class:** add a prefix branch in `detect-branch`
  (`pr-controller.yml:23-52`), create a matching `*-policy.yml` reusable
  workflow, and un-comment / add the corresponding `uses:` job (`:55-82` shows
  the pattern to follow).
- **Change the pytest job:** keep it consistent with how the `testing` skill and
  `run-tests` command describe local runs (`PYTHONPATH=src`, Python 3.12).

## Pitfalls (evidence in code)

- CI (both `pr-controller.yml:4` and `pr-pytest.yml:5`) triggers on PRs to
  **`develop`**, not `master`. PRs to other bases won't run these checks.
- Only the `feature` governance path is live; `devops`, `platform`, and `bugfix`
  handling is commented out (`pr-controller.yml:55-82`), so those branch types
  pass `detect-branch` but get no scope enforcement.
- The scope regex is prefix-based (`^services/$SERVICE/`,
  `feature-policy.yml:87`) — a `service` value that is a prefix of another dir
  could over-match; keep service names distinct.
