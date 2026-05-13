"""
conftest.py — Drop this in your project root (or each test folder).

Automatically captures pass/fail for every test and pushes results
to Netlify Blobs after the full suite completes.

Blob key mapping (must match your HTML pages):
    Customer tests  (CUS-*)  → customers-qa-results   ← UPGRADED from localStorage
    Jobsite tests   (JOB-*)  → jobsites-qa-results
    Invoice tests   (INV-*)  → invoices-qa-results
    Vendor tests    (VD-*)   → vendors-qa-state
"""

import pytest
from netlify_reporter import push_results

# Maps test ID prefix → blob key
BLOB_KEY_MAP = {
    "CUS": "customers-qa-results",
    "JOB": "jobsites-qa-results",
    "INV": "invoices-qa-results",
    "VD":  "vendors-qa-state",
}

# Collected during the run
_results: dict[str, dict] = {}


def _get_test_id(nodeid: str) -> str | None:
    """
    Extract the QA test ID from a pytest node ID.
    e.g. 'Customer/cus02_to_cus24.py::test_cus02' → 'CUS-02'
         'Vendor/vd001.py::test_vd001'             → 'VD-001'
    """
    name = nodeid.split("::")[-1]  # e.g. test_cus02
    name = name.replace("test_", "").upper()  # CUS02

    # Map function name back to hyphenated ID
    for prefix in BLOB_KEY_MAP:
        if name.startswith(prefix.replace("-", "")):
            # Strip prefix, zero-pad number
            num_part = name[len(prefix):]
            try:
                num = int(num_part)
                return f"{prefix}-{num:02d}"
            except ValueError:
                pass
    return None


def pytest_runtest_logreport(report):
    """Called after each test phase (setup / call / teardown)."""
    if report.when != "call":
        return

    test_id = _get_test_id(report.nodeid)
    if not test_id:
        return

    if report.passed:
        _results[test_id] = {"status": "passed", "notes": "", "ts": None}
    elif report.failed:
        # Capture failure reason from longrepr
        reason = ""
        if hasattr(report, "longreprtext"):
            reason = report.longreprtext[:300]
        elif hasattr(report, "longrepr") and report.longrepr:
            reason = str(report.longrepr)[:300]
        _results[test_id] = {"status": "failed", "notes": reason, "ts": None}
    elif report.skipped:
        _results[test_id] = {"status": "none", "notes": "skipped", "ts": None}


def pytest_sessionfinish(session, exitstatus):
    """Called once after all tests complete — push results grouped by blob key."""
    if not _results:
        return

    # Group by blob key
    groups: dict[str, dict] = {}
    for test_id, result in _results.items():
        prefix = test_id.split("-")[0]
        blob_key = BLOB_KEY_MAP.get(prefix)
        if blob_key:
            groups.setdefault(blob_key, {})[test_id] = result

    # Push each group
    for blob_key, results in groups.items():
        push_results(blob_key, results)
