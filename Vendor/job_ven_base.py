import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from playwright.async_api import Page, async_playwright
from faker import Faker
fake = Faker()

VALID_EMAIL = "kevin.clarke@wasteapplications.com"
VALID_PASSWORD = "Tuesday19@@@@"
LOGIN_URL = ("https://dw1qa.b2clogin.com/dw1qa.onmicrosoft.com/b2c_1_qa_signin/oauth2/v2.0/authorize?client_id=d7d76a18-ff69-445b-8c0e-e3c2d441ae0a&redirect_uri=https%3A%2F%2Fqa.wasteapplications.com%2FAccount%2FLogin&response_type=code%20id_token&scope=openid%20profile%20https%3A%2F%2Fdw1qa.onmicrosoft.com%2F0170418f-5650-4a29-b1e2-ebf4a97954c3%2FAPI.Access&response_mode=form_post")
BASE_URL = "https://qa.wasteapplications.com"

KNOWN_JOBSITE = {"id": "1627", "name": "Test Jobsite QA", "customer": "1627", "tax_rate": 9.0}
KNOWN_VENDOR  = {"id": "16321", "name": "Lake City Hauling", "status": "Active", "street": "1402 E Best Ave", "city": "Coeur D Alene", "state": "ID", "zip": "83814", "phone": "2089641910"}

def new_jobsite():
    return {"name": f"Automation Jobsite {datetime.now().strftime('%H%M%S')}", "customer": "1627", "street": fake.street_address(), "city": fake.city(), "state": fake.state_abbr(), "zip": fake.zipcode()[:5]}

def new_vendor():
    return {"name": f"Automation Vendor {datetime.now().strftime('%H%M%S')}", "street": fake.street_address(), "city": fake.city(), "state": fake.state_abbr(), "zip": fake.zipcode()[:5], "phone": "4045550100", "ein": f"{fake.random_int(10,99)}-{fake.random_int(1000000,9999999)}"}

@dataclass
class TestResult:
    test_id: str
    title: str
    passed: bool = False
    failure_reasons: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    def log(self, msg):
        self.evidence.append(msg)
        print(f"  {msg}")
    def fail(self, reason):
        self.failure_reasons.append(reason)
        print(f"  FAIL -- {reason}")
    def ok(self, label):
        print(f"  OK -- {label}")
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
        print("="*65)

FIND_INPUT_JS = "(labelText) => { const text = labelText.trim(); for (const inp of document.querySelectorAll('input[aria-labelledby]')) { const labelEl = document.getElementById(inp.getAttribute('aria-labelledby')); if (labelEl && labelEl.textContent.trim() === text) return inp; } for (const label of document.querySelectorAll('label[for]')) { if (label.textContent.trim() === text) { const inp = document.getElementById(label.getAttribute('for')); if (inp) return inp; } } return null; }"

async def get_text_blocks(page):
    return await page.evaluate("() => { const seen = new Set(), out = []; for (const el of document.querySelectorAll('p,span,div,td,th,h1,h2,h3,h4,li,label,strong,b,a')) { const t = el.textContent.trim().replace(/\\s+/g,' '); if (t.length >= 2 && t.length <= 400 && !seen.has(t)) { seen.add(t); out.push(t); } } return out.slice(0,200); }")

async def dismiss_popups(page):
    try:
        await page.evaluate("() => { var d = document.querySelector('.e-dlg-overlay'); if (d && d.offsetParent !== null) { var c = document.querySelector('.e-footer-content button'); if (c) c.click(); else d.click(); } }")
        await page.wait_for_timeout(400)
    except Exception:
        pass
    try:
        n = await page.evaluate("() => document.querySelectorAll('.e-popup-open').length")
        if n > 0:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)
    except Exception:
        pass

async def wait_spinners(page, timeout=20000):
    try:
        await page.wait_for_function("() => document.querySelectorAll('.e-spin-show').length === 0", timeout=timeout)
    except Exception:
        pass

async def grid_row_count(page):
    return await page.evaluate("() => document.querySelectorAll('.e-gridcontent .e-row, table tbody tr.e-row').length")

async def grid_rows_text(page):
    return await page.evaluate("() => Array.from(document.querySelectorAll('.e-gridcontent .e-row, table tbody tr.e-row')).map(r => r.textContent.trim().replace(/\\s+/g,' '))")

async def fill_label(page, label, value, name=""):
    el = await page.evaluate_handle(FIND_INPUT_JS, label)
    as_el = el.as_element()
    if not as_el:
        raise RuntimeError(f"Input not found: {label}")
    await page.evaluate("el => el.scrollIntoView({block:'center'})", as_el)
    await page.wait_for_timeout(150)
    await page.evaluate("([el,val]) => { el.focus(); el.value=''; el.dispatchEvent(new Event('input',{bubbles:true})); el.value=val; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }", [as_el, value])
    await page.wait_for_timeout(200)
    print(f"  OK {name or label} = {value}")

async def fill_masked(page, label, value, name=""):
    el = await page.evaluate_handle(FIND_INPUT_JS, label)
    as_el = el.as_element()
    if not as_el:
        raise RuntimeError(f"Masked input not found: {label}")
    await page.evaluate("el => el.scrollIntoView({block:'center'})", as_el)
    await page.wait_for_timeout(200)
    await as_el.click()
    await page.wait_for_timeout(300)
    await page.keyboard.press("Home")
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Delete")
    await page.keyboard.type("".join(c for c in value if c.isdigit()), delay=80)
    await page.wait_for_timeout(200)
    print(f"  OK {name or label} = {value}")

