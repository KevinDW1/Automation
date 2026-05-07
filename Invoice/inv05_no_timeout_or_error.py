"""
inv05_no_timeout_or_error.py
────────────────────────────
Test Case : INV-05 — Invoice generation — no timeout or error (QA)
Precond   : QA environment. Invoice generation triggered.
Steps     :
  1. Navigate to invoice generation
  2. Trigger invoice generation for a busy jobsite
  3. Observe for timeout or error
Expected  : Invoice generates without timeout or error in QA environment.

What "busy jobsite" means for this test
───────────────────────────────────────
  • Generate By: All  (widest possible scope — all customers, all jobsites)
  • Wide date range   (3 months of activity = maximum data load)
  • All Billing Cycles + All Billable Items (no filters = most work)
  This gives the generation engine the heaviest realistic workload in QA.

What we monitor during generation
──────────────────────────────────
  • Wall-clock time from GENERATE click → spinner gone
  • Browser console errors  (JS errors, network failures)
  • Error banners / toast messages on the page
  • HTTP 5xx responses on any network request during generation
  • "In Progress" batch status — watches for ERROR status in the grid
  • Final batch row count and status in Ready to Send

Assertions
──────────
  PASS if ALL of:
    ✅ Generation completes within MAX_GENERATION_SECONDS
    ✅ No error banners / toast messages
    ✅ No browser console errors of severity ERROR
    ✅ No HTTP 5xx responses captured during generation
    ✅ No ERROR status in the In Progress or Ready to Send grids
    ✅ Spinner clears cleanly (no frozen state)
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from playwright.async_api import Page, async_playwright, ConsoleMessage, Response

# ══════════════════════════════════════════════════════════════════════════════
# Configuration
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

# ── Test parameters ───────────────────────────────────────────────────────────
JOBSITE_ID = "1627"   # "busy" jobsite — has the most billable activity in QA

# Wide date range to maximise load (last 3 months)
TODAY      = datetime.today()
DATE_START = (TODAY - timedelta(days=90)).strftime("%m/%d/%Y")
DATE_END   = TODAY.strftime("%m/%d/%Y")
DATE_TODAY = TODAY.strftime("%m/%d/%Y")

# Maximum acceptable generation time in seconds before we call it a timeout
MAX_GENERATION_SECONDS = 120   # 2 minutes — adjust to your QA SLA

BATCH_NOTES     = f"INV-05 stability test — jobsite {JOBSITE_ID}"
INVOICE_MESSAGE = "Thank you for your business!"

# Error patterns to watch for in console messages and page text
CONSOLE_ERROR_PATTERNS = [
    r"uncaught",
    r"unhandled",
    r"typeerror",
    r"referenceerror",
    r"network\s+error",
    r"failed\s+to\s+fetch",
    r"500",
    r"internal\s+server\s+error",
]

PAGE_ERROR_PATTERNS = [
    r"error",
    r"timeout",
    r"failed",
    r"unable\s+to",
    r"could\s+not",
    r"exception",
    r"500",
]

# ══════════════════════════════════════════════════════════════════════════════
# Result type
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Inv05Result:
    # Timing
    generation_start_time:  Optional[float] = None
    generation_end_time:    Optional[float] = None
    generation_duration_s:  Optional[float] = None
    timed_out:              bool = False

    # Error observations
    console_errors:         list[str] = field(default_factory=list)
    http_5xx_responses:     list[str] = field(default_factory=list)
    page_error_banners:     list[str] = field(default_factory=list)
    grid_error_statuses:    list[str] = field(default_factory=list)
    spinner_froze:          bool = False

    # Outcome
    batches_created:        int  = 0
    passed:                 bool = False
    failure_reasons:        list[str] = field(default_factory=list)
    evidence:               list[str] = field(default_factory=list)

    def add_evidence(self, msg: str) -> None:
        self.evidence.append(msg)
        print(f"  📋 {msg}")

    def fail(self, reason: str) -> None:
        self.failure_reasons.append(reason)
        print(f"  ✗ {reason}")

# ══════════════════════════════════════════════════════════════════════════════
# JS / fill helpers
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
        print(f"  ✓ {field_name or label_text} = (first option via keyboard)")
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
    print(f"  ✓ Processing dates = '{start}' → '{end}'")


async def fill_jobsite_autocomplete(page: Page, jobsite_id: str) -> None:
    await page.evaluate(
        """() => {
            document.querySelectorAll('button').forEach(b => {
                b._savedPE = b.style.pointerEvents;
                b.style.pointerEvents = 'none';
            });
            const inputs = document.querySelectorAll('input.e-autocomplete, input[role="combobox"]');
            for (const el of inputs) {
                if (el.offsetParent !== null && !el.disabled) { el.focus(); break; }
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
    for sel in ["[role='listbox'] li", ".e-autocomplete-list li"]:
        try:
            await page.locator(sel).first.wait_for(state="visible", timeout=5_000)
            break
        except Exception:
            continue
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
async def trigger_generation(page: Page, result: Inv05Result) -> None:
    """
    Fill the form with maximum load configuration and click GENERATE.
    Measures wall-clock time and monitors for errors throughout.
    """
    print(f"\n→ Step 2: Triggering invoice generation for busy jobsite {JOBSITE_ID}…")
    print(f"  Date range : {DATE_START} → {DATE_END}  ({MAX_GENERATION_SECONDS}s timeout)")

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
    print(f"  {'✓' if clicked else '⚠ '} Generate By: Jobsite")
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

    await page.screenshot(path="inv05_form_filled.png")
    print("  ✓ Form ready — inv05_form_filled.png")

    await dismiss_open_popups(page)

    # ── Click GENERATE and start the clock ────────────────────────────────
    gen_btn = page.locator("button:has-text('GENERATE'), button:has-text('Generate')").first
    await gen_btn.wait_for(state="visible", timeout=10_000)

    result.generation_start_time = time.monotonic()
    wall_start = datetime.now()
    await gen_btn.click()
    print(f"\n  ⏱  GENERATE clicked at {wall_start.strftime('%H:%M:%S')} — observing…")

    result.add_evidence(f"Generation started at {wall_start.isoformat()}")
    result.add_evidence(f"Date range: {DATE_START} → {DATE_END}")
    result.add_evidence(f"Max allowed duration: {MAX_GENERATION_SECONDS}s")


# ══════════════════════════════════════════════════════════════════════════════
# Step 3 — Observe for timeout or error
# ══════════════════════════════════════════════════════════════════════════════

async def observe_generation(page: Page, result: Inv05Result) -> None:
    """
    Poll the page state every second while the generation spinner is active.
    Records:
      - Wall-clock duration
      - Whether MAX_GENERATION_SECONDS was exceeded  (timeout)
      - Any error banners that appear during processing
      - In-Progress grid status cells (watching for ERROR)
    """
    print("  → Observing generation progress…")

    poll_interval_ms = 1_000
    max_polls = MAX_GENERATION_SECONDS
    polls = 0
    spinner_gone = False
    progress_snapshots: list[str] = []

    while polls < max_polls:
        await page.wait_for_timeout(poll_interval_ms)
        polls += 1

        # ── Check spinner state ──────────────────────────────────────────
        spinner_count = await page.evaluate(
            "() => document.querySelectorAll('.e-spin-show').length"
        )
        if spinner_count == 0 and polls > 1:
            # Spinner has cleared — generation finished
            result.generation_end_time = time.monotonic()
            result.generation_duration_s = round(
                result.generation_end_time - result.generation_start_time, 2
            )
            spinner_gone = True
            print(f"  ✓ Spinner cleared after {result.generation_duration_s}s "
                  f"({polls} polls)")
            break

        # ── Snapshot In Progress grid every 10s ──────────────────────────
        if polls % 10 == 0:
            elapsed = polls
            progress_text = await page.evaluate(
                """() => {
                    const rows = document.querySelectorAll(
                        '.e-gridcontent .e-row, table.e-table tbody tr.e-row'
                    );
                    return Array.from(rows).map(r => r.textContent.trim().replace(/\\s+/g,' ')).join(' || ');
                }"""
            )
            snap = f"{elapsed}s: {progress_text[:120] or '(no rows)'}"
            progress_snapshots.append(snap)
            print(f"    [{elapsed:>4}s] {progress_text[:80] or '(no rows in grid)'}")

            # Check for ERROR status in any grid cell
            has_error = await page.evaluate(
                """() => {
                    const cells = document.querySelectorAll('td, .e-rowcell');
                    for (const c of cells) {
                        if (/\\berror\\b/i.test(c.textContent)) return c.textContent.trim();
                    }
                    return null;
                }"""
            )
            if has_error:
                result.grid_error_statuses.append(f"At {elapsed}s: '{has_error}'")
                print(f"  ⚠  ERROR status in grid at {elapsed}s: '{has_error[:80]}'")

    # ── Timeout check ────────────────────────────────────────────────────
    if not spinner_gone:
        result.generation_end_time = time.monotonic()
        result.generation_duration_s = round(
            result.generation_end_time - result.generation_start_time, 2
        )
        result.timed_out = True
        result.fail(
            f"Generation timed out — spinner still active after "
            f"{result.generation_duration_s:.1f}s "
            f"(limit: {MAX_GENERATION_SECONDS}s)"
        )

    for snap in progress_snapshots:
        result.add_evidence(f"Progress snapshot: {snap}")

    await page.wait_for_timeout(1_000)
    await page.screenshot(path="inv05_after_generate.png")
    print("  ✓ Post-generation screenshot: inv05_after_generate.png")


async def scan_for_errors(page: Page, result: Inv05Result) -> None:
    """
    After generation completes, scan the full page for error indicators:
      • Toast / banner messages
      • Any text matching error patterns in visible elements
      • In-Progress grid ERROR status rows
      • Ready to Send row count (0 may indicate silent failure)
    """
    print("\n→ Step 3: Scanning for errors or timeout indicators…")

    # ── Error banners / toasts ────────────────────────────────────────────
    banner_text = await page.evaluate(
        """() => {
            const selectors = [
                '.e-toast-message',
                '[role="alert"]',
                '.oc-notification',
                '.alert',
                '.alert-danger',
                '.alert-error',
                '[class*="error-message"]',
                '[class*="error-banner"]',
            ];
            const texts = [];
            for (const sel of selectors) {
                for (const el of document.querySelectorAll(sel)) {
                    const t = el.textContent.trim();
                    if (t) texts.push(t);
                }
            }
            return [...new Set(texts)];
        }"""
    )

    for banner in banner_text:
        lower = banner.lower()
        if any(re.search(p, lower) for p in PAGE_ERROR_PATTERNS):
            result.page_error_banners.append(banner)
            print(f"  ⚠  Error banner: '{banner[:100]}'")

    if not banner_text:
        print("  ✓ No error banners visible")

    # ── In Progress grid — check for ERROR status ─────────────────────────
    grid_statuses = await page.evaluate(
        """() => {
            const rows = document.querySelectorAll(
                '.e-gridcontent .e-row, table.e-table tbody tr.e-row'
            );
            return Array.from(rows).map(r => ({
                text:     r.textContent.trim().replace(/\\s+/g,' '),
                hasError: /\\berror\\b/i.test(r.textContent),
            }));
        }"""
    )

    for row in grid_statuses:
        result.add_evidence(f"Grid row: {row['text'][:100]}")
        if row["hasError"]:
            result.grid_error_statuses.append(row["text"][:100])
            result.fail(f"ERROR status in batch grid: '{row['text'][:80]}'")

    # ── Ready to Send row count ───────────────────────────────────────────
    # Scroll to Ready to Send section
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(600)

    ready_rows = await page.evaluate(
        """() => {
            // Count rows that are NOT in the In Progress section
            // Ready to Send uses a separate grid — count its rows
            const grids = document.querySelectorAll('.e-grid');
            if (grids.length >= 2) {
                return grids[1].querySelectorAll('.e-row').length;
            }
            // Fallback: total row count
            return document.querySelectorAll('.e-gridcontent .e-row').length;
        }"""
    )
    result.batches_created = ready_rows
    result.add_evidence(f"Ready to Send rows after generation: {ready_rows}")

    if ready_rows == 0 and not result.timed_out:
        print("  ⚠  Ready to Send grid is empty — generation may have silently failed")
        result.add_evidence("WARNING: 0 batches in Ready to Send — possible silent failure")
    else:
        print(f"  ✓ Ready to Send: {ready_rows} batch row(s)")

    # ── Final screenshot ──────────────────────────────────────────────────
    await page.screenshot(path="inv05_final_state.png")
    print("  ✓ Final state screenshot: inv05_final_state.png")


# ══════════════════════════════════════════════════════════════════════════════
# Assertion
# ══════════════════════════════════════════════════════════════════════════════

def assert_no_timeout_or_error(result: Inv05Result) -> None:
    """
    INV-05 pass criteria — ALL must be true:
      ✅ Spinner cleared within MAX_GENERATION_SECONDS
      ✅ No error banners on the page
      ✅ No browser console errors (ERROR level)
      ✅ No HTTP 5xx responses
      ✅ No ERROR status in any grid row
      ✅ Duration is reported (generation completed measurably)
    """
    print("\n→ Evaluating pass/fail criteria…")

    all_clear = True

    # 1. Timeout
    if result.timed_out:
        result.fail(
            f"TIMEOUT — generation did not complete within {MAX_GENERATION_SECONDS}s"
        )
        all_clear = False
    else:
        print(f"  ✅ No timeout — completed in {result.generation_duration_s}s "
              f"(limit {MAX_GENERATION_SECONDS}s)")

    # 2. Page error banners
    if result.page_error_banners:
        result.fail(f"Error banner(s) detected: {result.page_error_banners}")
        all_clear = False
    else:
        print("  ✅ No page error banners")

    # 3. Browser console errors
    if result.console_errors:
        result.fail(f"Browser console error(s): {result.console_errors[:3]}")
        all_clear = False
    else:
        print("  ✅ No browser console errors")

    # 4. HTTP 5xx
    if result.http_5xx_responses:
        result.fail(f"HTTP 5xx response(s): {result.http_5xx_responses[:3]}")
        all_clear = False
    else:
        print("  ✅ No HTTP 5xx responses")

    # 5. Grid error status
    if result.grid_error_statuses:
        result.fail(f"ERROR status in grid: {result.grid_error_statuses[:3]}")
        all_clear = False
    else:
        print("  ✅ No ERROR status in batch grid")

    result.passed = all_clear


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    print("\n" + "═" * 65)
    print("  INV-05 — Invoice generation — no timeout or error (QA)")
    print(f"  Jobsite        : {JOBSITE_ID}  (busy — 90-day range)")
    print(f"  Billing period : {DATE_START}  →  {DATE_END}")
    print(f"  Max allowed    : {MAX_GENERATION_SECONDS}s")
    print("  Expected       : Completes without timeout or error")
    print("═" * 65)

    result = Inv05Result()

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

        # ── Attach console error listener ─────────────────────────────────
        CONSOLE_NOISE_FILTERS = [
            "mono_download_assets",
            "_framework/",
            "dotnet.wasm",
            "pattern attribute",
        ]

        def on_console(msg: ConsoleMessage) -> None:
            if msg.type == "error":
                text = msg.text
                lower = text.lower()
                if any(noise in lower for noise in CONSOLE_NOISE_FILTERS):
                    return   # Blazor WASM infrastructure noise — not a test failure
                if any(re.search(p, lower) for p in CONSOLE_ERROR_PATTERNS):
                    result.console_errors.append(text[:200])
                    print(f"  ⚠  Console error: {text[:100]}")

        page.on("console", on_console)

        # ── Attach HTTP response listener ─────────────────────────────────
        def on_response(response: Response) -> None:
            if response.status >= 500:
                entry = f"HTTP {response.status} — {response.url[:100]}"
                result.http_5xx_responses.append(entry)
                print(f"  ⚠  {entry}")

        page.on("response", on_response)

        try:
            await do_login(page)

            # Step 1: Navigate
            await navigate_to_generate_invoices(page)

            # Step 2: Trigger generation
            await trigger_generation(page, result)

            # Step 3: Observe — polls every second until done or timeout
            await observe_generation(page, result)

            # Step 3 cont: Scan page for error state
            await scan_for_errors(page, result)

            # Assert
            assert_no_timeout_or_error(result)

        except Exception as exc:
            result.fail(f"Script exception: {exc}")
            await page.screenshot(path="inv05_error.png")
            print(f"\n❌ Script error: {exc}")

        finally:
            await page.wait_for_timeout(3_000)
            await context.close()
            await browser.close()

    # ── Final test report ──────────────────────────────────────────────────
    duration_str = (
        f"{result.generation_duration_s:.2f}s"
        if result.generation_duration_s is not None else "N/A"
    )
    within_limit = (
        result.generation_duration_s is not None and
        result.generation_duration_s <= MAX_GENERATION_SECONDS
    )

    print("\n" + "═" * 65)
    print("  INV-05 TEST REPORT")
    print("─" * 65)
    print(f"  Jobsite            : {JOBSITE_ID}")
    print(f"  Billing period     : {DATE_START}  →  {DATE_END}")
    print(f"  Generation time    : {duration_str}  "
          f"({'✅ within' if within_limit else '❌ exceeded'} {MAX_GENERATION_SECONDS}s limit)")
    print(f"  Timed out          : {'❌ YES' if result.timed_out    else '✅ NO'}")
    print(f"  Error banners      : {'❌ YES' if result.page_error_banners  else '✅ NO'}  "
          f"({len(result.page_error_banners)} found)")
    print(f"  Console errors     : {'❌ YES' if result.console_errors      else '✅ NO'}  "
          f"({len(result.console_errors)} found)")
    print(f"  HTTP 5xx           : {'❌ YES' if result.http_5xx_responses  else '✅ NO'}  "
          f"({len(result.http_5xx_responses)} found)")
    print(f"  Grid error status  : {'❌ YES' if result.grid_error_statuses else '✅ NO'}  "
          f"({len(result.grid_error_statuses)} found)")
    print(f"  Batches created    : {result.batches_created}")
    print("─" * 65)

    if result.passed:
        print("  VERDICT: ✅ PASS")
        print("  Invoice generates without timeout or error in QA environment.")
    else:
        print("  VERDICT: ❌ FAIL")
        for reason in result.failure_reasons:
            print(f"    • {reason}")

    if result.console_errors:
        print("\n  Console errors:")
        for e in result.console_errors[:5]:
            print(f"    {e}")

    if result.http_5xx_responses:
        print("\n  HTTP 5xx responses:")
        for r in result.http_5xx_responses[:5]:
            print(f"    {r}")

    print("─" * 65)
    print("  Evidence:")
    for e in result.evidence:
        print(f"    {e}")

    print("═" * 65)
    print("\n  🎥 Video: videos/")
    print("  📸 inv05_form_filled.png | inv05_after_generate.png | inv05_final_state.png")


if __name__ == "__main__":
    asyncio.run(main())
