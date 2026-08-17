# CI PR Governance & Pytest

Trigger: a pull request opened/updated against `develop`.
End state: PR either passes both branch-scope governance and the pytest
suite, or fails with a scope/test error.

Paths under `.github/workflows/`.

## Flow

Two independent workflows trigger on `pull_request` → `develop`.

```
[A. Governance chain]
pr-controller.yml :: trigger on PR to develop        :3-5
  detect-branch job                                  :8-52
    reads github.head_ref                            :20
    classifies by prefix: devops/, platform/,
      feature/, bugfix/ ; else exit 1                 :23,30,37,46,50-51
    feature/<service>/<task> → service, task outputs   :39-44
  call feature-policy.yml (only active path)           :69-75
    (devops/platform/bugfix calls commented out)       :55-82
    feature-policy.yml :: enforce scope                :24-98
      list changed files (tj-actions/changed-files)     :37-39
      task=="docs"  → must match ^docs/features/<service>/   :65-76
      else          → must match ^services/<service>/        :84-95
      first out-of-scope file → error + exit 1                :72-75,91-94

[B. Pytest]
pr-pytest.yml :: trigger on PR to develop             :3-6
  setup: working-directory services/data-simulator     :16-40
    Python 3.12 + pip cache                             :24-31
    install requirements.txt + requirements-dev.txt     :36-40
  run: pytest -v  (PYTHONPATH=src)                      :42-45
```

## Sub-flows

None — both chains are independent and documented together since they gate
the same PR.
