"""
equip_base.py
Shared helpers for TC-01 through TC-22 Equipment Management tests.
No special Unicode characters - ASCII only for Windows compatibility.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from playwright.async_api import Page, async_playwright

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
BASE_URL = "https://qa.wasteapplications.com"

TODAY      = datetime.today()
DATE_TODAY = TODAY.strftime("%m/%d/%Y")
DATE_START = TODAY.replace(day=1).strftime("%m/%d/%Y")
DATE_END   = TODAY.strftime("%m/%d/%Y")

# Known test jobsite with equipment on it
KNOWN_JOBSITE_ID = "11821"

# Equipment Management page tiles and their nav paths
EQUIP_TILES = {
    "overview":           "Overview",
    "generate_removed":   "Generate Usage - Removed Equipment",
    "generate_monthly":   "Generate Usage - Monthly",
    "posted_usage":       "Posted Usage",
}


# ============================================================
# Result type
# ============================================================

@dataclass
class TestResult:
    test_id: str
    title: str
    passed: bool = False
    failure_reasons: list = field(default_factory=list)
    evidence: list = field(default_factory=list)

    def log(self, msg):
        self.evidence.append(msg)
        print(f"  LOG: {msg}")

    def fail(self, reason):
        self.failure_reasons.append(reason)
        print(f"  FAIL: {reason}")

    def ok(self, label):
        print(f"  OK: {label}")

    def print_report(self):
        print("\n" + "="*65)
        print(f"  {self.test_id} -- {self.title}")
        print("-"*65)
        if self.passed:
            print("  VERDICT: PASS")
        else:
            print("  VERDICT: FAIL")
            for r in self.failure_reasons:
                print(f"    * {r}")
        if self.evidence:
            print("-"*65)
            for e in self.evidence:
                print(f"    {e}")
        print("="*65)


# ============================================================
# JS helpers -- all plain strings, no special characters
# ============================================================

FIND_INPUT_JS = (
    "(labelText) => {"
    "  const text = labelText.trim();"
    "  for (const inp of document.querySelectorAll('input[aria-labelledby]')) {"
    "    const labelEl = document.getElementById(inp.getAttribute('aria-labelledby'));"
    "    if (labelEl && labelEl.textContent.trim() === text) return inp;"
    "  }"
    "  for (const label of document.querySelectorAll('label[for]')) {"
    "    if (label.textContent.trim() === text) {"
    "      const inp = document.getElementById(label.getAttribute('for'));"
    "      if (inp) return inp;"
    "    }"
    "  }"
    "  const bare = text.replace(/\\s*\\*\\s*$/, '').trim();"
    "  for (const inp of document.querySelectorAll('input[aria-labelledby]')) {"
    "    const labelEl = document.getElementById(inp.getAttribute('aria-labelledby'));"
    "    if (labelEl && labelEl.textContent.trim().replace(/\\s*\\*\\s*$/, '') === bare) return inp;"
    "  }"
    "  for (const label of document.querySelectorAll('label[for]')) {"
    "    if (label.textContent.trim().replace(/\\s*\\*\\s*$/, '') === bare) {"
    "      const inp = document.getElementById(label.getAttribute('for'));"
    "      if (inp) return inp;"
    "    }"
    "  }"
    "  return null;"
    "}"
)


async def get_text_blocks(page: Page) -> list:
    return await page.evaluate(
        "() => {"
        "  const seen = new Set(), out = [];"
        "  for (const el of document.querySelectorAll('p,span,div,td,th,h1,h2,h3,h4,li,label,strong,b,a')) {"
        "    const t = el.textContent.trim().replace(/\\s+/g,' ');"
        "    if (t.length >= 2 && t.length <= 400 && !seen.has(t)) { seen.add(t); out.push(t); }"
        "  }"
        "  return out.slice(0,200);"
        "}"
    )


async def dismiss_popups(page: Page) -> None:
    try:
        await page.evaluate(
            "() => {"
            "  var d = document.querySelector('.e-dlg-overlay');"
            "  if (d && d.offsetParent !== null) {"
            "    var c = document.querySelector('.e-footer-content button');"
            "    if (c) c.click(); else d.click();"
            "  }"
            "}"
        )
        await page.wait_for_timeout(400)
    except Exception:
        pass
    try:
        n = await page.evaluate(
            "() => document.querySelectorAll('.e-popup-open').length"
        )
        if n > 0:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)
    except Exception:
        pass


async def wait_spinners(page: Page, timeout: int = 20000) -> None:
    try:
        await page.wait_for_function(
            "() => document.querySelectorAll('.e-spin-show').length === 0",
            timeout=timeout,
        )
    except Exception:
        pass


async def grid_row_count(page: Page) -> int:
    return await page.evaluate(
        "() => document.querySelectorAll('.e-gridcontent .e-row, table tbody tr.e-row').length"
    )


async def grid_rows_text(page: Page) -> list:
    return await page.evaluate(
        "() => Array.from(document.querySelectorAll('.e-gridcontent .e-row, table tbody tr.e-row'))"
        ".map(r => r.textContent.trim().replace(/\\s+/g,' '))"
    )


async def fill_label(page: Page, label: str, value: str, name: str = "") -> None:
    el = await page.evaluate_handle(FIND_INPUT_JS, label)
    as_el = el.as_element()
    if not as_el:
        raise RuntimeError(f"Input not found: {label}")
    await page.evaluate("el => el.scrollIntoView({block:'center'})", as_el)
    await page.wait_for_timeout(150)
    await page.evaluate(
        "([el,val]) => {"
        "  el.focus(); el.value='';"
        "  el.dispatchEvent(new Event('input',{bubbles:true}));"
        "  el.value=val;"
        "  el.dispatchEvent(new Event('input',{bubbles:true}));"
        "  el.dispatchEvent(new Event('change',{bubbles:true}));"
        "}",
        [as_el, value],
    )
    await page.wait_for_timeout(200)
    print(f"  OK {name or label} = {value}")


async def fill_dropdown(page: Page, label: str, value: str, name: str = "") -> None:
    el = await page.evaluate_handle(FIND_INPUT_JS, label)
    as_el = el.as_element()
    if not as_el:
        raise RuntimeError(f"Dropdown not found: {label}")
    await page.evaluate(
        "el => {"
        "  const t = el.closest('[role=\"combobox\"]') || el.parentElement || el;"
        "  t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
        "  t.dispatchEvent(new MouseEvent('click',{bubbles:true}));"
        "  el.focus();"
        "}",
        as_el,
    )
    await page.wait_for_timeout(400)
    await page.keyboard.type(value, delay=100)
    await page.wait_for_timeout(700)
    await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(300)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(400)
    print(f"  OK {name or label} = {value}")


async def fill_date(page: Page, label: str, value: str, name: str = "") -> None:
    el = await page.evaluate_handle(FIND_INPUT_JS, label)
    as_el = el.as_element()
    if not as_el:
        dp = page.locator("input.e-datepicker").first
        if await dp.count() > 0:
            as_el = await dp.element_handle()
        else:
            raise RuntimeError(f"DatePicker not found: {label}")
    await page.evaluate("el => { el.focus(); el.click(); }", as_el)
    await page.wait_for_timeout(200)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.type(value, delay=80)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    print(f"  OK {name or label} = {value}")


async def search_grid(page: Page, query: str) -> None:
    await dismiss_popups(page)
    await page.wait_for_timeout(300)
    search = page.locator("input[placeholder*='Search' i], input.search-input").first
    await search.wait_for(state="visible", timeout=8000)
    hdl = await search.element_handle()
    await page.evaluate(
        "([el,q]) => {"
        "  el.focus(); el.value=q;"
        "  el.dispatchEvent(new Event('input',{bubbles:true}));"
        "  el.dispatchEvent(new Event('change',{bubbles:true}));"
        "}",
        [hdl, query],
    )
    await page.wait_for_timeout(1200)
    await wait_spinners(page)
    print(f"  OK searched: {query}")


# ============================================================
# Login
# ============================================================

async def do_login(page: Page) -> None:
    print("Logging in...")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
    for sel in [
        "input[placeholder='Email Address']", "#signInName",
        "input[name='signInName']", "input[type='email']", "input[type='text']",
    ]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=20000)
            await loc.fill(VALID_EMAIL)
            await page.keyboard.press("Tab")
            print("  OK email entered")
            break
        except Exception:
            continue
    await page.wait_for_timeout(300)
    for sel in ["input[placeholder='Password']", "#password", "input[type='password']"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.fill(VALID_PASSWORD)
            break
    await page.wait_for_timeout(300)
    await page.locator("button[type='submit'][id='next']").click()
    await page.wait_for_url(re.compile(r"wasteapplications\.com"), timeout=30000)
    await page.wait_for_load_state("networkidle", timeout=20000)
    print(f"  OK logged in -- {page.url}")


# ============================================================
# Navigation
# ============================================================

async def _wait_nav(page: Page) -> None:
    await page.wait_for_function(
        "() => Array.from(document.querySelectorAll('button,a,span,li'))"
        ".some(el => el.offsetParent!==null && el.textContent.trim().length>1)",
        timeout=30000,
    )


async def _click_nav(page: Page, *labels) -> None:
    for label in labels:
        for sel in [
            f"span:has-text('{label}')", f"button:has-text('{label}')",
            f"a:has-text('{label}')",    f"li:has-text('{label}')",
        ]:
            loc = page.locator(sel).first
            try:
                await loc.wait_for(state="visible", timeout=4000)
                await loc.click()
                print(f"  OK clicked: {label}")
                return
            except Exception:
                continue
    raise RuntimeError(f"Could not click nav item: {labels}")


async def nav_to_equipment_management(page: Page) -> None:
    """Navigate to the Equipment Management landing page."""
    print("Navigating to Equipment Management...")
    await dismiss_popups(page)
    await _wait_nav(page)
    await _click_nav(page, "Accounting")
    await page.wait_for_timeout(800)
    await _click_nav(page, "Equipment Management", "Equipment")
    await page.wait_for_function(
        "() => !window.location.href.endsWith('/home')"
        " && document.querySelectorAll('.e-control, h1, h2').length > 0",
        timeout=25000,
    )
    await wait_spinners(page)
    await page.wait_for_timeout(600)
    print(f"  OK Equipment Management -- {page.url}")


async def click_tile(page: Page, tile_name: str) -> None:
    """Click one of the four tiles on the Equipment Management page."""
    for sel in [
        f"h2:has-text('{tile_name}')", f"h3:has-text('{tile_name}')",
        f"div:has-text('{tile_name}')", f"span:has-text('{tile_name}')",
        f"a:has-text('{tile_name}')",   f"button:has-text('{tile_name}')",
    ]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=5000)
            await loc.click()
            print(f"  OK tile clicked: {tile_name}")
            await wait_spinners(page)
            await page.wait_for_timeout(800)
            return
        except Exception:
            continue
    # JS fallback
    clicked = await page.evaluate(
        f"() => {{"
        f"  for (const el of document.querySelectorAll('*')) {{"
        f"    if (el.textContent.trim() === '{tile_name}' && el.offsetParent !== null) {{"
        f"      el.click(); return true;"
        f"    }}"
        f"  }}"
        f"  return false;"
        f"}}"
    )
    if not clicked:
        raise RuntimeError(f"Tile not found: {tile_name}")
    await wait_spinners(page)
    await page.wait_for_timeout(800)
    print(f"  OK tile clicked via JS: {tile_name}")


async def nav_to_jobsite_service_orders(page: Page, jobsite_id: str) -> None:
    """Navigate to a jobsite's service orders / delivery tab."""
    await _wait_nav(page)
    await _click_nav(page, "Management")
    await page.wait_for_timeout(800)
    await _click_nav(page, "Jobsites", "Jobsite")
    await page.wait_for_function(
        "() => !window.location.href.endsWith('/home')"
        " && document.querySelectorAll('.e-grid,.e-control').length > 0",
        timeout=25000,
    )
    await wait_spinners(page)
    # Open the jobsite
    link = page.locator(f"a:has-text('{jobsite_id}')").first
    try:
        await link.wait_for(state="visible", timeout=6000)
    except Exception:
        await search_grid(page, jobsite_id)
        link = page.locator(f"a:has-text('{jobsite_id}')").first
        await link.wait_for(state="visible", timeout=6000)
    await link.click()
    await wait_spinners(page)
    await page.wait_for_timeout(800)
    print(f"  OK jobsite {jobsite_id} opened")


async def click_btn(page: Page, *labels) -> bool:
    """Click the first visible button matching any label. Returns True if clicked."""
    for label in labels:
        for sel in [
            f"button:has-text('{label}')", f"a:has-text('{label}')",
            f"span:has-text('{label}')",
        ]:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(500)
                print(f"  OK button: {label}")
                return True
    return False
