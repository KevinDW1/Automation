"""
inv_base.py
───────────
Shared login, navigation, fill helpers, and result types
used by INV-07 through INV-22.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from playwright.async_api import Page, async_playwright

# ══════════════════════════════════════════════════════════════════════════════
# Credentials & URLs
# ══════════════════════════════════════════════════════════════════════════════

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

# ══════════════════════════════════════════════════════════════════════════════
# Known test data — update to match your QA database
# ══════════════════════════════════════════════════════════════════════════════

TODAY      = datetime.today()
DATE_START = TODAY.replace(day=1).strftime("%m/%d/%Y")
DATE_END   = TODAY.strftime("%m/%d/%Y")
DATE_TODAY = TODAY.strftime("%m/%d/%Y")

KNOWN_CUSTOMER = {
    "id":     "1627",
    "name":   "Waste Applications QA Customer",
    "street": "131 Glenn Bridge Rd",
    "city":   "Arden",
    "state":  "NC",
    "zip":    "28704",
}

KNOWN_JOBSITE = {
    "id":       "1627",
    "tax_rate": 9.0,
}

# ══════════════════════════════════════════════════════════════════════════════
# Generic result type
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TestResult:
    test_id:         str
    title:           str
    passed:          bool              = False
    failure_reasons: list[str]         = field(default_factory=list)
    evidence:        list[str]         = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.evidence.append(msg)
        print(f"  📋 {msg}")

    def fail(self, reason: str) -> None:
        self.failure_reasons.append(reason)
        print(f"  ✗  FAIL — {reason}")

    def passed_check(self, label: str) -> None:
        print(f"  ✅ {label}")

    def print_report(self) -> None:
        print("\n" + "═" * 65)
        print(f"  {self.test_id} TEST REPORT — {self.title}")
        print("─" * 65)
        if self.passed:
            print("  VERDICT: ✅ PASS")
        else:
            print("  VERDICT: ❌ FAIL")
            for r in self.failure_reasons:
                print(f"    • {r}")
        print("─" * 65)
        print("  Evidence:")
        for e in self.evidence:
            print(f"    {e}")
        print("═" * 65)

# ══════════════════════════════════════════════════════════════════════════════
# FIND_INPUT_JS — label-matching helper used by fill functions
# ══════════════════════════════════════════════════════════════════════════════

FIND_INPUT_JS = """
(labelText) => {
    const text = labelText.trim();
    for (const inp of document.querySelectorAll('input[aria-labelledby]')) {
        const labelEl = document.getElementById(inp.getAttribute('aria-labelledby'));
        if (labelEl && labelEl.textContent.trim() === text) return inp;
    }
    for (const label of document.querySelectorAll('label[for]')) {
        if (label.textContent.trim() === text) {
            const inp = document.getElementById(label.getAttribute('for'));
            if (inp) return inp;
        }
    }
    const bare = text.replace(/\\s*\\*\\s*$/, '').trim();
    for (const inp of document.querySelectorAll('input[aria-labelledby]')) {
        const labelEl = document.getElementById(inp.getAttribute('aria-labelledby'));
        if (labelEl && labelEl.textContent.trim().replace(/\\s*\\*\\s*$/, '') === bare) return inp;
    }
    for (const label of document.querySelectorAll('label[for]')) {
        if (label.textContent.trim().replace(/\\s*\\*\\s*$/, '') === bare) {
            const inp = document.getElementById(label.getAttribute('for'));
            if (inp) return inp;
        }
    }
    return null;
}
"""

# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def parse_currency(text: str) -> Optional[float]:
    cleaned = re.sub(r"[^\d.\-]", "", text.replace(",", ""))
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


async def dismiss_open_popups(page: Page) -> None:
    count = await page.evaluate(
        "() => document.querySelectorAll('.e-popup-open').length"
    )
    if count > 0:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)
        remaining = await page.evaluate(
            "() => document.querySelectorAll('.e-popup-open').length"
        )
        if remaining > 0:
            await page.mouse.click(10, 10)
            await page.wait_for_timeout(400)
        try:
            await page.wait_for_function(
                "() => document.querySelectorAll('.e-popup-open').length === 0",
                timeout=5_000,
            )
        except Exception:
            pass


async def wait_spinners_gone(page: Page, timeout: int = 20_000) -> None:
    try:
        await page.wait_for_function(
            "() => document.querySelectorAll('.e-spin-show').length === 0",
            timeout=timeout,
        )
    except Exception:
        pass


async def get_all_text_blocks(page: Page) -> list[str]:
    return await page.evaluate(
        """() => {
            const seen = new Set();
            const out  = [];
            for (const el of document.querySelectorAll(
                'p,span,div,td,th,h1,h2,h3,h4,li,address,label,strong,b'
            )) {
                const t = el.textContent.trim().replace(/\\s+/g,' ');
                if (t.length >= 2 && t.length <= 500 && !seen.has(t)) {
                    seen.add(t); out.push(t);
                }
            }
            return out.slice(0, 200);
        }"""
    )


async def fill_by_label(page: Page, label_text: str, value: str, field_name: str = "") -> None:
    el = await page.evaluate_handle(FIND_INPUT_JS, label_text)
    as_el = el.as_element()
    if not as_el:
        raise RuntimeError(f"Input not found for label: '{label_text}'")
    await page.evaluate("el => el.scrollIntoView({ block: 'center' })", as_el)
    await page.wait_for_timeout(150)
    await page.evaluate(
        """([el, val]) => {
            el.focus(); el.value = '';
            el.dispatchEvent(new Event('input',  { bubbles: true }));
            el.value = val;
            el.dispatchEvent(new Event('input',  { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        [as_el, value],
    )
    await page.wait_for_timeout(250)
    print(f"  ✓ {field_name or label_text} = '{value}'")


async def fill_dropdown_first_option(page: Page, label_text: str, field_name: str = "") -> str:
    el = await page.evaluate_handle(FIND_INPUT_JS, label_text)
    as_el = el.as_element()
    if not as_el:
        raise RuntimeError(f"Dropdown not found: '{label_text}'")
    await page.evaluate("el => el.scrollIntoView({ block: 'center' })", as_el)
    await page.wait_for_timeout(150)
    await page.evaluate(
        """el => {
            const t = el.closest('[role="combobox"]') || el.parentElement || el;
            t.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            t.dispatchEvent(new MouseEvent('mouseup',   { bubbles: true }));
            t.dispatchEvent(new MouseEvent('click',     { bubbles: true }));
            el.focus();
        }""",
        as_el,
    )
    await page.wait_for_timeout(500)
    listbox = page.locator("[role='listbox'] li.e-list-item, [role='listbox'] li").first
    selected_text = ""
    try:
        await listbox.wait_for(state="visible", timeout=6_000)
        selected_text = (await listbox.inner_text()).strip()
        hdl = await listbox.element_handle()
        await page.evaluate("el => el.click()", hdl)
        await page.wait_for_timeout(300)
        print(f"  ✓ {field_name or label_text} = '{selected_text}'")
    except Exception:
        await page.keyboard.press("ArrowDown")
        await page.wait_for_timeout(300)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(300)
        print(f"  ✓ {field_name or label_text} = (first option)")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    try:
        await page.wait_for_function(
            "() => document.querySelectorAll('.e-popup-open').length === 0",
            timeout=5_000,
        )
    except Exception:
        pass
    return selected_text


async def fill_daterange(page: Page, start: str, end: str) -> None:
    loc = page.locator("input.e-daterangepicker, input.e-date-range-picker").first
    if await loc.count() == 0:
        raise RuntimeError("DateRangePicker not found")
    await loc.click()
    await page.wait_for_timeout(300)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.type(start, delay=80)
    await page.wait_for_timeout(200)
    await page.keyboard.press("Tab")
    await page.wait_for_timeout(200)
    await page.keyboard.type(end, delay=80)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(400)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(200)
    print(f"  ✓ Date range = '{start}' → '{end}'")

# ══════════════════════════════════════════════════════════════════════════════
# Login
# ══════════════════════════════════════════════════════════════════════════════

async def do_login(page: Page) -> None:
    print("→ Logging in…")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
    for sel in [
        "input[placeholder='Email Address']", "#signInName",
        "input[name='signInName']", "input[type='email']", "input[type='text']",
    ]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=20_000)
            await loc.fill(VALID_EMAIL)
            await page.keyboard.press("Tab")
            print("  ✓ Email entered")
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
    await page.wait_for_url(re.compile(r"wasteapplications\.com"), timeout=30_000)
    await page.wait_for_load_state("networkidle", timeout=20_000)
    print(f"  ✓ Logged in — {page.url}")

# ══════════════════════════════════════════════════════════════════════════════
# Navigation helpers
# ══════════════════════════════════════════════════════════════════════════════

async def wait_for_nav(page: Page) -> None:
    """Wait for the Blazor nav bar to mount."""
    await page.wait_for_function(
        """() => Array.from(document.querySelectorAll('button,a,span,li'))
                      .some(el => el.offsetParent !== null && el.textContent.trim().length > 1)""",
        timeout=30_000,
    )


async def click_nav(page: Page, *labels: str) -> None:
    """Click a nav item matching any of the given text labels."""
    for label in labels:
        for sel in [
            f"span:has-text('{label}')",   # confirmed working in prod
            f"button:has-text('{label}')",
            f"a:has-text('{label}')",
            f"li:has-text('{label}')",
            f"a[href*='{label.lower().replace(' ', '-')}']",
            f"a[href*='{label.replace(' ', '')}']",
        ]:
            loc = page.locator(sel).first
            try:
                await loc.wait_for(state="visible", timeout=4_000)
                await loc.click()
                print(f"  ✓ Clicked: '{label}'")
                return
            except Exception:
                continue
    # JS fallback
    for label in labels:
        clicked = await page.evaluate(
            f"""() => {{
                for (const el of document.querySelectorAll('button,a,span,li')) {{
                    if (el.offsetParent !== null &&
                        el.textContent.trim().toLowerCase() === '{label.lower()}') {{
                        el.click(); return true;
                    }}
                }}
                return false;
            }}"""
        )
        if clicked:
            print(f"  ✓ Clicked via JS: '{label}'")
            return
    raise RuntimeError(f"Could not click any of: {labels}")


async def nav_to_accounting_generate_invoices(page: Page) -> None:
    print("\n→ Navigating to Accounting > Generate Invoices…")
    await wait_for_nav(page)
    await click_nav(page, "Accounting")
    await page.wait_for_timeout(1_000)
    await click_nav(page, "Generate Invoices")
    await page.wait_for_function(
        """() => {
            const url = window.location.href;
            const notHome = !url.endsWith('/home');
            const onInvoicing = url.includes('billing') || url.includes('invoic') || url.includes('Invoic');
            const hasControls = document.querySelectorAll('.e-control').length > 0;
            return notHome && (onInvoicing || hasControls);
        }""",
        timeout=25_000,
    )
    await wait_spinners_gone(page)
    await page.wait_for_timeout(800)
    print(f"  ✓ Generate Invoices ready — {page.url}")


async def nav_to_sent_batches(page: Page) -> None:
    """From Generate Invoices page, click SENT BATCHES tab."""
    for sel in ["a:has-text('Sent Batches')", "a:has-text('SENT BATCHES')",
                "button:has-text('Sent Batches')", "span:has-text('SENT BATCHES')"]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=5_000)
            await loc.click()
            print("  ✓ Sent Batches opened")
            await wait_spinners_gone(page)
            await page.wait_for_timeout(600)
            return
        except Exception:
            continue
    # JS fallback
    clicked = await page.evaluate(
        """() => {
            for (const el of document.querySelectorAll('a,button,span')) {
                if (/sent.?batch/i.test(el.textContent) && el.offsetParent !== null) {
                    el.click(); return true;
                }
            }
            return false;
        }"""
    )
    if not clicked:
        raise RuntimeError("SENT BATCHES tab not found")
    await wait_spinners_gone(page)
    await page.wait_for_timeout(600)
    print("  ✓ Sent Batches opened via JS")


async def open_first_batch(page: Page, customer_hint: str = "") -> str:
    """
    Open the first batch row in the current grid.
    Syncfusion grids use javascript:void(0) links — we click the row cell
    directly via JS to trigger the row-click handler, not the anchor href.
    Returns the batch label text.
    """
    rows = page.locator(".e-gridcontent .e-row, table tbody tr")
    count = await rows.count()
    target_row = None

    # Prefer a row matching the customer hint
    if customer_hint:
        for i in range(min(count, 20)):
            row = rows.nth(i)
            if customer_hint.lower() in (await row.inner_text()).lower():
                target_row = row
                break

    if target_row is None:
        if count == 0:
            raise RuntimeError("No rows found in grid")
        target_row = rows.first

    label = (await target_row.inner_text()).strip().replace("\n", " ")[:60]

    # Click the first cell (batch number column) via JS to fire row handler
    first_cell = target_row.locator("td").first
    cell_hdl = await first_cell.element_handle()
    await page.evaluate(
        """el => {
            // Try clicking any anchor inside first
            const a = el.querySelector('a');
            if (a) { a.click(); return; }
            // Otherwise click the cell itself — triggers Syncfusion row select + navigate
            el.click();
            // Also dispatch a dblclick in case row needs double-click to open
            el.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
        }""",
        cell_hdl,
    )
    await page.wait_for_timeout(1_500)

    # If URL didn't change, try clicking the row itself
    before_url = page.url
    if page.url == before_url:
        row_hdl = await target_row.element_handle()
        await page.evaluate("el => el.click()", row_hdl)
        await page.wait_for_timeout(1_000)

    await wait_spinners_gone(page)
    await page.wait_for_timeout(800)
    print(f"  ✓ Opened batch row: '{label}'")
    return label


async def generate_invoice(
    page: Page,
    generate_by: str = "All",
    customer_id: str = "",
    jobsite_id:  str = "",
    date_start:  str = DATE_START,
    date_end:    str = DATE_END,
    batch_notes: str = "Automated QA test",
) -> None:
    """
    Fill and submit the Generate Invoices form.
    generate_by: 'All', 'Customer', or 'Jobsite'
    """
    print(f"\n→ Generating invoice (Generate By: {generate_by})…")

    # Generate By radio
    if generate_by != "All":
        await page.evaluate(
            f"""() => {{
                for (const label of document.querySelectorAll('label')) {{
                    if (/^{generate_by}$/i.test(label.textContent.trim())) {{
                        const inp = label.control ||
                                    document.getElementById(label.getAttribute('for'));
                        if (inp) inp.click(); else label.click();
                        return;
                    }}
                }}
            }}"""
        )
        await page.wait_for_timeout(500)
        print(f"  ✓ Generate By: {generate_by}")

    await fill_daterange(page, date_start, date_end)

    # Autocomplete for customer or jobsite
    if customer_id or jobsite_id:
        search_val = customer_id or jobsite_id
        await page.evaluate(
            """() => {
                document.querySelectorAll('button').forEach(b => {
                    b._pe = b.style.pointerEvents;
                    b.style.pointerEvents = 'none';
                });
                const inputs = document.querySelectorAll('input.e-autocomplete,input[role="combobox"]');
                for (const el of inputs) {
                    if (el.offsetParent !== null && !el.disabled) { el.focus(); break; }
                }
                document.querySelectorAll('button').forEach(b => {
                    b.style.pointerEvents = b._pe || '';
                });
            }"""
        )
        await page.wait_for_timeout(300)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(search_val, delay=150)
        await page.wait_for_timeout(800)
        try:
            first = page.locator("[role='listbox'] li").first
            await first.wait_for(state="visible", timeout=5_000)
            hdl = await first.element_handle()
            await page.evaluate("el => el.click()", hdl)
            print(f"  ✓ Selected: '{search_val}'")
        except Exception:
            await page.keyboard.press("ArrowDown")
            await page.wait_for_timeout(300)
            await page.keyboard.press("Enter")

    await fill_dropdown_first_option(page, "Billing Cycles *", "Billing Cycles")
    await fill_dropdown_first_option(page, "Billable Items *",  "Billable Items")
    await dismiss_open_popups(page)

    # Posting Date
    dp = page.locator("[data-testid='invoicing-posting-date'], input.e-datepicker").first
    dp_hdl = await dp.element_handle()
    await page.evaluate("el => { el.focus(); el.click(); }", dp_hdl)
    await page.wait_for_timeout(200)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.type(DATE_TODAY, delay=80)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    print(f"  ✓ Posting Date = '{DATE_TODAY}'")
    await dismiss_open_popups(page)

    try:
        await fill_by_label(page, "Batch Notes (internal)", batch_notes)
    except Exception:
        pass

    await dismiss_open_popups(page)
    gen_btn = page.locator("button:has-text('GENERATE'), button:has-text('Generate')").first
    await gen_btn.wait_for(state="visible", timeout=10_000)
    await gen_btn.click()
    print("  ✓ GENERATE clicked — waiting…")
    await page.wait_for_function(
        "() => document.querySelectorAll('.e-spin-show').length === 0",
        timeout=60_000,
    )
    await page.wait_for_timeout(1_000)
    print("  ✓ Generation complete")
