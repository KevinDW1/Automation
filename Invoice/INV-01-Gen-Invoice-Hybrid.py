import asyncio, re, json
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

VALID_EMAIL    = "kevin.clarke@wasteapplications.com"
VALID_PASSWORD = "Tuesday19@@@@"
APP_URL  = "https://wa.dw1.com"
API_BASE = "https://dw1-overcast-central-api.azurewebsites.net"
TODAY      = datetime.today()
DATE_END   = TODAY.strftime("%Y-%m-%d")
DATE_START = (TODAY - timedelta(days=30)).strftime("%Y-%m-%d")
DATE_TODAY = TODAY.strftime("%Y-%m-%d")

async def main():
    print(f"\n{'='*65}\n  INV-01 HYBRID  {DATE_START}->{DATE_END}\n{'='*65}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width":1920,"height":1080},
            record_video_dir="videos/", record_video_size={"width":1920,"height":1080})
        page = await context.new_page()

        api_hdrs = {}
        page.on("request", lambda req: api_hdrs.update(dict(req.headers))
            if "dw1-overcast-central-api" in req.url
            and dict(req.headers).get("authorization","").startswith("Bearer ") else None)

        # Login
        print("\n[STEP 1] Login")
        await page.goto(APP_URL, timeout=30000)
        await page.wait_for_timeout(2000)
        for sel in ["input[placeholder='Email Address']","#signInName","input[type='email']","input[type='text']"]:
            loc = page.locator(sel).first
            try:
                await loc.wait_for(state="visible", timeout=8000)
                await loc.fill(VALID_EMAIL); await page.keyboard.press("Tab"); print("  OK email"); break
            except: continue
        await page.wait_for_timeout(500)
        for sel in ["input[placeholder='Password']","#password","input[type='password']"]:
            loc = page.locator(sel).first
            if await loc.count()>0 and await loc.is_visible(): await loc.fill(VALID_PASSWORD); print("  OK password"); break
        await page.wait_for_timeout(500)
        for sel in ["button[type='submit'][id='next']","button[type='submit']"]:
            btn = page.locator(sel).first
            if await btn.count()>0 and await btn.is_visible(): await btn.click(); print("  OK submit"); break
        await page.wait_for_url(re.compile(r"wa\.dw1\.com/home"), timeout=60000)
        try: await page.wait_for_load_state("networkidle", timeout=20000)
        except: pass
        await page.wait_for_timeout(2000)
        print(f"  OK {page.url}")

        # Navigate to generate-invoices to capture headers
        await page.goto(f"{APP_URL}/modules/billing/generate-invoices", timeout=30000)
        try: await page.wait_for_load_state("networkidle", timeout=20000)
        except: pass
        await page.wait_for_timeout(3000)

        token     = api_hdrs.get("authorization","")[7:]
        client_id = api_hdrs.get("oc-selected-client-id","2")
        print(f"  Token len={len(token)}  client_id={client_id}")
        if not token: print("  FAIL no token"); await context.close(); await browser.close(); return

        hdrs = {
            "authorization":         f"Bearer {token}",
            "oc-selected-client-id": client_id,
            "accept":                "application/json",
            "content-type":          "application/json",
            "origin":                APP_URL,
            "referer":               f"{APP_URL}/",
        }

        # Probe billing cycle and billable item endpoints
        print("\n[STEP 2] Probe lookup endpoints")
        cycle_id = None
        item_id  = None
        for path in ["/invoicing/billing-cycles","/billing-cycles","/invoicing/lookup/billing-cycles","/lookup/billing-cycles"]:
            r = await page.request.fetch(f"{API_BASE}{path}", method="GET", headers=hdrs, timeout=10000)
            b = await r.text()
            print(f"  GET {path} -> {r.status} | {b[:80]}")
            if r.status==200 and b.strip().startswith(("[","{")):
                data = json.loads(b)
                items = data if isinstance(data,list) else data.get("data",data.get("items",[]))
                if items: cycle_id = items[0].get("id"); print(f"  cycle_id={cycle_id}"); break

        for path in ["/invoicing/billable-items","/billable-items","/invoicing/lookup/billable-items","/lookup/billable-items"]:
            r = await page.request.fetch(f"{API_BASE}{path}", method="GET", headers=hdrs, timeout=10000)
            b = await r.text()
            print(f"  GET {path} -> {r.status} | {b[:80]}")
            if r.status==200 and b.strip().startswith(("[","{")):
                data = json.loads(b)
                items = data if isinstance(data,list) else data.get("data",data.get("items",[]))
                if items: item_id = items[0].get("id"); print(f"  item_id={item_id}"); break

        # POST generate -- wrapped in "request" object, dates as YYYY-MM-DD
        print("\n[STEP 3] POST generate invoices")
        inner = {
            "startDate":       DATE_START,
            "endDate":         DATE_END,
            "postingDate":     DATE_TODAY,
            "generateBy":      "All",
            "batchNotes":      "INV-01 automated QA",
            "invoiceMessage":  "Thank you for your business!",
            "minInvoiceTotal": 0,
        }
        if cycle_id: inner["billingCycleId"] = cycle_id
        if item_id:  inner["billableItemId"] = item_id
        payload = {"request": inner}
        print(f"  Token BEFORE: {token[:30]}...")
        print(f"  Payload: {json.dumps(payload)}")

        r3 = await page.request.fetch(f"{API_BASE}/invoicing/batches",
            method="POST", headers=hdrs, data=json.dumps(payload), timeout=120000)
        b3 = await r3.text()
        is_json = b3.strip().startswith(("{","["))
        print(f"  HTTP {r3.status} | json={is_json} | {b3[:400]}")
        print(f"  Token AFTER: {token[:30]}...")

        batch_id = None
        if r3.status in (200,201,202) and is_json:
            data = json.loads(b3)
            batch_id = data.get("batchId") or data.get("id") or data.get("batch_id")
            print(f"  OK Generated! batch_id={batch_id}")
        elif r3.status==400 and is_json:
            print(f"  400 validation: {b3}")
        else:
            print(f"  FAIL HTTP {r3.status}")

        # GET verify
        print("\n[STEP 4] GET verify batches")
        r4 = await page.request.fetch(f"{API_BASE}/invoicing/batches", method="GET", headers=hdrs, timeout=15000)
        b4 = await r4.text()
        print(f"  HTTP {r4.status} | {b4[:300]}")

        # UI confirm
        print("\n[STEP 5] UI confirm")
        await page.goto(f"{APP_URL}/modules/billing/generate-invoices", timeout=30000)
        try: await page.wait_for_load_state("networkidle", timeout=20000)
        except: pass
        await page.wait_for_timeout(2000)
        await page.screenshot(path="inv01_result.png")

        verdict = "PASS" if r3.status in (200,201,202) else "FAIL"
        print(f"\n{'='*65}\n  VERDICT: {verdict}  batch_id={batch_id}\n{'='*65}")

        await page.wait_for_timeout(2000)
        await context.close()
        await browser.close()

asyncio.run(main())
