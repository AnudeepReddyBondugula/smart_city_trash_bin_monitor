import os

import pytest

# Set dummy environment variables for pydantic settings validation during tests
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_DB"] = "test_db"
os.environ["POSTGRES_USER"] = "test_user"
os.environ["POSTGRES_PASSWORD"] = "test_password"
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"
os.environ["KAFKA_TOPIC"] = "simulated_telemetry"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach the test's first docstring line to the call-phase report.

    This is read later by ``pytest_report_teststatus`` so the docstring can be
    surfaced in verbose output. Stashing on the report avoids mutating pytest's
    private ``item._nodeid``, which previously risked breaking plugins, coverage
    reporting, test selection, and CI output parsing.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    doc = getattr(getattr(item, "function", None), "__doc__", None)
    if not doc:
        return
    lines = [line.strip() for line in doc.strip().split("\n") if line.strip()]
    if lines:
        report.docstring = lines[0]


def pytest_report_teststatus(report, config):
    """Append the test docstring to the verbose outcome word (e.g. PASSED ...).

    Uses pytest's documented reporting hook so the node ID itself is never
    rewritten. Returns ``None`` for non-verbose runs and non-call phases so
    default handling is preserved.
    """
    if getattr(config.option, "verbose", 0) < 1:
        return None
    if report.when != "call":
        return None
    doc = getattr(report, "docstring", None)
    if not doc:
        return None
    if report.passed:
        return "passed", ".", f"PASSED  {doc}"
    if report.failed:
        return "failed", "F", f"FAILED  {doc}"
    if report.skipped:
        return "skipped", "s", f"SKIPPED  {doc}"
    return None
