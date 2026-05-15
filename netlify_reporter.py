"""
netlify_reporter.py — Shared utility to push pytest results to Netlify Blobs.
"""

import os
import json
import requests
from datetime import datetime, timezone

SITE_ID = os.environ.get("NETLIFY_SITE_ID", "")
TOKEN   = os.environ.get("NETLIFY_TOKEN", "")


def push_results(blob_key: str, results: dict) -> bool:
    if not SITE_ID or not TOKEN:
        print("[netlify_reporter] ⚠  NETLIFY_SITE_ID or NETLIFY_TOKEN not set — skipping.")
        return False

    payload = {
        "results": results,
        "savedAt": datetime.now(timezone.utc).isoformat(),
        "source": "github-actions",
    }

    # Step 1: get a signed upload URL from Netlify
    sign_url = f"https://api.netlify.com/api/v1/sites/{SITE_ID}/blobs/{blob_key}"
    print(f"[netlify_reporter] Requesting signed URL: {sign_url}")

    try:
        sign_resp = requests.get(
            sign_url,
            headers={"Authorization": f"Bearer {TOKEN}"},
            params={"sign": "true"},
            timeout=15,
        )
        print(f"[netlify_reporter] Sign response: {sign_resp.status_code} {sign_resp.text[:300]}")

        if sign_resp.ok:
            signed = sign_resp.json()
            upload_url = signed.get("url")
            if not upload_url:
                # Some versions return the data directly — try direct PUT
                raise ValueError("No signed URL returned, trying direct PUT")

            # Step 2: upload to the signed URL
            up_resp = requests.put(
                upload_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if up_resp.ok:
                print(f"[netlify_reporter] ✅  Results pushed → {blob_key}")
                return True
            else:
                print(f"[netlify_reporter] ❌  Upload failed: {up_resp.status_code} {up_resp.text[:200]}")
                return False
        else:
            # Try direct PUT as fallback
            raise ValueError(f"Sign request failed: {sign_resp.status_code}")

    except Exception as exc:
        print(f"[netlify_reporter] Trying direct PUT fallback: {exc}")
        # Fallback: direct PUT to the API endpoint
        try:
            put_url = f"https://api.netlify.com/api/v1/sites/{SITE_ID}/blobs/{blob_key}"
            resp = requests.put(
                put_url,
                headers={
                    "Authorization": f"Bearer {TOKEN}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(payload),
                timeout=15,
            )
            print(f"[netlify_reporter] Direct PUT: {resp.status_code} {resp.text[:300]}")
            if resp.ok:
                print(f"[netlify_reporter] ✅  Results pushed → {blob_key}")
                return True
            else:
                print(f"[netlify_reporter] ❌  Direct PUT failed: {resp.status_code}")
                return False
        except Exception as exc2:
            print(f"[netlify_reporter] ❌  All methods failed: {exc2}")
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