# CI PR Governance & Pytest — Detailed Trace

Paths under `.github/workflows/`.

## A. Governance chain

### 1. Trigger

**File**: `pr-controller.yml:3-5`
On PR to `develop`.

### 2. Detect branch type

**File**: `pr-controller.yml:8-52`, job `detect-branch`

Key logic:
- Reads `github.head_ref` (`:20`) and classifies by prefix: `devops/` (`:23`),
  `platform/` (`:30`), `feature/` (`:37`), `bugfix/` (`:46`); anything else →
  `exit 1` (`:50-51`).
- For `feature/<service>/<task>`: `service = cut -f2`, `task = cut -f3-`
  (`:39-40`), exported as job outputs (`:42-44`).

### 3. Call feature policy (only active path)

**File**: `pr-controller.yml:69-75`
If `type == 'feature'`, calls `feature-policy.yml` with `service` + `task`.
`devops`/`platform`/`bugfix` job calls are commented out (`:55-82`).

### 4. Enforce scope

**File**: `feature-policy.yml:24-98`

Key logic:
- Lists changed files via `tj-actions/changed-files` (`:37-39`).
- If `task == "docs"` → files must match `^docs/features/<service>/`
  (`:65-76`).
- Else → files must match `^services/<service>/` (`:84-95`).
- First out-of-scope file → prints error and `exit 1` (`:72-75`, `:91-94`).

## B. Pytest

### 1. Trigger

**File**: `pr-pytest.yml:3-6`
On PR to `develop`.

### 2. Setup

**File**: `pr-pytest.yml:16-40`
`working-directory: services/data-simulator` (`:18`), Python 3.12 with pip
cache (`:24-31`), install `requirements.txt` + `requirements-dev.txt`
(`:36-40`).

### 3. Run

**File**: `pr-pytest.yml:42-45`
`pytest -v` with `PYTHONPATH: src`.
