# Feature Branch Policy Workflow

## Overview

The `feature-policy.yml` workflow enforces repository governance for feature branches.

Its primary responsibility is to ensure that a feature branch modifies only the files that belong to the service it was created for. This helps maintain service isolation, reduces accidental cross-service changes, and simplifies code reviews.

This workflow is **not triggered directly**. It is invoked as a reusable workflow by the repository's governance workflow.

---

# Trigger

The workflow uses the `workflow_call` event.

```yaml
on:
  workflow_call:
```

This means another GitHub Actions workflow is responsible for calling it and providing the required inputs.

---

# Inputs

The workflow requires two inputs.

| Input     | Description                        | Example              |
| --------- | ---------------------------------- | -------------------- |
| `service` | Name of the service being modified | `data-simulator`     |
| `task`    | Name of the feature task           | `add-kafka-producer` |

Example branch:

```text
feature/data-simulator/add-kafka-producer
```

Produces:

```text
service = data-simulator
task = add-kafka-producer
```

---

# Workflow Flow

```text
Pull Request
      │
      ▼
pr-governance.yml
      │
      ▼
feature-policy.yml
      │
      ▼
Retrieve changed files
      │
      ▼
Validate every modified file
      │
      ├────────────── Valid
      │                 │
      │                 ▼
      │          Workflow succeeds
      │
      └────────────── Invalid
                        │
                        ▼
                 Workflow fails
```

---

# Validation Rules

## Standard Feature Branch

Feature branches may modify files only within their assigned service directory.

Allowed:

```text
services/<service>/**
```

Example:

Branch

```text
feature/data-simulator/add-kafka
```

Allowed files:

```text
services/data-simulator/src/main.py
services/data-simulator/tests/test_main.py
services/data-simulator/requirements.txt
```

Rejected:

```text
services/event-streaming/main.py
README.md
.github/workflows/pr-pytest.yml
```

---

## Documentation Feature

If the task name is `docs`, the workflow allows modifications only under:

```text
docs/features/<service>/**
```

Example:

Branch

```text
feature/data-simulator/docs
```

Allowed:

```text
docs/features/data-simulator/design.md
docs/features/data-simulator/api.md
```

Rejected:

```text
services/data-simulator/main.py
README.md
```

---

# Failure Behaviour

If a file is detected outside the permitted directory, the workflow immediately fails.

Example output:

```text
❌ Invalid change detected: README.md

Feature branches may ONLY modify:

services/data-simulator/**
```

This prevents pull requests from introducing unintended changes outside the feature's scope.

---

# Benefits

* Enforces clear ownership of service changes.
* Prevents accidental modifications to unrelated services.
* Simplifies pull request reviews.
* Encourages developers to keep feature branches focused.
* Supports scalable development in a multi-service repository.

---

# Future Enhancements

Potential improvements include:

* Allow shared directories (for example, `shared/` or `common/`) through an allowlist.
* Validate branch naming conventions before enforcing file scope.
* Support multiple services within a single feature branch when explicitly approved.
* Produce a detailed summary of allowed and rejected files in the workflow output.

---

# Maintenance

When updating this workflow:

* Keep the directory validation rules aligned with the repository structure.
* Update the allowed paths if services are renamed or moved.
* Ensure new shared directories are explicitly handled rather than implicitly permitted.
* Test the workflow with both valid and invalid pull requests to verify policy enforcement.
