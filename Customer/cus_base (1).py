"""
cus_base.py
───────────
Shared helpers for the Customer QA suite.
Selectors based on confirmed placeholder text from the actual UI.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from playwright.async_api import Page

# ── Constants ────────────────────────────────────────────────────────────────

LOGIN_URL = (
    "https://dw1qa.b2clogin.com/dw1qa.onmicrosoft.com/b2c_1_qa_signin/oauth2/v2.0/authorize"
    "?client_id=d7d76a18-ff69-445b-8c0e-e3c2d441ae0a"
    "&redirect_uri=https%3A%2F%2Fqa.wasteapplications.com%2FAccount%2FLogin"
    "&response_type=code%20id_token"
    "&scope=openid%20profile%20https%3A%2F%2Fdw1qa.onmicrosoft.com%2F0170418f-5650-4a29-b1e2-ebf4a97954c3%2FAPI.Access"
    "&response_mode=form_post"
)

VALID_EMAIL    = "kevin.clarke@wasteapplications.com"
VALID_PASSWORD = "Tuesday19@@@@"

KNOWN_CUSTOMER = {
    "id":   "16373",
    "name": "Malone-Miller",
}


def new_customer() -> dict:
    uid = uuid.uuid4().hex[:6].upper()
    return {
        "name":   f"Auto Customer {uid}",
        "street": "123 Test Street",
        "city":   "Atlanta",
        "state":  "GA",
        "zip":    "30301",
        "first":  "Auto",
        "last":   f"User{uid}",
        "phone":  "4045550100",
        "email":  f"auto.{uid.lower()}@wasteapplications.com",
    }


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class TestResult:
    test_id: str
    title:   str
    passed:  bool = False
    logs:    list = field(default_factory=list)
    failure_reasons: list = field(default_factory=list)

    def ok(self, msg):
        self.logs.append(f"  ✓ {msg}"); print(f"  ✓ {msg}")

    def fail(self, msg):
        self.failure_reasons.append(msg)
        self.logs.append(f"  ✗ {msg}"); print(f"  ✗ {msg}")

    def log(self, msg):
        self.logs.append(f"    {msg}"); print(f"    {msg}")

    def print_report(self):
        verdict = "PASS" if self.passed else "FAIL"
        sep = "=" * 65
        print(f"\n{sep}\n  {self.test_id} -- {self.title}\n{'-'*65}")
        print(f"  VERDICT: {verdict}")
        for r in self.failure_reasons:
            print(f"    • {r}")
        print(sep)


# ── Auth ─────────────────────────────────────────────────────────────────────

async def do_login(page: Page) -> None:
    print("\n→ Logging in…")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
    await page.wait_for_timeout(2_000)
    await page.locator('input[type="email"]').first.fill(VALID_EMAIL)
    await page.wait_for_timeout(500)
    await page.locator("button#next, button[type='submit']").first.click()
    await page.wait_for_timeout(1_500)
    await page.locator('input[type="password"]').first.fill(VALID_PASSWORD)
    await page.wait_for_timeout(500)
    await page.locator("button#next, button[type='submit']").first.click()
    await page.wait_for_url("**/home", timeout=30_000)
    await page.wait_for_load_state("networkidle", timeout=20_000)
    await page.wait_for_timeout(2_000)
    print("  ✓ Logged in\n")


# ── Discard dialog ────────────────────────────────────────────────────────────

async def dismiss_discard_dialog(page: Page) -> None:
    await page.wait_for_timeout(600)
    for sel in [
        "button:has-text('Yes')",
        "button:has-text('Continue')",
        "button:has-text('Discard')",
        "button:has-text('Confirm')",
        "button:has-text('Leave')",
        "button:has-text('OK')",
        "[class*='confirm'] button",
        "[class*='dialog'] button:last-child",
    ]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            print(f"  ✓ Discard dialog dismissed via: {sel}")
            await page.wait_for_timeout(500)
            return


# ── Navigation ────────────────────────────────────────────────────────────────

async def nav_to_customers(page: Page) -> None:
    print("\n→ Navigating to Customers…")
    await dismiss_open_popups(page)
    if "Customer/Customer" not in page.url:
        await page.goto(
            "https://qa.wasteapplications.com/Modules/Customer/Customer",
            wait_until="domcontentloaded", timeout=20_000,
        )
    await wait_spinners_gone(page)
    await page.wait_for_timeout(1_500)
    await dismiss_discard_dialog(page)
    print("  ✓ On Customers page")


async def open_customer_by_id(page: Page, customer_id: str) -> None:
    print(f"\n→ Opening customer {customer_id}…")
    await nav_to_customers(page)
    link = page.locator(f"a:has-text('{customer_id}')").first
    if await link.count() > 0:
        await link.click()
    else:
        await search_customer(page, customer_id)
        await page.wait_for_timeout(800)
        link = page.locator(f"a:has-text('{customer_id}')").first
        if await link.count() > 0:
            await link.click()
    await wait_spinners_gone(page)
    await page.wait_for_timeout(1_500)
    print(f"  ✓ Customer {customer_id} opened")


async def search_customer(page: Page, term: str) -> None:
    search = page.locator(
        "input[placeholder*='Search Customer' i], input[placeholder*='search' i]"
    ).first
    await search.wait_for(state="visible", timeout=10_000)
    await search.fill("")
    await search.fill(term)
    await page.wait_for_timeout(1_500)
    await wait_spinners_gone(page)


async def click_new_customer(page: Page) -> None:
    for sel in ["button:has-text('NEW CUSTOMER')", "button:has-text('New Customer')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(2_000)
            await wait_spinners_gone(page)
            print("  ✓ New Customer dialog opened")
            return
    raise RuntimeError("NEW CUSTOMER button not found")


# ── Core field filler using placeholder ──────────────────────────────────────

async def fill_placeholder(page: Page, placeholder: str, value: str, log_name: str) -> bool:
    """
    Fill a Syncfusion float-input by its placeholder text.
    Tries direct input first, then JS value injection.
    """
    loc = page.locator(f"input[placeholder='{placeholder}']").first
    if await loc.count() == 0:
        # Try partial match
        loc = page.locator(f"input[placeholder*='{placeholder.rstrip(' *')}']").first
    if await loc.count() > 0:
        await loc.scroll_into_view_if_needed()
        await loc.click()
        await loc.triple_click()
        await loc.fill(value)
        await page.wait_for_timeout(200)
        print(f"  ✓ {log_name} filled")
        return True
    print(f"  ⚠  {log_name} not found (placeholder: '{placeholder}')")
    return False


async def fill_by_label(page: Page, label: str, value: str, log_name: str) -> None:
    # Try placeholder first (confirmed pattern from UI)
    if await fill_placeholder(page, label, value, log_name):
        return
    # Fallback: e-float-text label → sibling input
    loc = page.locator(f"label.e-float-text:has-text('{label}')").first
    if await loc.count() > 0:
        inp = page.locator(f"label.e-float-text:has-text('{label}') ~ input, "
                           f"label.e-label-bottom:has-text('{label}') ~ input").first
        if await inp.count() > 0:
            await inp.triple_click()
            await inp.fill(value)
            print(f"  ✓ {log_name} filled (label fallback)")
            return
    print(f"  ⚠  {log_name} field not found")


async def fill_masked_input(page: Page, placeholder: str, value: str, log_name: str) -> None:
    loc = page.locator(f"input[placeholder='{placeholder}'], "
                       f"input[placeholder*='{placeholder.rstrip(' *')}']").first
    if await loc.count() > 0:
        await loc.scroll_into_view_if_needed()
        await loc.click()
        await loc.fill("")
        for ch in value:
            await page.keyboard.type(ch, delay=50)
        print(f"  ✓ {log_name} filled (masked)")
        return
    print(f"  ⚠  {log_name} masked field not found (placeholder: '{placeholder}')")


async def fill_dropdown(page: Page, placeholder: str, value: str, log_name: str) -> None:
    """
    Syncfusion dropdown — click the wrapper span, type, pick first match.
    """
    # The visible wrapper is a span.e-ddl; the hidden input has the placeholder
    wrapper = page.locator(
        f"span.e-ddl:has(input[placeholder='{placeholder}']), "
        f"span.e-ddl:has(input[placeholder*='{placeholder.rstrip(' *')}'])"
    ).first

    if await wrapper.count() > 0:
        await wrapper.scroll_into_view_if_needed()
        await wrapper.click()
        await page.wait_for_timeout(600)
        # Type to filter
        await page.keyboard.type(value, delay=80)
        await page.wait_for_timeout(600)
        # Pick first list item
        for opt_sel in [
            f"[role='listbox'] li:has-text('{value}')",
            "[role='listbox'] li.e-list-item:first-child",
            "[role='option']:first-child",
        ]:
            opt = page.locator(opt_sel).first
            if await opt.count() > 0 and await opt.is_visible():
                await opt.click()
                print(f"  ✓ {log_name} selected: {value}")
                return
        await page.keyboard.press("Enter")
        print(f"  ✓ {log_name} selected via Enter")
        return

    # Fallback: direct input
    inp = page.locator(f"input[placeholder='{placeholder}']").first
    if await inp.count() > 0:
        await inp.click()
        await page.keyboard.type(value, delay=80)
        await page.wait_for_timeout(600)
        opt = page.locator("[role='listbox'] li").first
        if await opt.count() > 0:
            await opt.click()
        else:
            await page.keyboard.press("Enter")
        print(f"  ✓ {log_name} filled (input fallback)")
        return

    print(f"  ⚠  {log_name} dropdown not found (placeholder: '{placeholder}')")


async def fill_step1(page: Page, data: dict) -> None:
    print("  → Filling Step 1…")
    await fill_placeholder(page, "Customer Name *", data["name"],   "Customer Name")
    await fill_dropdown(   page, "Billing Address *", data["street"], "Billing Address")
    await fill_placeholder(page, "City *",           data["city"],   "City")
    await fill_dropdown(   page, "State *",           data["state"],  "State")
    await fill_placeholder(page, "Zip Code *",        data["zip"],    "Zip Code")
    await page.wait_for_timeout(500)
    for sel in ["button:has-text('NEXT')", "button:has-text('Next')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(2_000)
            await wait_spinners_gone(page)
            print("  ✓ Step 1 complete — NEXT clicked")
            return


async def fill_step2(page: Page, data: dict) -> None:
    print("  → Filling Step 2…")
    await fill_placeholder(page, "First Name *",     data["first"], "First Name")
    await fill_placeholder(page, "Last Name",         data["last"],  "Last Name")
    await fill_masked_input(page, "Phone Number 1 *", data["phone"], "Phone")
    await fill_placeholder(page, "Email 1 *",         data["email"], "Email")
    await page.wait_for_timeout(500)
    for sel in ["button:has-text('CREATE')", "button:has-text('Create')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0:
            try:
                await btn.wait_for(state="visible", timeout=8_000)
                await btn.click(force=True)
            except Exception:
                await page.evaluate(
                    "() => document.querySelector('button[b-olf07bymmj]')?.click()"
                )
            await page.wait_for_timeout(3_000)
            await wait_spinners_gone(page)
            print("  ✓ Step 2 complete — CREATE clicked")
            return
    raise RuntimeError("CREATE button not found in Step 2")


# ── Waits & utilities ─────────────────────────────────────────────────────────

async def wait_spinners_gone(page: Page, timeout: int = 15_000) -> None:
    for sel in [".e-spin-show", ".e-spinner-pane.e-spin-show"]:
        try:
            await page.locator(sel).first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass
    await page.wait_for_timeout(300)


async def dismiss_open_popups(page: Page) -> None:
    for sel in ["button:has-text('Close')", "button[aria-label='Close']",
                ".e-dlg-closeicon-btn"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(300)


async def get_all_text_blocks(page: Page) -> list[str]:
    return await page.evaluate("""() => {
        const seen = new Set(); const out = [];
        for (const el of document.querySelectorAll('*')) {
            if (el.offsetParent === null) continue;
            const t = el.textContent.trim().replace(/\\s+/g,' ');
            if (t.length >= 2 && t.length <= 200 && !seen.has(t)) {
                seen.add(t); out.push(t);
            }
        }
        return out;
    }""")


async def get_grid_row_count(page: Page) -> int:
    return await page.evaluate(
        "() => document.querySelectorAll('.e-gridcontent .e-row').length"
    )


async def get_grid_rows_text(page: Page) -> list[str]:
    return await page.evaluate("""() =>
        Array.from(document.querySelectorAll('.e-gridcontent .e-row'))
        .map(r => r.textContent.trim().replace(/\\s+/g,' '))""")