async def fill_dropdown(page, label, value, name=""):
    el = await page.evaluate_handle(FIND_INPUT_JS, label)
    as_el = el.as_element()
    if not as_el:
        raise RuntimeError(f"Dropdown not found: {label}")
    await page.evaluate("el => { const t = el.closest('[role=\"combobox\"]') || el.parentElement || el; t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true})); t.dispatchEvent(new MouseEvent('click',{bubbles:true})); el.focus(); }", as_el)
    await page.wait_for_timeout(400)
    await page.keyboard.type(value, delay=100)
    await page.wait_for_timeout(700)
    await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(300)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(400)
    print(f"  OK {name or label} = {value}")

async def fill_autocomplete(page, value, label_hint=""):
    await page.evaluate("() => { document.querySelectorAll('button').forEach(b => { b._pe = b.style.pointerEvents; b.style.pointerEvents='none'; }); const inputs = document.querySelectorAll('input.e-autocomplete,input[role=\"combobox\"]'); for (const el of inputs) { if (el.offsetParent!==null && !el.disabled) { el.focus(); break; } } document.querySelectorAll('button').forEach(b => { b.style.pointerEvents = b._pe||''; }); }")
    await page.wait_for_timeout(300)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.type(value, delay=150)
    await page.wait_for_timeout(800)
    try:
        first = page.locator("[role='listbox'] li").first
        await first.wait_for(state="visible", timeout=5000)
        hdl = await first.element_handle()
        await page.evaluate("el => el.click()", hdl)
        print(f"  OK autocomplete = {value}")
    except Exception:
        await page.keyboard.press("ArrowDown")
        await page.wait_for_timeout(300)
        await page.keyboard.press("Enter")
        print(f"  OK autocomplete = {value} (keyboard)")
    await page.wait_for_timeout(400)

async def do_login(page):
    print("Logging in...")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
    for sel in ["input[placeholder='Email Address']", "#signInName", "input[name='signInName']", "input[type='text']"]:
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

async def _wait_nav(page):
    await page.wait_for_function("() => Array.from(document.querySelectorAll('button,a,span,li')).some(el => el.offsetParent!==null && el.textContent.trim().length>1)", timeout=30000)

async def _click(page, *labels):
    for label in labels:
        for sel in [f"span:has-text('{label}')", f"button:has-text('{label}')", f"a:has-text('{label}')", f"li:has-text('{label}')"]:
            loc = page.locator(sel).first
            try:
                await loc.wait_for(state="visible", timeout=4000)
                await loc.click()
                print(f"  OK clicked: {label}")
                return
            except Exception:
                continue
    raise RuntimeError(f"Could not click: {labels}")

async def nav_to_vendors(page):
    print("Navigating to Vendors...")
    await dismiss_popups(page)
    await _wait_nav(page)
    await _click(page, "Management")
    await page.wait_for_timeout(800)
    await _click(page, "Vendors", "Vendor")
    await page.wait_for_function("() => !window.location.href.endsWith('/home') && document.querySelectorAll('.e-control,.e-grid').length>0", timeout=25000)
    await wait_spinners(page)
    await page.wait_for_timeout(600)
    print(f"  OK vendors ready -- {page.url}")

async def nav_to_jobsites(page):
    print("Navigating to Jobsites...")
    await dismiss_popups(page)
    await _wait_nav(page)
    await _click(page, "Management")
    await page.wait_for_timeout(800)
    await _click(page, "Jobsites", "Jobsite")
    await page.wait_for_function("() => !window.location.href.endsWith('/home') && document.querySelectorAll('.e-control,.e-grid').length>0", timeout=25000)
    await wait_spinners(page)
    await page.wait_for_timeout(600)
    print(f"  OK jobsites ready -- {page.url}")

async def search_grid(page, query):
    await dismiss_popups(page)
    await page.wait_for_timeout(300)
    search_sel = "input[placeholder*='Search' i], input.search-input"
    search = page.locator(search_sel).first
    await search.wait_for(state="visible", timeout=8000)
    hdl = await search.element_handle()
    await page.evaluate("([el,q]) => { el.focus(); el.value=q; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }", [hdl, query])
    await page.wait_for_timeout(1200)
    await wait_spinners(page)
    print(f"  OK searched: {query}")

async def open_record_by_id(page, record_id):
    link = page.locator(f"a:has-text('{record_id}')").first
    try:
        await link.wait_for(state="visible", timeout=6000)
    except Exception:
        await search_grid(page, record_id)
        link = page.locator(f"a:has-text('{record_id}')").first
        await link.wait_for(state="visible", timeout=6000)
    await link.click()
    await wait_spinners(page)
    await page.wait_for_timeout(800)
    print(f"  OK opened: {record_id}")

async def click_new_button(page, label="NEW JOBSITE"):
    for sel in [f"button:has-text('{label}')", f"button:has-text('{label.title()}')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_function("() => { const inputs = document.querySelectorAll('input.e-input,input.e-autocomplete'); for (const i of inputs) if (i.offsetParent!==null) return true; return false; }", timeout=15000)
            await wait_spinners(page)
            await page.wait_for_timeout(500)
            print(f"  OK {label} wizard open")
            return
    raise RuntimeError(f"'{label}' button not found")

async def click_save(page):
    for sel in ["button:has-text('Save')", "button:has-text('SAVE')", "button:has-text('Update')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(2000)
            await wait_spinners(page)
            print("  OK saved")
            return

async def click_edit(page):
    for sel in ["button:has-text('Edit')", "button:has-text('EDIT')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(800)
            await wait_spinners(page)
            print("  OK edit opened")
            return
