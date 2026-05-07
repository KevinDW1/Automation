import asyncio, re
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width":1920,"height":1080})
        page = await context.new_page()

        # Intercept all requests to find the login URL for wa.dw1.com
        api_headers = {}
        def on_request(req):
            if "dw1-overcast-central-api" in req.url:
                hdrs = dict(req.headers)
                if hdrs.get("authorization","").startswith("Bearer "):
                    api_headers.update(hdrs)
                    print(f"  CAPTURED: {req.url[:80]}")
        page.on("request", on_request)

        # Go directly to wa.dw1.com -- let it redirect to its own login
        print("Navigating to wa.dw1.com...")
        await page.goto("https://wa.dw1.com", timeout=30000)
        await page.wait_for_timeout(3000)
        print(f"Landed on: {page.url}")

        # Fill login if redirected to B2C
        for sel in ["input[placeholder='Email Address']","#signInName","input[type='email']","input[type='text']"]:
            loc = page.locator(sel).first
            try:
                await loc.wait_for(state="visible", timeout=5000)
                await loc.fill("kevin.clarke@wasteapplications.com")
                await page.keyboard.press("Tab")
                print("OK email entered")
                break
            except: continue

        await page.wait_for_timeout(300)
        for sel in ["input[placeholder='Password']","#password","input[type='password']"]:
            loc = page.locator(sel).first
            if await loc.count()>0 and await loc.is_visible():
                await loc.fill("Tuesday19@@@@"); break

        await page.wait_for_timeout(300)
        try:
            await page.locator("button[type='submit'][id='next']").click()
        except:
            await page.locator("button[type='submit']").first.click()

        await page.wait_for_timeout(5000)
        print(f"After login: {page.url}")

        # Navigate to generate-invoices
        await page.goto("https://wa.dw1.com/modules/billing/generate-invoices", timeout=30000)
        try: await page.wait_for_load_state("networkidle", timeout=20000)
        except: pass
        await page.wait_for_timeout(3000)

        print(f"\nAPI headers captured: {list(api_headers.keys())}")
        if api_headers:
            print(f"Token: {api_headers.get('authorization','')[:50]}...")
            print(f"oc-selected-client-id: {api_headers.get('oc-selected-client-id','NOT FOUND')}")

        await page.wait_for_timeout(3000)
        await context.close()
        await browser.close()

asyncio.run(main())
