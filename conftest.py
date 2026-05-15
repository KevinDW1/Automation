import pytest
from netlify_reporter import push_results

BLOB_KEY_MAP = {
    "CUS": "customers-qa-results",
    "JOB": "jobsites-qa-results",
    "INV": "invoices-qa-results",
    "VEN": "vendors-qa-state",
    "TC":  "equipment-qa-results",
}

_results = {}

def _get_test_id(nodeid):
    name = nodeid.split("::")[-1].replace("test_", "").upper()
    for prefix in BLOB_KEY_MAP:
        if name.startswith(prefix):
            num_part = name[len(prefix):]
            try:
                return f"{prefix}-{int(num_part):02d}"
            except ValueError:
                pass
    return None

def pytest_runtest_logreport(report):
    if report.when != "call":
        return
    test_id = _get_test_id(report.nodeid)
    if not test_id:
        return
    if report.passed:
        _results[test_id] = {"status": "passed", "notes": "", "ts": None}
    elif report.failed:
        reason = str(report.longrepr)[:300] if hasattr(report, "longrepr") and report.longrepr else ""
        _results[test_id] = {"status": "failed", "notes": reason, "ts": None}
    elif report.skipped:
        _results[test_id] = {"status": "none", "notes": "skipped", "ts": None}

def pytest_sessionfinish(session, exitstatus):
    if not _results:
        return
    print(f"[conftest] Pushing {len(_results)} results")
    groups = {}
    for test_id, result in _results.items():
        prefix = test_id.split("-")[0]
        blob_key = BLOB_KEY_MAP.get(prefix)
        if blob_key:
            groups.setdefault(blob_key, {})[test_id] = result
    for blob_key, results in groups.items():
        print(f"[conftest] Pushing {len(results)} to {blob_key}")
        push_results(blob_key, results)
