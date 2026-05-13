"""
netlify_reporter.py — Shared utility to push pytest results to Netlify Blobs.

Usage in any test file:
    from netlify_reporter import push_results

    # After collecting results, call:
    push_results(BLOB_KEY, results_dict)

    Where results_dict maps test IDs to { "status": "passed"|"failed"|"none", "notes": "..." }
"""

import os
import json
import requests
from datetime import datetime, timezone

# Your Netlify site ID — set as NETLIFY_SITE_ID in GitHub Secrets
SITE_ID = os.environ.get("NETLIFY_SITE_ID", "")

# Netlify personal access token — set as NETLIFY_TOKEN in GitHub Secrets
TOKEN = os.environ.get("NETLIFY_TOKEN", "")

NETLIFY_BLOBS_URL = "https://api.netlify.com/api/v1/blobs/{site_id}/{key}"


def push_results(blob_key: str, results: dict) -> bool:
    """
    Push test results to Netlify Blobs.

    Args:
        blob_key: The blob key used by the HTML page (e.g. 'jobsites-qa-results')
        results:  Dict mapping test IDs to { status, notes }
                  e.g. { "CUS-02": { "status": "passed", "notes": "" }, ... }

    Returns:
        True if saved to cloud, False if failed.
    """
    if not SITE_ID or not TOKEN:
        print("[netlify_reporter] ⚠  NETLIFY_SITE_ID or NETLIFY_TOKEN not set — skipping cloud push.")
        return False

    payload = {
        "results": results,
        "savedAt": datetime.now(timezone.utc).isoformat(),
        "source": "github-actions",
    }

    url = NETLIFY_BLOBS_URL.format(site_id=SITE_ID, key=blob_key)

    try:
        resp = requests.put(
            url,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if resp.ok:
            print(f"[netlify_reporter] ✅  Results pushed to Netlify Blobs → {blob_key}")
            return True
        else:
            print(f"[netlify_reporter] ❌  Netlify Blobs returned {resp.status_code}: {resp.text}")
            return False
    except Exception as exc:
        print(f"[netlify_reporter] ❌  Failed to push results: {exc}")
        return False


def build_results_from_pytest(test_map: dict, passed_ids: list, failed_ids: list, notes_map: dict = None) -> dict:
    """
    Helper to build the results dict from pytest pass/fail lists.

    Args:
        test_map:    Dict of all test IDs (keys) — used to initialise 'none' for untested
        passed_ids:  List of test IDs that passed
        failed_ids:  List of test IDs that failed
        notes_map:   Optional dict of { test_id: "note string" }

    Returns:
        results dict ready for push_results()
    """
    notes = notes_map or {}
    results = {}
    for test_id in test_map:
        if test_id in passed_ids:
            status = "passed"
        elif test_id in failed_ids:
            status = "failed"
        else:
            status = "none"
        results[test_id] = {
            "status": status,
            "notes": notes.get(test_id, ""),
            "ts": None,
        }
    return results
