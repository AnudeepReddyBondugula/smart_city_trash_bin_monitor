# PR Pytest Workflow

## Overview

The `pr-pytest.yml` workflow is the Continuous Integration (CI) workflow responsible for validating Python code by running the project's unit tests.

The workflow is triggered automatically whenever a Pull Request (PR) is opened, synchronized, or reopened against the `develop` branch. Its purpose is to ensure that new changes do not introduce regressions before they are merged.

---

## Trigger

```yaml
on:
  pull_request:
    branches:
      - develop
```

The workflow executes only for pull requests targeting the `develop` branch.

### Example

```
feature/data-simulator/add-kafka-producer
                │
                ▼
             develop
```

The workflow starts automatically after the pull request is created or updated.

---

## Workflow Responsibilities

The workflow performs the following steps:

1. **Checkout the repository**

   * Retrieves the latest source code from the pull request.

2. **Set up Python**

   * Installs the configured Python version.
   * Restores cached Python dependencies when available.

3. **Install project dependencies**

   * Installs runtime dependencies from `requirements.txt`.
   * Installs development dependencies from `requirements-dev.txt`.

4. **Run unit tests**

   * Executes the complete pytest suite located under the service.

If any test fails, the workflow fails and the pull request cannot pass the required status checks.

---

## Project Structure

The workflow currently targets the Data Simulator service.

```
services/
└── data-simulator/
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── pytest.ini
    ├── src/
    └── tests/
```

All workflow commands execute from:

```
services/data-simulator
```

---

## Expected Outcome

| Test Result            | Workflow Status |
| ---------------------- | --------------- |
| All tests pass         | ✅ Success       |
| One or more tests fail | ❌ Failed        |

A failed workflow indicates that the proposed changes introduced a failing test or broke the existing test suite.

---

## Branch Protection

This workflow is intended to be configured as a required status check for the `develop` branch.

Recommended GitHub Branch Protection Rule:

* Require pull requests before merging.
* Require status checks to pass before merging.
* Require the **PR Pytest** workflow to succeed.

This prevents code with failing tests from being merged into the development branch.

---

## Future Enhancements

As the project grows, this workflow can be extended to include additional quality gates, such as:

* Ruff linting
* Black formatting checks
* MyPy type checking
* Code coverage reporting
* Security scanning
* Docker image build validation
* Multi-version Python testing

These checks may be added as separate jobs within the workflow or as reusable GitHub Actions workflows.

---

## Maintenance

When modifying this workflow:

* Keep dependency installation deterministic.
* Update the Python version when the project's supported version changes.
* Ensure new test dependencies are added to `requirements-dev.txt`.
* Keep the workflow generic so it can be extended to additional Python services in the future.
