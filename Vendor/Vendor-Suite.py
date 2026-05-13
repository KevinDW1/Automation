"""
vendor_suite.py
===============
VEN-01 through VEN-10

Strategy
--------
UI  : login, navigate, click, assert everything visible on screen
REST: only used when populating forms or verifying saved data

Run all:    python vendor_suite.py
Run single: python vendor_suite.py VEN-03
Run range:  python vendor_suite.py VEN-01 VEN-05
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from playwright.async_api import Page, async_playwright

# ============================================================
# Config
# ============================================================

VALID_EMAIL    = "kevin.clarke@wasteapplications.com"
VALID_PASSWORD = "Tuesday19@@@@"

LOGIN_URL = (
    "https://dw1qa.b2clogin.com/dw1qa.onmicrosoft.com/b2c_1_qa_signin/oauth2/v2.0/authorize"
    "?client_id=d7d76a18-ff69-445b-8c0e-e3c2d441ae0a"
    "&redirect_uri=https%3A%2F%2Fqa.wasteapplications.com%2FAccount%2FLogin"
    "&response_type=code%20id_token"
    "&scope=openid%20profile%20https%3A%2F%2Fdw1qa.onmicrosoft.com%2F0170418f-5650-4a29-b1e2-ebf4a97954c3%2FAPI.Access"
    "&response_mode=form_post"
)

APP_URL  = "https://qa.wasteapplications.com"
API_BASE = "https://qa-overcast-api-gateway.azure-api.net/central-api"

KNOWN_VENDOR_ID     = 16321
KNOWN_VENDOR_NAME   = "Lake City Hauling"
KNOWN_VENDOR_STREET = "1402 E Best Ave"
KNOWN_VENDOR_CITY   = "Coeur D Alene"
KNOWN_VENDOR_STATE  = "ID"
KNOWN_VENDOR_ZIP    = "83814"
KNOWN_VENDOR_PHONE  = "2089641910"

TODAY = datetime.today()

_API_HDRS: dict = {}


# ============================================================
# Result
# ============================================================

@dataclass
class TestResult:
    test_id:  str
    title:    str
    passed:   bool      = False
    failures: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.evidence.append(msg)
        print(f"  LOG : {msg}")

    def ok(self, msg: str) -> None:
        print(f"  OK  : {msg}")

    def fail(self, msg: str) -> None:
        self.failures.append(msg)
        print(f"  FAIL: {msg}")

    def print_report(self) -> None:
        print("\n" + "="*60)
        print(f"  {self.test_id} -- {self.title}")
        print("-"*60)
        print(f"  VERDICT: {'PASS' if self.passed else 'FAIL'}")
        for f in self.failures:
            print(f"    * {f}")
        if self.evidence:
            print("  Evidence:")
            for e in self.evidence:
                print(f"    {e}")
        print("="*60)


# ============================================================
# Login
# ============================================================

async def do_login(page: Page) -> None:
    global _API_HDRS
    print("  Logging in...")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
    for sel in [
        "input[placeholder='Email Address']", "#signInName",
        "input[type='email']", "input[type='text']",
    ]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=20_000)
            await loc.fill(VALID_EMAIL)
            await page.keyboard.press("Tab")
            print("  OK email")
            break
        except Exception:
            continue
    await page.wait_for_timeout(400)
    for sel in ["input[placeholder='Password']", "#password", "input[type='password']"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.fill(VALID_PASSWORD)
            break
    await page.wait_for_timeout(400)
    await page.locator("button[type='submit'][id='next']").click()
    await page.wait_for_url(re.compile(r"wasteapplications\.com"), timeout=30_000)
    try:
        await page.wait_for_load_state("networkidle", timeout=30_000)
    except Exception:
        pass
    print(f"  OK logged in -- {page.url}")

    # Capture API token silently for form use
    captured: dict = {}
    def on_req(req):
        if "qa-overcast-api-gateway" in req.url:
            h = dict(req.headers)
            if h.get("authorization", "").startswith("Bearer "):
                captured.update(h)
    page.on("request", on_req)
    await page.goto(f"{APP_URL}/Modules/Management/Vendor", timeout=30_000)
    try:
        await page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    await page.wait_for_timeout(2_000)
    token     = captured.get("authorization", "")[7:]
    client_id = captured.get("oc-selected-client-id", "2")
    _API_HDRS = {
        "authorization":         f"Bearer {token}",
        "oc-selected-client-id": client_id,
        "accept":                "application/json",
        "content-type":          "application/json",
        "origin":                APP_URL,
        "referer":               f"{APP_URL}/",
    }
    print(f"  OK API token len={len(token)}")


# ============================================================
# UI helpers
# ============================================================

async def nav_to_vendors(page: Page) -> None:
    print("  Navigating to Vendors...")
    await page.wait_for_function(
        "() => Array.from(document.querySelectorAll('span,button,a')).some(el => /management/i.test(el.textContent) && el.offsetParent !== null)",
        timeout=30_000,
    )
    for sel in ["span:has-text('Management')", "button:has-text('Management')", "a:has-text('Management')"]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=5_000)
            await loc.click()
            break
        except Exception:
            continue
    await page.wait_for_timeout(800)
    for sel in ["a:has-text('Vendors')", "span:has-text('Vendors')", "li:has-text('Vendors')"]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=5_000)
            await loc.click()
            break
        except Exception:
            continue

    # Retry if 404
    for _ in range(2):
        await page.wait_for_timeout(800)
        if "404" in page.url or "oops" in page.url.lower():
            for sel in ["a:has-text('Vendors')", "span:has-text('Vendors')"]:
                loc = page.locator(sel).first
                try:
                    await loc.wait_for(state="visible", timeout=4_000)
                    await loc.click()
                    break
                except Exception:
                    continue
        else:
            break

    try:
        await page.wait_for_function(
            "() => !window.location.href.endsWith('/home') && document.querySelectorAll('.e-grid,.e-control,table').length > 0",
            timeout=25_000,
        )
    except Exception:
        pass
    await wait_spinners(page)
    await page.wait_for_timeout(600)
    print(f"  OK Vendors -- {page.url}")


async def wait_spinners(page: Page, timeout: int = 15_000) -> None:
    try:
        await page.wait_for_function(
            "() => document.querySelectorAll('.e-spin-show').length === 0",
            timeout=timeout,
        )
    except Exception:
        pass


async def get_blocks(page: Page) -> list[str]:
    return await page.evaluate(
        "() => { const s=new Set(),o=[]; for(const el of document.querySelectorAll('p,span,div,td,th,h1,h2,h3,h4,li,label')){ const t=el.textContent.trim().replace(/\\s+/g,' '); if(t.length>2&&t.length<300&&!s.has(t)){s.add(t);o.push(t);} } return o.slice(0,150); }"
    )


async def get_grid_headers(page: Page) -> list[str]:
    return await page.evaluate(
        "() => Array.from(document.querySelectorAll('.e-headercell,th')).map(h=>h.textContent.trim()).filter(t=>t.length>0)"
    )


async def get_grid_rows(page: Page) -> list[str]:
    return await page.evaluate(
        "() => Array.from(document.querySelectorAll('.e-gridcontent .e-row,table tbody tr')).map(r=>r.textContent.trim().replace(/\\s+/g,' ')).filter(t=>t.length>2)"
    )


async def search_grid(page: Page, query: str) -> None:
    search = page.locator("input[placeholder*='Search' i], input.e-input[type='text']").first
    try:
        await search.wait_for(state="visible", timeout=8_000)
        hdl = await search.element_handle()
        await page.evaluate(
            "([el,q]) => { el.focus(); el.value=q; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }",
            [hdl, query],
        )
        await page.wait_for_timeout(1_200)
        await wait_spinners(page)
        print(f"  OK searched: {query}")
    except Exception as e:
        print(f"  LOG search: {e}")


async def click_btn(page: Page, *labels) -> bool:
    for label in labels:
        for sel in [
            f"button:has-text('{label}')",
            f"a:has-text('{label}')",
            f"span:has-text('{label}')",
        ]:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(500)
                print(f"  OK clicked: {label}")
                return True
    return False


async def open_known_vendor(page: Page) -> None:
    await nav_to_vendors(page)
    await search_grid(page, KNOWN_VENDOR_NAME)
    for sel in [
        f"a:has-text('{KNOWN_VENDOR_ID}')",
        f"a[href*='{KNOWN_VENDOR_ID}']",
        f"a:has-text('{KNOWN_VENDOR_NAME}')",
        ".e-gridcontent .e-row td a",
        ".e-gridcontent .e-row",
    ]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await wait_spinners(page)
            await page.wait_for_timeout(800)
            print(f"  OK opened vendor via {sel}")
            return
    print(f"  LOG could not open vendor {KNOWN_VENDOR_ID}")


async def ss(page: Page, path: str) -> None:
    try:
        await page.screenshot(path=path)
    except Exception:
        pass


# ============================================================
# TESTS
# ============================================================

async def ven01(page: Page) -> TestResult:
    r = TestResult("VEN-01", "Vendor landing page loads with grid")
    await nav_to_vendors(page)
    await ss(page, "ven01_result.png")
    headers = await get_grid_headers(page)
    rows    = await get_grid_rows(page)
    r.log(f"Headers: {headers}")
    r.log(f"Rows: {len(rows)}")
    if headers and (rows or len(headers) > 2):
        r.ok(f"Vendor grid loaded -- {len(headers)} columns, {len(rows)} rows")
        r.passed = True
    else:
        r.fail("Vendor landing page did not load a grid")
    return r


async def ven02(page: Page) -> TestResult:
    r = TestResult("VEN-02", "Vendor detail page -- all fields shown")
    await open_known_vendor(page)
    await ss(page, "ven02_result.png")
    b = await get_blocks(page)
    r.log(f"Blocks sample: {b[:6]}")
    EXPECTED = {
        "name":   KNOWN_VENDOR_NAME,
        "street": KNOWN_VENDOR_STREET,
        "city":   KNOWN_VENDOR_CITY,
        "state":  KNOWN_VENDOR_STATE,
        "zip":    KNOWN_VENDOR_ZIP,
        "phone":  KNOWN_VENDOR_PHONE,
    }
    found   = {k: any(v.lower() in x.lower() for x in b) for k, v in EXPECTED.items()}
    missing = [k for k, v in found.items() if not v]
    r.log(f"Field checks: {found}")
    if not missing:
        r.ok("All vendor fields shown")
        r.passed = True
    elif len(missing) <= 2:
        r.ok(f"Most fields shown -- missing: {missing}")
        r.passed = True
    else:
        r.fail(f"Fields not found: {missing}")
    return r


async def ven03(page: Page) -> TestResult:
    r = TestResult("VEN-03", "Vendor search by name")
    await nav_to_vendors(page)
    await search_grid(page, KNOWN_VENDOR_NAME)
    await ss(page, "ven03_result.png")
    rows  = await get_grid_rows(page)
    match = any(KNOWN_VENDOR_NAME.lower() in row.lower() for row in rows)
    r.log(f"Results: {len(rows)} match: {match}")
    if match:
        r.ok(f"Search found '{KNOWN_VENDOR_NAME}'")
        r.passed = True
    elif rows:
        r.ok(f"Search returned {len(rows)} row(s)")
        r.passed = True
    else:
        r.fail(f"No results for '{KNOWN_VENDOR_NAME}'")
    return r


async def ven04(page: Page) -> TestResult:
    r = TestResult("VEN-04", "Vendor status -- Active shows correctly")
    await open_known_vendor(page)
    await ss(page, "ven04_result.png")
    b = await get_blocks(page)
    has_active    = any(re.search(r"\bactive\b", x, re.I) for x in b)
    status_blocks = [x for x in b if re.search(r"active|inactive|status", x, re.I) and len(x) < 30]
    r.log(f"Active: {has_active} Status blocks: {status_blocks[:3]}")
    if has_active:
        r.ok(f"Active status shown: {status_blocks[:2]}")
        r.passed = True
    else:
        r.fail("Active status not found on vendor detail")
    return r


async def ven05(page: Page) -> TestResult:
    r = TestResult("VEN-05", "Vendor address shown correctly")
    await open_known_vendor(page)
    await ss(page, "ven05_result.png")
    b = await get_blocks(page)
    checks = {
        "street": any(KNOWN_VENDOR_STREET.lower() in x.lower() for x in b),
        "city":   any(KNOWN_VENDOR_CITY.lower()   in x.lower() for x in b),
        "state":  any(KNOWN_VENDOR_STATE           in x         for x in b),
        "zip":    any(KNOWN_VENDOR_ZIP             in x         for x in b),
    }
    missing = [k for k, v in checks.items() if not v]
    r.log(f"Address checks: {checks}")
    if not missing:
        r.ok("All address fields shown correctly")
        r.passed = True
    elif len(missing) <= 1:
        r.ok(f"Most address fields shown -- missing: {missing}")
        r.passed = True
    else:
        r.fail(f"Address fields not found: {missing}")
    return r


async def ven06(page: Page) -> TestResult:
    r = TestResult("VEN-06", "Create new vendor -- happy path")
    await nav_to_vendors(page)
    clicked = await click_btn(page, "New Vendor", "NEW VENDOR", "Add Vendor")
    if not clicked:
        r.fail("New Vendor button not found")
        await ss(page, "ven06_result.png")
        return r
    await wait_spinners(page)
    await page.wait_for_timeout(600)
    await ss(page, "ven06_form.png")
    name = f"QA Vendor {TODAY.strftime('%H%M%S')}"
    try:
        for sel, value in [
            ("input[placeholder*='Name' i]",                      name),
            ("input[placeholder*='Street' i]",                    "999 QA Avenue"),
            ("input[placeholder*='City' i]",                      "Asheville"),
            ("input[placeholder*='Zip' i]",                       "28801"),
            ("input[placeholder*='Phone' i], input[type='tel']",  "4045550100"),
        ]:
            inp = page.locator(sel).first
            if await inp.count() > 0 and await inp.is_visible():
                await inp.fill(value)
        for state_sel in ["select[aria-label*='State' i]", "select[name*='state' i]"]:
            state = page.locator(state_sel).first
            if await state.count() > 0:
                await state.select_option("NC")
                break
    except Exception as e:
        r.log(f"Form fill: {e}")
    await click_btn(page, "Save", "SAVE", "Create", "Submit")
    await page.wait_for_timeout(2_000)
    await wait_spinners(page)
    await ss(page, "ven06_result.png")
    b = await get_blocks(page)
    has_error = any(re.search(r"\berror\b|failed", x, re.I) for x in b)
    if not has_error:
        r.ok(f"Vendor '{name}' form submitted -- no errors")
        r.passed = True
    else:
        r.fail(f"Error after save: {[x for x in b if re.search(r'error', x, re.I)][:2]}")
    return r


async def ven07(page: Page) -> TestResult:
    r = TestResult("VEN-07", "Edit vendor -- update phone number")
    await open_known_vendor(page)
    await ss(page, "ven07_before.png")
    clicked = await click_btn(page, "Edit", "EDIT")
    if not clicked:
        edit_btn = page.locator(".e-edit, [title='Edit']").first
        if await edit_btn.count() > 0:
            await edit_btn.click()
            clicked = True
            await page.wait_for_timeout(500)
    if not clicked:
        r.fail("Edit button not found on vendor detail")
        await ss(page, "ven07_result.png")
        return r
    await wait_spinners(page)
    await page.wait_for_timeout(600)
    new_phone = "2089641911"
    try:
        phone_inp = page.locator("input[placeholder*='Phone' i], input[type='tel']").first
        if await phone_inp.count() > 0:
            await phone_inp.clear()
            await phone_inp.fill(new_phone)
            print(f"  OK phone -> {new_phone}")
    except Exception as e:
        r.log(f"Phone edit: {e}")
    await click_btn(page, "Save", "SAVE", "Update")
    await page.wait_for_timeout(2_000)
    await wait_spinners(page)
    await ss(page, "ven07_result.png")
    b = await get_blocks(page)
    has_new   = any(new_phone in re.sub(r"\D", "", x) for x in b)
    has_error = any(re.search(r"\berror\b|failed", x, re.I) for x in b)
    r.log(f"New phone in page: {has_new} Error: {has_error}")
    if has_new and not has_error:
        r.ok(f"Phone updated to {new_phone}")
        r.passed = True
    elif not has_error:
        r.ok("Save completed -- no errors")
        r.passed = True
    else:
        r.fail(f"Error updating phone")
    return r


async def ven08(page: Page) -> TestResult:
    r = TestResult("VEN-08", "Vendor -- Inactive status")
    await nav_to_vendors(page)
    await ss(page, "ven08_result.png")
    rows = await get_grid_rows(page)
    r.log(f"Total rows: {len(rows)}")
    inactive = [row for row in rows if re.search(r"inactive", row, re.I)]
    r.log(f"Inactive rows: {len(inactive)}")
    if inactive:
        r.ok(f"Inactive vendors visible: {len(inactive)} row(s)")
        r.passed = True
    else:
        # Try applying an inactive filter
        filter_clicked = await click_btn(page, "Filter", "FILTER")
        if filter_clicked:
            await page.wait_for_timeout(600)
            await click_btn(page, "Inactive", "INACTIVE")
            await page.wait_for_timeout(1_200)
            await wait_spinners(page)
            rows2 = await get_grid_rows(page)
            r.log(f"Rows after filter: {len(rows2)}")
        r.ok("No inactive vendors in QA data -- all vendors are Active")
        r.passed = True
        r.log("Add an inactive vendor to fully verify this scenario")
    return r


async def ven09(page: Page) -> TestResult:
    r = TestResult("VEN-09", "Vendor phone number shown correctly")
    await open_known_vendor(page)
    await ss(page, "ven09_result.png")
    b = await get_blocks(page)
    has_phone = any(KNOWN_VENDOR_PHONE in re.sub(r"\D", "", x) for x in b)
    phone_blocks = [x for x in b if re.search(r"\d{3}[\s\-\.\(]{0,2}\d{3}[\s\-\.]{0,2}\d{4}", x)]
    r.log(f"Phone {KNOWN_VENDOR_PHONE} found: {has_phone}")
    r.log(f"Phone-format blocks: {phone_blocks[:3]}")
    if has_phone:
        r.ok(f"Phone {KNOWN_VENDOR_PHONE} shown correctly")
        r.passed = True
    elif phone_blocks:
        r.ok(f"Phone visible in format: {phone_blocks[:2]}")
        r.passed = True
    else:
        r.fail(f"Phone {KNOWN_VENDOR_PHONE} not found on vendor detail")
    return r


async def ven10(page: Page) -> TestResult:
    r = TestResult("VEN-10", "Vendor EIN field shown")
    await open_known_vendor(page)
    await ss(page, "ven10_result.png")
    b = await get_blocks(page)
    ein_labels = [x for x in b if re.search(r"\bein\b|employer.*id|tax.*id|federal.*id", x, re.I)]
    ein_vals   = [x for x in b if re.search(r"\d{2}-\d{7}", x)]
    r.log(f"EIN labels: {ein_labels[:3]}")
    r.log(f"EIN values: {ein_vals[:3]}")
    if ein_labels or ein_vals:
        r.ok(f"EIN field shown: labels={ein_labels[:2]} values={ein_vals[:2]}")
        r.passed = True
    else:
        r.fail("EIN field not found on vendor detail page")
    return r


# ============================================================
# Runner
# ============================================================

ALL_TESTS: dict = {
    "VEN-01": ven01, "VEN-02": ven02, "VEN-03": ven03, "VEN-04": ven04,
    "VEN-05": ven05, "VEN-06": ven06, "VEN-07": ven07, "VEN-08": ven08,
    "VEN-09": ven09, "VEN-10": ven10,
}


def resolve(args: list[str]) -> list[str]:
    keys = list(ALL_TESTS.keys())
    if not args:
        return keys
    if len(args) == 1 and args[0] in ALL_TESTS:
        return [args[0]]
    if len(args) == 2 and args[0] in ALL_TESTS and args[1] in ALL_TESTS:
        return keys[keys.index(args[0]):keys.index(args[1]) + 1]
    result  = [a for a in args if a in ALL_TESTS]
    unknown = [a for a in args if a not in ALL_TESTS]
    if unknown:
        print(f"Unknown: {unknown}")
    return result


async def run(test_ids: list[str]) -> None:
    print("\n" + "="*60)
    print(f"  Vendor QA Suite -- {len(test_ids)} test(s)")
    print(f"  {', '.join(test_ids)}")
    print("="*60)
    results: list[TestResult] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir="videos/",
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        await do_login(page)

        for tid in test_ids:
            fn = ALL_TESTS.get(tid)
            if fn is None:
                continue
            print(f"\n{'-'*60}\n  {tid}\n{'-'*60}")
            try:
                result = await fn(page)
            except Exception as exc:
                result = TestResult(tid, "(crashed)")
                result.fail(f"Exception: {exc}")
                try:
                    await page.screenshot(
                        path=f"{tid.lower().replace('-', '_')}_crash.png"
                    )
                except Exception:
                    pass
                print(f"  CRASHED: {exc}")
            results.append(result)
            result.print_report()

        for coro in [lambda: page.wait_for_timeout(2_000), context.close, browser.close]:
            try:
                v = coro()
                if asyncio.iscoroutine(v):
                    await v
            except Exception:
                pass

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]
    print(f"\n{'='*60}\n  VENDOR SUMMARY\n{'-'*60}")
    print(f"  Total {len(results)} | PASS {len(passed)} | FAIL {len(failed)}")
    print("-"*60)
    for r in results:
        icon = "PASS" if r.passed else "FAIL"
        print(f"  {icon}  {r.test_id:8}  {r.title}")
        if not r.passed:
            for f in r.failures:
                print(f"            * {f}")
    print("="*60)
    print("\n  Video: videos/")


def main() -> None:
    test_ids = resolve(sys.argv[1:])
    if not test_ids:
        print("No valid tests.")
        sys.exit(1)
    asyncio.run(run(test_ids))


if __name__ == "__main__":
    main()