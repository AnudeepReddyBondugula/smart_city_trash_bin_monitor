# CI PR Governance & Pytest — Debug Guide

## Log locations

| Layer | Log file | What's in it |
|-------|----------|---------------|
| GitHub Actions | run logs on the PR's "Checks" tab | job output for `detect-branch`, `feature-policy`, `pr-pytest` |

## What to search for

| Symptom | Where to look | Search term |
|---------|---------------|-------------|
| Unknown branch prefix rejected | `pr-controller.yml:50-51` | controller job fails immediately |
| Out-of-scope file edit rejected | `feature-policy.yml:72,91` | `❌ Invalid change detected` |
| Failing test blocks merge | `pr-pytest.yml` job output | `pytest -v` non-zero exit |

## Quick commands

```bash
# Governance, locally (requires `act`)
act pull_request -e event.json -W .github/workflows/pr-controller.yml

# Tests, exactly as CI runs them
cd services/data-simulator && PYTHONPATH=src pytest -v
```

## Env vars that affect this flow

None beyond the branch name itself (`github.head_ref`) driving scope
detection.

## Common breakpoints

- `pr-controller.yml:20` branch-prefix classification.
- `feature-policy.yml:37-39` changed-files list — confirm scope regex against
  actual diff.
- `pr-pytest.yml:42-45` — reproduce locally with the quick command above.
