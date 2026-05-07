"""
inv04_service_types.py
──────────────────────
Test Case : INV-04 — Invoice includes all service types in billing period
Precond   : Jobsite has multiple service types (e.g. Rolloff, Toilets, Equipment)
Steps     :
  1. Generate invoice for billing period with multiple service types
  2. Review all line items
Expected  : All service types for the period appear as separate line items
            on the invoice.

Strategy
────────
  • Generate By: Jobsite → filter to JOBSITE_ID
  • After generation open the batch detail page
  • Extract every line item row from the invoice
  • Group by service type label
  • Assert: every known service type on the jobsite appears at least once
  • Assert: each appears as a SEPARATE line (not merged/collapsed)
  • Full evidence trail printed — every line item captured

Reuses all proven helpers (FIND_INPUT_JS, fill helpers, dismiss_open_popups)
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from playwright.async_api import Page, async_playwright

# ══════════════════════════════════════════════════════════════════════════════
# Test configuration
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

# ── Target jobsite ────────────────────────────────────────────────────────────
JOBSITE_ID = "1627"

# Service types expected on this jobsite — all must appear as separate lines.
# Update this list to match what is actually configured on the jobsite.
EXPECTED_SERVICE_TYPES: list[str] = [
    "Rolloff",
    "Toilets",
    "Equipment",
]

# ── Billing period — current month to capture active service orders ───────────
TODAY      = datetime.today()
DATE_START = TODAY.replace(day=1).strftime("%m/%d/%Y")
DATE_END   = TODAY.strftime("%m/%d/%Y")
DATE_TODAY = TODAY.strftime("%m/%d/%Y")

BATCH_NOTES     = f"INV-04 service types verification — jobsite {JOBSITE_ID}"
INVOICE_MESSAGE = "Thank you for your business!"

# ══════════════════════════════════════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LineItem:
    """One line extracted from the invoice."""
    description:  str
    service_type: str        # best-guess service type label
    quantity:     str = ""
    amount:       str = ""
    raw_row:      str = ""   # full row text for evidence


@dataclass
class Inv04Result:
    jobsite_id:            str
    expected_service_types: list[str]
    line_items:            list[LineItem]  = field(default_factory=list)
    found_service_types:   list[str]       = field(default_factory=list)
    missing_service_types: list[str]       = field(default_factory=list)
    merged_lines:          list[str]       = field(default_factory=list)
    passed:                bool            = False
    failure_reasons:       list[str]       = field(default_factory=list)
    evidence:              list[str]       = field(default_factory=list)

    def add_evidence(self, msg: str) -> None:
        self.evidence.append(msg)
        print(f"  📋 {msg}")

    def fail(self, reason: str) -> None:
        self.failure_reasons.append(reason)
        print(f"  ✗ FAIL — {reason}")


# ══════════════════════════════════════════════════════════════════════════════
# JS helpers
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
# Shared fill helpers  (same proven patterns throughout this project)
# ══════════════════════════════════════════════════════════════════════════════

async def dismiss_open_popups(page: Page) -> None:
    count = await page.evaluate(
        "() => document.querySelectorAll('.e-popup-open').length"
    )
    if count > 0:
        print(f"  → Dismissing {count} open popup(s)…")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)
        remaining = await page.evaluate(
            "() => document.querySelectorAll('.e-popup-open').length"
        )
        if remaining > 0:
            await page.mouse.click(10, 10)
            await page.wait_for_timeout(400)
        await page.wait_for_function(
            "() => document.querySelectorAll('.e-popup-open').length === 0",
            timeout=5_000,
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
            el.focus();
            el.value = '';
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
        raise RuntimeError(f"Dropdown not found for label: '{label_text}'")
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
        print(f"  ✓ {field_name or label_text} = '{selected_text}' (first option)")
    except Exception:
        await page.keyboard.press("ArrowDown")
        await page.wait_for_timeout(300)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(300)
        print(f"  ✓ {field_name or label_text} = (first option via keyboard)")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    await page.wait_for_function(
        "() => document.querySelectorAll('.e-popup-open').length === 0",
        timeout=5_000,
    )
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
    print(f"  ✓ Processing dates = '{start}' → '{end}'")


async def fill_jobsite_autocomplete(page: Page, jobsite_id: str) -> None:
    """Focus the Jobsite ID/Name autocomplete and type the jobsite ID."""
    await page.evaluate(
        """() => {
            document.querySelectorAll('button').forEach(b => {
                b._savedPE = b.style.pointerEvents;
                b.style.pointerEvents = 'none';
            });
            const inputs = document.querySelectorAll('input.e-autocomplete, input[role="combobox"]');
            for (const el of inputs) {
                if (el.offsetParent !== null && !el.disabled) {
                    el.focus();
                    break;
                }
            }
            document.querySelectorAll('button').forEach(b => {
                b.style.pointerEvents = b._savedPE || '';
            });
        }"""
    )
    await page.wait_for_timeout(300)

    is_input = await page.evaluate("() => document.activeElement?.tagName === 'INPUT'")
    if not is_input:
        for sel in [
            "input[aria-label*='Jobsite' i]",
            "input[placeholder*='Jobsite' i]",
            "input[placeholder*='All Jobsites' i]",
            "input.e-autocomplete",
        ]:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                hdl = await loc.element_handle()
                await page.evaluate("el => { el.focus(); el.click(); }", hdl)
                await page.wait_for_timeout(300)
                break

    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.wait_for_timeout(100)
    await page.keyboard.type(jobsite_id, delay=180)
    print(f"  ✓ Typed jobsite ID: '{jobsite_id}'")

    # Wait for dropdown
    for sel in ["[role='listbox'] li", ".e-autocomplete-list li", "ul.e-ul li"]:
        try:
            await page.locator(sel).first.wait_for(state="visible", timeout=5_000)
            break
        except Exception:
            continue

    # Select first suggestion
    try:
        first = page.locator("[role='listbox'] li.e-list-item, [role='listbox'] li").first
        await first.wait_for(state="visible", timeout=4_000)
        selected = (await first.inner_text()).strip()
        hdl = await first.element_handle()
        await page.evaluate("el => el.click()", hdl)
        print(f"  ✓ Jobsite selected: '{selected}'")
    except Exception:
        await page.keyboard.press("ArrowDown")
        await page.wait_for_timeout(300)
        await page.keyboard.press("Enter")
        print("  ✓ Jobsite selected via keyboard")

    await page.wait_for_timeout(400)


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
    try:
        await page.wait_for_load_state("networkidle", timeout=30_000)
    except Exception:
        pass  # networkidle may never fire on Blazor SPA
    print(f"  ✓ Logged in — {page.url}")


# ══════════════════════════════════════════════════════════════════════════════
# Navigation
# ══════════════════════════════════════════════════════════════════════════════

async def navigate_to_generate_invoices(page: Page) -> None:
    print("\n→ Navigating to Accounting > Generate Invoices…")

    # ── Step 1: Wait for the app shell to fully load ──────────────────────
    print("  → Waiting for nav bar to mount…")
    try:
        await page.wait_for_function(
            """() => {
                const els = document.querySelectorAll('button, a, span, li');
                for (const el of els) {
                    if (/accounting/i.test(el.textContent) && el.offsetParent !== null)
                        return true;
                }
                return false;
            }""",
            timeout=30_000,
        )
        print("  ✓ Nav bar ready")
    except Exception:
        dump = await page.evaluate(
            """() => ({
                url:     window.location.href,
                buttons: Array.from(document.querySelectorAll('button'))
                           .map(b => b.textContent.trim()).filter(Boolean),
                links:   Array.from(document.querySelectorAll('a'))
                           .map(a => a.textContent.trim() + ' → ' + a.href).filter(Boolean).slice(0,20),
            })"""
        )
        await page.screenshot(path="debug_no_nav.png")
        raise RuntimeError(f"Nav bar never mounted. Page state: {dump}")

    # ── Step 2: Click Accounting ──────────────────────────────────────────
    accounting_clicked = False
    for sel in [
        "button:has-text('Accounting')",
        "a:has-text('Accounting')",
        "span:has-text('Accounting')",
        "li:has-text('Accounting')",
    ]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=5_000)
            await loc.click()
            accounting_clicked = True
            print(f"  ✓ Accounting clicked via: {sel}")
            break
        except Exception:
            continue

    if not accounting_clicked:
        clicked = await page.evaluate(
            """() => {
                for (const el of document.querySelectorAll('button,a,span,li')) {
                    if (/^accounting$/i.test(el.textContent.trim()) && el.offsetParent !== null) {
                        el.click(); return el.tagName + ':' + el.textContent.trim();
                    }
                }
                return null;
            }"""
        )
        if clicked:
            print(f"  ✓ Accounting clicked via JS: {clicked}")
        else:
            await page.screenshot(path="debug_accounting_not_found.png")
            raise RuntimeError("Accounting menu item not found")

    await page.wait_for_timeout(1_200)

    # ── Step 3: Click Generate Invoices ──────────────────────────────────
    gen_clicked = False
    for sel in [
        "a[href*='GenerateInvoices']",
        "a[href*='Generate']",
        "a:has-text('Generate Invoices')",
        "span:has-text('Generate Invoices')",
        "li:has-text('Generate Invoices')",
    ]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=5_000)
            await loc.click()
            gen_clicked = True
            print(f"  ✓ Generate Invoices clicked via: {sel}")
            break
        except Exception:
            continue

    if not gen_clicked:
        clicked = await page.evaluate(
            """() => {
                for (const el of document.querySelectorAll('a,span,li')) {
                    if (/generate\s+invoice/i.test(el.textContent) && el.offsetParent !== null) {
                        el.click(); return el.tagName + ':' + el.textContent.trim();
                    }
                }
                return null;
            }"""
        )
        if not clicked:
            await page.screenshot(path="debug_gen_invoices_not_found.png")
            raise RuntimeError("Generate Invoices menu item not found")
        print(f"  ✓ Generate Invoices clicked via JS: {clicked}")

    # ── Step 4: Wait for SPA route + content ─────────────────────────────
    print("  → Waiting for page to render…")
    try:
        await page.wait_for_function(
            """() => {
                const notHome     = !window.location.href.endsWith('/home');
                const hasControls = document.querySelectorAll('.e-control').length > 0;
                return notHome && hasControls;
            }""",
            timeout=25_000,
        )
    except Exception:
        info = await page.evaluate(
            """() => ({
                url:      window.location.href,
                controls: document.querySelectorAll('.e-control').length,
                visible:  Array.from(document.querySelectorAll('h1,h2,h3,button'))
                            .map(e => e.textContent.trim()).filter(Boolean).slice(0,15),
            })"""
        )
        await page.screenshot(path="debug_nav_failed.png")
        raise RuntimeError(f"Generate Invoices page did not render. State: {info}")

    try:
        await page.wait_for_function(
            "() => document.querySelectorAll('.e-spin-show').length === 0",
            timeout=20_000,
        )
    except Exception:
        pass

    await page.wait_for_timeout(800)
    print(f"  ✓ Generate Invoices page ready — {page.url}")
async def generate_jobsite_invoice(page: Page) -> None:
    print(f"\n→ Step 1: Generating invoice for jobsite {JOBSITE_ID} "
          f"(period {DATE_START} → {DATE_END})…")

    # Generate By: Jobsite
    clicked = await page.evaluate(
        """() => {
            for (const label of document.querySelectorAll('label')) {
                if (/^jobsite$/i.test(label.textContent.trim())) {
                    const inp = label.control ||
                                document.getElementById(label.getAttribute('for'));
                    if (inp) { inp.click(); return true; }
                    label.click(); return true;
                }
            }
            return false;
        }"""
    )
    print(f"  {'✓' if clicked else '⚠ '} Generate By: Jobsite "
          f"{'selected' if clicked else '— radio not found, proceeding'}")
    await page.wait_for_timeout(500)

    await fill_daterange(page, DATE_START, DATE_END)
    await fill_jobsite_autocomplete(page, JOBSITE_ID)
    await fill_dropdown_first_option(page, "Billing Cycles *", "Billing Cycles")
    await fill_dropdown_first_option(page, "Billable Items *",  "Billable Items")
    await dismiss_open_popups(page)

    # Posting Date
    dp = page.locator("[data-testid='invoicing-posting-date']").first
    if await dp.count() == 0:
        dp = page.locator("input.e-datepicker").first
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
        await fill_by_label(page, "Batch Notes (internal)", BATCH_NOTES, "Batch Notes")
    except Exception:
        pass
    try:
        await fill_by_label(
            page, "Invoice Message (will appear on invoices)",
            INVOICE_MESSAGE, "Invoice Message",
        )
    except Exception:
        pass

    await page.screenshot(path="inv04_form_filled.png")
    print("  ✓ Form complete — inv04_form_filled.png")

    await dismiss_open_popups(page)
    gen_btn = page.locator("button:has-text('GENERATE'), button:has-text('Generate')").first
    await gen_btn.wait_for(state="visible", timeout=10_000)
    await gen_btn.click()
    print("  ✓ GENERATE clicked")

    await page.wait_for_function(
        "() => document.querySelectorAll('.e-spin-show').length === 0",
        timeout=60_000,
    )
    await page.wait_for_timeout(1_000)
    await page.screenshot(path="inv04_after_generate.png")
    print("  ✓ Generation complete — inv04_after_generate.png")


# ══════════════════════════════════════════════════════════════════════════════
# Step 2 — Open batch and extract all line items
# ══════════════════════════════════════════════════════════════════════════════

async def open_batch_detail(page: Page, result: Inv04Result) -> bool:
    """
    Find the newly generated batch row in Ready to Send grid and open it.
    Returns True if successfully opened.
    """
    print("\n→ Step 2: Opening batch to review line items…")

    # Check the grid has at least one row
    row_count = await page.evaluate(
        "() => document.querySelectorAll('.e-gridcontent .e-row, table.e-table tbody tr.e-row').length"
    )
    if row_count == 0:
        result.fail("No batch rows in Ready to Send grid — generation produced 0 invoices")
        await page.screenshot(path="inv04_no_batch.png")
        return False

    result.add_evidence(f"Batch grid row count: {row_count}")

    # Click the first batch link (Batch # column)
    batch_link = page.locator(
        ".e-gridcontent .e-row a, table.e-table tbody tr.e-row a"
    ).first
    if await batch_link.count() == 0:
        result.fail("No clickable batch link found in grid")
        return False

    batch_text = (await batch_link.inner_text()).strip()
    batch_href = await batch_link.get_attribute("href") or ""
    result.add_evidence(f"Opening batch: '{batch_text}' href='{batch_href}'")
    print(f"  → Clicking batch: '{batch_text}'")

    await batch_link.click()
    try:
        await page.wait_for_load_state("networkidle", timeout=30_000)
    except Exception:
        pass  # networkidle may never fire on Blazor SPA
    await page.wait_for_function(
        "() => document.querySelectorAll('.e-spin-show').length === 0",
        timeout=15_000,
    )
    await page.wait_for_timeout(1_000)
    await page.screenshot(path="inv04_batch_detail.png")
    print("  ✓ Batch detail open — inv04_batch_detail.png")
    return True


async def extract_all_line_items(page: Page, result: Inv04Result) -> None:
    """
    Extract every line item visible on the invoice/batch detail page.

    Four strategies tried in order:
      1. Syncfusion grid rows  (.e-row td cells)
      2. HTML table rows  (tr > td)
      3. Definition-list / label-value pairs  (.line-item, .invoice-line, etc.)
      4. Full text scan — any element whose text matches a service-type keyword

    Each found item is stored as a LineItem with its raw text preserved.
    """
    print("  → Extracting all line items from invoice…")

    raw_items: list[dict] = await page.evaluate(
        """() => {
            const items = [];
            const seen  = new Set();

            const addItem = (desc, qty, amount, raw, source) => {
                const key = desc + '|' + amount;
                if (seen.has(key)) return;
                seen.add(key);
                items.push({ desc, qty, amount, raw, source });
            };

            // ── Strategy 1: Syncfusion grid rows ──────────────────────────
            const gridRows = document.querySelectorAll(
                '.e-gridcontent .e-row, .e-grid tbody tr.e-row'
            );
            for (const row of gridRows) {
                const cells = Array.from(row.querySelectorAll('td'))
                                   .map(c => c.textContent.trim())
                                   .filter(Boolean);
                if (cells.length >= 2) {
                    addItem(cells[0], cells[1] || '', cells[cells.length - 1], cells.join(' | '), 'syncfusion-grid');
                }
            }

            // ── Strategy 2: Plain HTML table rows ─────────────────────────
            const tableRows = document.querySelectorAll('table tr');
            for (const row of tableRows) {
                if (row.closest('.e-grid')) continue;   // already handled
                const cells = Array.from(row.querySelectorAll('td, th'))
                                   .map(c => c.textContent.trim())
                                   .filter(Boolean);
                if (cells.length >= 2 && !/^(batch|invoice|posting|customer|jobsite)/i.test(cells[0])) {
                    addItem(cells[0], cells[1] || '', cells[cells.length - 1], cells.join(' | '), 'html-table');
                }
            }

            // ── Strategy 3: Invoice line item containers ───────────────────
            const lineSelectors = [
                '.line-item', '.invoice-line', '.invoice-row',
                '[class*="line-item"]', '[class*="lineitem"]',
                '[class*="service-line"]', '[class*="invoice-item"]',
            ];
            for (const sel of lineSelectors) {
                for (const el of document.querySelectorAll(sel)) {
                    const txt = el.textContent.trim().replace(/\\s+/g, ' ');
                    if (txt.length > 3) {
                        addItem(txt, '', '', txt, 'css-line-item');
                    }
                }
            }

            // ── Strategy 4: Text nodes near service-type keywords ──────────
            const serviceKeywords = ['rolloff', 'toilet', 'equipment', 'service',
                                     'rental', 'haul', 'delivery', 'pickup',
                                     'fee', 'charge', 'portable'];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            let node;
            while ((node = walker.nextNode())) {
                const t = node.textContent.trim();
                if (!t || t.length < 3) continue;
                const lower = t.toLowerCase();
                if (serviceKeywords.some(k => lower.includes(k))) {
                    const parent = node.parentElement;
                    if (parent && parent.tagName !== 'SCRIPT' && parent.tagName !== 'STYLE') {
                        addItem(t, '', '', t, 'text-node');
                    }
                }
            }

            return items;
        }"""
    )

    result.add_evidence(f"Total raw items extracted: {len(raw_items)}")

    # Convert to LineItem objects and infer service type
    service_type_patterns: list[tuple[str, str]] = [
        (r"rolloff",    "Rolloff"),
        (r"toilet|portabl|sanit", "Toilets"),
        (r"equipment|equip",      "Equipment"),
        (r"haul|pickup|pull",     "Haul/Pickup"),
        (r"deliver",              "Delivery"),
        (r"rental|rent",          "Rental"),
        (r"service\s+order",      "Service Order"),
        (r"fee|charge",           "Fee/Charge"),
    ]

    for raw in raw_items:
        desc  = raw.get("desc", "")
        lower = desc.lower()
        stype = "Unknown"
        for pattern, label in service_type_patterns:
            if re.search(pattern, lower):
                stype = label
                break

        item = LineItem(
            description=desc,
            service_type=stype,
            quantity=raw.get("qty", ""),
            amount=raw.get("amount", ""),
            raw_row=raw.get("raw", ""),
        )
        result.line_items.append(item)

    # Summarise what was found
    print(f"\n  Line items extracted ({len(result.line_items)}):")
    for i, li in enumerate(result.line_items, 1):
        print(f"    {i:>2}. [{li.service_type:>14}]  {li.description[:60]}"
              + (f"  |  qty: {li.quantity}" if li.quantity else "")
              + (f"  |  amt: {li.amount}"   if li.amount   else ""))

    await page.screenshot(path="inv04_line_items.png")
    print("\n  ✓ Screenshot of invoice: inv04_line_items.png")


# ══════════════════════════════════════════════════════════════════════════════
# Assertions
# ══════════════════════════════════════════════════════════════════════════════

def assert_all_service_types_present(result: Inv04Result) -> None:
    """
    INV-04 assertion:
      A. Every EXPECTED_SERVICE_TYPE appears as at least one separate line item.
      B. No two distinct service types are merged into a single line
         (each type has its OWN row — not "Rolloff + Toilets" in one cell).
      C. At least one line item exists at all.
    """
    print("\n→ Verifying all service types appear as separate line items…")

    # ── Assertion C: at least one line item ──────────────────────────────
    if not result.line_items:
        result.fail("No line items found on invoice — invoice may be empty")
        return

    result.add_evidence(f"Total line items: {len(result.line_items)}")

    # ── Build found service types set ─────────────────────────────────────
    # A service type "appears" if at least one LineItem's service_type
    # or description contains it (case-insensitive)
    found: set[str] = set()
    for expected in result.expected_service_types:
        pattern = expected.lower().rstrip("s")   # "Rolloffs" → "rolloff" for matching
        for li in result.line_items:
            if (pattern in li.description.lower() or
                pattern in li.service_type.lower()):
                found.add(expected)
                break

    result.found_service_types   = sorted(found)
    result.missing_service_types = [
        s for s in result.expected_service_types if s not in found
    ]

    result.add_evidence(f"Expected service types : {result.expected_service_types}")
    result.add_evidence(f"Found service types    : {result.found_service_types}")
    result.add_evidence(f"Missing service types  : {result.missing_service_types}")

    # ── Assertion A: all expected types present ────────────────────────────
    if result.missing_service_types:
        result.fail(
            f"Missing service type(s) as separate line items: "
            f"{result.missing_service_types}"
        )
    else:
        print(f"  ✅ All {len(result.expected_service_types)} expected service types "
              f"found as line items: {result.found_service_types}")

    # ── Assertion B: each type appears as its OWN line (not merged) ────────
    # A merged line would contain two or more service type keywords in one cell.
    service_keywords = [s.lower().rstrip("s") for s in result.expected_service_types]
    for li in result.line_items:
        lower = li.description.lower()
        hits  = [kw for kw in service_keywords if kw in lower]
        if len(hits) >= 2:
            merged_desc = f"'{li.description[:80]}' contains: {hits}"
            result.merged_lines.append(merged_desc)
            result.fail(
                f"Merged line item detected — two service types in one row: "
                f"{merged_desc}"
            )

    if not result.merged_lines:
        print("  ✅ No merged lines detected — each service type is a separate line item")

    # ── Final verdict ──────────────────────────────────────────────────────
    result.passed = (
        len(result.missing_service_types) == 0 and
        len(result.merged_lines) == 0 and
        len(result.line_items) > 0
    )


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    print("\n" + "═" * 65)
    print("  INV-04 — Invoice includes all service types in billing period")
    print(f"  Jobsite          : {JOBSITE_ID}")
    print(f"  Expected types   : {EXPECTED_SERVICE_TYPES}")
    print(f"  Billing period   : {DATE_START}  →  {DATE_END}")
    print("  Expected result  : All service types appear as separate lines")
    print("═" * 65)

    result = Inv04Result(
        jobsite_id=JOBSITE_ID,
        expected_service_types=EXPECTED_SERVICE_TYPES,
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir="videos/",
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        try:
            await do_login(page)
            await navigate_to_generate_invoices(page)

            # Step 1: Generate
            await generate_jobsite_invoice(page)

            # Step 2: Open batch and extract line items
            batch_opened = await open_batch_detail(page, result)
            if batch_opened:
                await extract_all_line_items(page, result)

            # Assertions
            assert_all_service_types_present(result)

        except Exception as exc:
            result.fail(f"Script exception: {exc}")
            await page.screenshot(path="inv04_error.png")
            print(f"\n❌ Script error: {exc}")

        finally:
            await page.wait_for_timeout(3_000)
            await context.close()
            await browser.close()

    # ── Final test report ──────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  INV-04 TEST REPORT")
    print("─" * 65)
    print(f"  Jobsite          : {result.jobsite_id}")
    print(f"  Billing period   : {DATE_START}  →  {DATE_END}")
    print(f"  Line items found : {len(result.line_items)}")
    print(f"  Service types    : {result.found_service_types}")
    print(f"  Missing types    : {result.missing_service_types or 'None'}")
    print(f"  Merged lines     : {result.merged_lines or 'None'}")
    print("─" * 65)

    if result.passed:
        print("  VERDICT: ✅ PASS")
        print("  All service types appear as separate line items on the invoice.")
    else:
        print("  VERDICT: ❌ FAIL")
        for reason in result.failure_reasons:
            print(f"    • {reason}")

    print("─" * 65)
    print("  Line item detail:")
    for i, li in enumerate(result.line_items, 1):
        print(f"    {i:>2}. [{li.service_type:>14}]  {li.description[:60]}")

    print("─" * 65)
    print("  Evidence trail:")
    for e in result.evidence:
        print(f"    {e}")

    print("═" * 65)
    print("\n  🎥 Video: videos/")
    print("  📸 inv04_form_filled.png | inv04_after_generate.png")
    print("     inv04_batch_detail.png | inv04_line_items.png")


if __name__ == "__main__":
    asyncio.run(main())
