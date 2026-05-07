"""
inv06_customer_header.py
────────────────────────
Test Case : INV-06 — Invoice displays customer name and address correctly
Precond   : Invoice generated for a known customer (already exists in system)
Steps     :
  1. Open generated invoice
  2. Check customer name and billing address in header
Expected  : Customer name and billing address match the customer record exactly.

Approach
────────
  No generation needed — precondition states invoice already exists.
  Navigate Accounting > Generate Invoices > SENT BATCHES, open the most
  recent batch for the known customer, open the invoice, extract the
  header, compare every field to the known customer record.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Page, async_playwright

# ══════════════════════════════════════════════════════════════════════════════
# Configuration — update to match your QA database
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

KNOWN_CUSTOMER = {
    "id":     "1627",
    "name":   "Waste Applications QA Customer",
    "street": "131 Glenn Bridge Rd",
    "city":   "Arden",
    "state":  "NC",
    "zip":    "28704",
}

# ══════════════════════════════════════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FieldResult:
    name:    str
    expected: str
    found:   str
    matched: bool


@dataclass
class Inv06Result:
    fields:          list[FieldResult] = field(default_factory=list)
    invoice_url:     str               = ""
    raw_header:      str               = ""
    passed:          bool              = False
    failure_reasons: list[str]         = field(default_factory=list)
    evidence:        list[str]         = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.evidence.append(msg)
        print(f"  📋 {msg}")

    def fail(self, reason: str) -> None:
        self.failure_reasons.append(reason)
        print(f"  ✗  {reason}")

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
# Step 1 — Open generated invoice
# ══════════════════════════════════════════════════════════════════════════════

async def open_invoice(page: Page, result: Inv06Result) -> None:
    print("\n→ Step 1: Opening generated invoice…")

    # Wait for nav bar to mount
    print("  → Waiting for nav bar…")
    await page.wait_for_function(
        """() => Array.from(document.querySelectorAll('button,a,span,li'))
                      .some(el => /accounting/i.test(el.textContent)
                               && el.offsetParent !== null)""",
        timeout=30_000,
    )
    print("  ✓ Nav bar ready")

    # Click Accounting
    for sel in ["button:has-text('Accounting')", "a:has-text('Accounting')",
                "span:has-text('Accounting')", "li:has-text('Accounting')"]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=4_000)
            await loc.click()
            print("  ✓ Accounting menu opened")
            break
        except Exception:
            continue
    await page.wait_for_timeout(1_000)

    # Click Generate Invoices
    for sel in ["a[href*='GenerateInvoices']", "a:has-text('Generate Invoices')",
                "span:has-text('Generate Invoices')"]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=4_000)
            await loc.click()
            print("  ✓ Generate Invoices clicked")
            break
        except Exception:
            continue

    await page.wait_for_function(
        """() => !window.location.href.endsWith('/home')
              && document.querySelectorAll('.e-control').length > 0""",
        timeout=25_000,
    )
    await page.wait_for_timeout(800)
    print(f"  ✓ Generate Invoices loaded — {page.url}")
    await page.screenshot(path="inv06_step1_gen_invoices.png")

    # Click SENT BATCHES
    print("  → Opening Sent Batches…")
    for sel in ["a:has-text('Sent Batches')", "button:has-text('Sent Batches')",
                "span:has-text('SENT BATCHES')", "a:has-text('SENT BATCHES')",
                "text=SENT BATCHES", "text=Sent Batches"]:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=5_000)
            await loc.click()
            print(f"  ✓ Sent Batches clicked via: {sel}")
            break
        except Exception:
            continue
    else:
        # JS fallback
        clicked = await page.evaluate(
            """() => {
                for (const el of document.querySelectorAll('a,button,span')) {
                    if (/sent.?batch/i.test(el.textContent) && el.offsetParent !== null) {
                        el.click(); return el.textContent.trim();
                    }
                }
                return null;
            }"""
        )
        if clicked:
            print(f"  ✓ Sent Batches clicked via JS: {clicked}")
        else:
            await page.screenshot(path="inv06_no_sent_batches.png")
            raise RuntimeError(
                "SENT BATCHES tab not found — see inv06_no_sent_batches.png"
            )

    await page.wait_for_function(
        "() => document.querySelectorAll('.e-spin-show').length === 0",
        timeout=15_000,
    )
    await page.wait_for_timeout(800)
    await page.screenshot(path="inv06_step1_sent_batches.png")
    print("  ✓ Sent Batches open — inv06_step1_sent_batches.png")

    # Find batch for known customer — try customer match first, fall back to first row
    result.log(f"Looking for batch matching customer: '{KNOWN_CUSTOMER['name']}'")
    batch_link = None
    rows = page.locator(".e-gridcontent .e-row, table tbody tr")
    row_count = await rows.count()
    result.log(f"Batch grid rows found: {row_count}")

    for i in range(min(row_count, 20)):
        row = rows.nth(i)
        row_text = await row.inner_text()
        if (KNOWN_CUSTOMER["name"].lower() in row_text.lower() or
                KNOWN_CUSTOMER["id"] in row_text):
            batch_link = row.locator("a").first
            result.log(f"Customer matched in row {i}: {row_text[:80]}")
            break

    if not batch_link or await batch_link.count() == 0:
        batch_link = page.locator(".e-gridcontent .e-row a, table tbody tr a").first
        result.log("No customer-specific row — using first available batch")

    if await batch_link.count() == 0:
        await page.screenshot(path="inv06_no_batch.png")
        raise RuntimeError("No batch links in Sent Batches grid")

    batch_label = (await batch_link.inner_text()).strip()
    result.log(f"Opening batch: '{batch_label}'")
    await batch_link.click()
    try:
        await page.wait_for_load_state("networkidle", timeout=30_000)
    except Exception:
        pass  # networkidle may never fire on Blazor SPA
    await page.wait_for_function(
        "() => document.querySelectorAll('.e-spin-show').length === 0",
        timeout=15_000,
    )
    await page.wait_for_timeout(800)
    await page.screenshot(path="inv06_step1_batch_open.png")
    print(f"  ✓ Batch '{batch_label}' open — inv06_step1_batch_open.png")

    # Open individual invoice link if present
    inv_link = page.locator(
        "a[href*='Invoice'], a[href*='invoice'], "
        "a:has-text('View'), a:has-text('INV'), "
        ".e-gridcontent .e-row a"
    ).first

    if await inv_link.count() > 0:
        inv_label = (await inv_link.inner_text()).strip()
        result.log(f"Opening invoice: '{inv_label}'")
        await inv_link.click()
        try:
        await page.wait_for_load_state("networkidle", timeout=30_000)
    except Exception:
        pass  # networkidle may never fire on Blazor SPA
        await page.wait_for_function(
            "() => document.querySelectorAll('.e-spin-show').length === 0",
            timeout=15_000,
        )
        await page.wait_for_timeout(800)
        print(f"  ✓ Invoice '{inv_label}' open")
    else:
        result.log("No individual invoice link — header read from batch detail")

    result.invoice_url = page.url
    await page.screenshot(path="inv06_step1_invoice.png")
    print(f"  ✓ Invoice page ready — inv06_step1_invoice.png")
    print(f"    URL: {page.url}")

# ══════════════════════════════════════════════════════════════════════════════
# Step 2 — Check customer name and billing address in header
# ══════════════════════════════════════════════════════════════════════════════

async def check_header(page: Page, result: Inv06Result) -> None:
    print("\n→ Step 2: Checking customer name and billing address in header…")

    # Collect all meaningful text blocks from the invoice page
    blocks: list[str] = await page.evaluate(
        """() => {
            const seen = new Set();
            const out  = [];
            for (const el of document.querySelectorAll(
                'p,span,div,td,th,h1,h2,h3,h4,li,address,label,strong,b'
            )) {
                const t = el.textContent.trim().replace(/\\s+/g,' ');
                if (t.length >= 3 && t.length <= 400 && !seen.has(t)) {
                    seen.add(t);
                    out.push(t);
                }
            }
            return out.slice(0, 150);
        }"""
    )

    result.log(f"Text blocks collected from invoice page: {len(blocks)}")
    result.raw_header = " | ".join(blocks[:15])
    result.log(f"Sample blocks: {blocks[:8]}")

    def find_block(value: str) -> str:
        for b in blocks:
            if value.lower() in b.lower():
                return b
        return ""

    # Field-by-field checks
    checks = [
        ("Customer Name",  KNOWN_CUSTOMER["name"],   False),
        ("Street Address", KNOWN_CUSTOMER["street"],  True),
        ("City",           KNOWN_CUSTOMER["city"],    True),
        ("State",          KNOWN_CUSTOMER["state"],   True),
        ("ZIP Code",       KNOWN_CUSTOMER["zip"],     True),
    ]

    for field_name, expected, case_sensitive in checks:
        block = find_block(expected)
        if case_sensitive:
            matched = expected in block
        else:
            matched = bool(block)

        fr = FieldResult(
            name=field_name,
            expected=expected,
            found=block[:100] if block else "(not found on page)",
            matched=matched,
        )
        result.fields.append(fr)

        icon = "✅" if matched else "❌"
        print(f"\n  {icon} [{field_name}]")
        print(f"       Expected : '{expected}'")
        print(f"       Context  : '{fr.found}'")

        if not matched:
            result.fail(f"[{field_name}] '{expected}' not found in invoice header")

    # Bonus: all address components in one block
    combined = next(
        (b for b in blocks if all(
            c.lower() in b.lower() for c in [
                KNOWN_CUSTOMER["street"],
                KNOWN_CUSTOMER["city"],
                KNOWN_CUSTOMER["state"],
                KNOWN_CUSTOMER["zip"],
            ]
        )),
        None,
    )
    if combined:
        print(f"\n  ✅ [Full Address Block] all components together:")
        print(f"       '{combined[:120]}'")
        result.log(f"Full address block: '{combined[:120]}'")
    else:
        print(f"\n  ⚠  [Full Address Block] address components not in one block")

    result.passed = not result.failure_reasons
    await page.screenshot(path="inv06_step2_header_check.png")
    print("\n  ✓ Header check screenshot: inv06_step2_header_check.png")

# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    print("\n" + "═" * 65)
    print("  INV-06 — Invoice displays customer name and address correctly")
    print(f"  Customer : {KNOWN_CUSTOMER['name']}  (ID: {KNOWN_CUSTOMER['id']})")
    print(f"  Address  : {KNOWN_CUSTOMER['street']}, "
          f"{KNOWN_CUSTOMER['city']}, "
          f"{KNOWN_CUSTOMER['state']} {KNOWN_CUSTOMER['zip']}")
    print("  Expected : Name and address match customer record exactly")
    print("═" * 65)

    result = Inv06Result()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir="videos/",
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        try:
            await do_login(page)
            await open_invoice(page, result)    # Step 1
            await check_header(page, result)    # Step 2

        except Exception as exc:
            result.fail(f"Script exception: {exc}")
            await page.screenshot(path="inv06_error.png")
            print(f"\n❌ Script error: {exc}")

        finally:
            await page.wait_for_timeout(3_000)
            await context.close()
            await browser.close()

    # ── Test report ────────────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  INV-06 TEST REPORT")
    print("─" * 65)
    print(f"  Invoice URL : {result.invoice_url or 'N/A'}")
    print("─" * 65)
    print("  Field results:")
    for fr in result.fields:
        icon = "✅ PASS" if fr.matched else "❌ FAIL"
        print(f"    {icon}  [{fr.name}]")
        print(f"           Expected : '{fr.expected}'")
        print(f"           Found in : '{fr.found}'")
    print("─" * 65)

    if result.passed:
        print("  VERDICT: ✅ PASS")
        print("  Customer name and billing address match the customer record exactly.")
    else:
        print("  VERDICT: ❌ FAIL")
        for r in result.failure_reasons:
            print(f"    • {r}")

    print("─" * 65)
    print("  Evidence:")
    for e in result.evidence:
        print(f"    {e}")
    print("═" * 65)
    print("\n  🎥 Video: videos/")
    print("  📸 inv06_step1_gen_invoices.png   inv06_step1_sent_batches.png")
    print("     inv06_step1_batch_open.png      inv06_step1_invoice.png")
    print("     inv06_step2_header_check.png")


if __name__ == "__main__":
    asyncio.run(main())
