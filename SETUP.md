# Netlify → GitHub Actions Integration — Setup Guide

## What you're getting
After this setup, every time your GitHub Actions workflow runs:
1. Playwright tests execute
2. Results (pass/fail + notes) are automatically pushed to Netlify Blobs
3. Your HTML pages load the updated results on next visit

---

## Files to add to your repo

| File | Where to put it |
|------|----------------|
| `netlify_reporter.py` | Project root (same level as your test folders) |
| `conftest.py` | Project root |
| `smoke-test.yml` | `.github/workflows/smoke-test.yml` |

---

## Step 1 — Get your Netlify Personal Access Token

1. Go to https://app.netlify.com/user/applications
2. Click **New access token**
3. Name it `github-actions-qa`
4. Copy the token (you only see it once)

---

## Step 2 — Get your Netlify Site ID

Run this in PowerShell (you already have netlify CLI linked):
```powershell
netlify status
```
Copy the **Project Id** value — it looks like: `9cdcff74-c8a7-4c23-bfdd-7c474a9620fd`

---

## Step 3 — Add GitHub Secrets

Go to: https://github.com/KevinDW1/Automation/settings/secrets/actions

Add these secrets (New repository secret):

| Secret Name | Value |
|-------------|-------|
| `NETLIFY_TOKEN` | Your personal access token from Step 1 |
| `NETLIFY_SITE_ID` | `9cdcff74-c8a7-4c23-bfdd-7c474a9620fd` |
| `APP_USERNAME` | Your app login username |
| `APP_PASSWORD` | Your app login password |

---

## Step 4 — Update your Customer HTML page

The Customer Management page currently only uses localStorage — not Netlify Blobs.
Update the `saveProgress()` and `loadProgress()` functions to match the
Invoice/Jobsite pages, but use blob key: `customers-qa-results`

---

## Step 5 — Commit and push

```powershell
git add netlify_reporter.py conftest.py .github/workflows/smoke-test.yml
git commit -m "Add Netlify results reporter"
git push origin main
```

This push will trigger the workflow automatically.

---

## How results flow

```
pytest test_cus02 → PASSED
        ↓
conftest.py captures: { "CUS-02": { "status": "passed" } }
        ↓
pytest_sessionfinish fires
        ↓
netlify_reporter.py PUT → Netlify Blobs "customers-qa-results"
        ↓
Customer HTML page loads blob on next visit → shows green ✓
```

---

## Blob key reference

| HTML Page | Blob Key |
|-----------|----------|
| Customer Management | `customers-qa-results` |
| Jobsite Management | `jobsites-qa-results` |
| Invoice Management | `invoices-qa-results` |
| Vendor Management | `vendors-qa-state` |

---

## Verifying it worked

After a workflow run, check the Actions log for lines like:
```
[netlify_reporter] ✅  Results pushed to Netlify Blobs → customers-qa-results
[netlify_reporter] ✅  Results pushed to Netlify Blobs → jobsites-qa-results
```

Then open your Netlify site and the results should be live.
