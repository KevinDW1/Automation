"""
netlify_reporter.py — Pushes pytest results to Netlify Blobs via CLI.
"""

import os
import json
import subprocess
from datetime import datetime, timezone

SITE_ID = os.environ.get("NETLIFY_SITE_ID", "")
TOKEN   = os.environ.get("NETLIFY_TOKEN", "")


def push_results(blob_store: str, results: dict) -> bool:
    if not SITE_ID or not TOKEN:
        print("[netlify_reporter] ⚠  NETLIFY_SITE_ID or NETLIFY_TOKEN not set — skipping.")
        return False

    payload = json.dumps({
        "results": results,
        "savedAt": datetime.now(timezone.utc).isoformat(),
        "source": "github-actions",
    })

    env = os.environ.copy()
    env["NETLIFY_AUTH_TOKEN"] = TOKEN
    env["NETLIFY_SITE_ID"]    = SITE_ID

    try:
        result = subprocess.run(
            ["netlify", "blobs:set", blob_store, "results", payload],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print(f"[netlify_reporter] ✅  Results pushed → {blob_store}/results")
            return True
        else:
            print(f"[netlify_reporter] ❌  CLI error: {result.stderr.strip()}")
            return False
    except Exception as exc:
        print(f"[netlify_reporter] ❌  Failed: {exc}")
        return False


def build_results_from_pytest(test_map: dict, passed_ids: list, failed_ids: list, notes_map: dict = None) -> dict:
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
