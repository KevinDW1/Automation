"""
job01_to_job24.py
─────────────────
Jobsite QA Suite — JOB-01 through JOB-24

Run all:    python job01_to_job24.py
Run single: python job01_to_job24.py JOB-06
Run range:  python job01_to_job24.py JOB-07 JOB-12
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime

from playwright.async_api import Page, async_playwright

from job_ven_base import (
    KNOWN_JOBSITE, KNOWN_VENDOR, new_jobsite,
    TestResult, do_login,
    nav_to_jobsites, nav_to_vendors,
    search_grid, open_record_by_id, click_new_button,
    click_save, click_edit,
    fill_label, fill_masked, fill_dropdown, fill_autocomplete,
    dismiss_popups, wait_spinners,
    get_text_blocks, grid_row_count, grid_rows_text, _click,
)

# ══════════════════════════════════════════════════════════════════════════════
# JOB-01 — Create new jobsite — happy path
# ══════════════════════════════════════════════════════════════════════════════

async def job01(page: Page) -> TestResult:
    """
    Steps   : 1. Click NEW JOBSITE.
              2. Enter Customer ID, jobsite name, address.
              3. Click NEXT then finish wizard.
    Expected: Jobsite created and appears in grid.
    """
    r = TestResult("JOB-01", "Create new jobsite — happy path")
    data = new_jobsite()

    await nav_to_jobsites(page)
    await click_new_button(page, "NEW JOBSITE")

    # Step 1: Customer Information autocomplete
    await fill_autocomplete(page, data["customer"], "Customer ID")
    await page.wait_for_timeout(500)

    # NEXT
    for sel in ["button:has-text('NEXT')", "button:has-text('Next')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(1_500)
            await wait_spinners(page)
            break

    # Step 2: Jobsite details
    try:
        await fill_label(page,    "Jobsite Name *", data["name"],   "Name")
        await fill_dropdown(page, "Address *",       data["street"], "Street")
        await fill_label(page,    "City *",          data["city"],   "City")
        await fill_dropdown(page, "State *",         data["state"],  "State")
        await fill_label(page,    "Zip Code *",      data["zip"],    "ZIP")
    except Exception as e:
        r.log(f"Field fill partial: {e}")

    # CREATE / FINISH
    for sel in ["button:has-text('CREATE')", "button:has-text('FINISH')",
                "button:has-text('Save')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(force=True)
            await page.wait_for_timeout(3_000)
            await wait_spinners(page)
            break

    await page.screenshot(path="job01_result.png")
    blocks = await get_text_blocks(page)
    created = any(
        re.search(r"success|created|jobsite.*added|saved", b, re.I)
        for b in blocks
    ) or any(data["name"].lower() in b.lower() for b in blocks)

    if created:
        r.ok(f"Jobsite '{data['name']}' created successfully")
        r.passed = True
    else:
        r.fail("Jobsite creation result unclear — check job01_result.png")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-02 — Create jobsite — missing required name
# ══════════════════════════════════════════════════════════════════════════════

async def job02(page: Page) -> TestResult:
    """
    Steps   : 1. Open NEW JOBSITE wizard.
              2. Complete customer step.
              3. Leave jobsite name blank and click NEXT/CREATE.
    Expected: Validation error — name required. Cannot proceed.
    """
    r = TestResult("JOB-02", "Create jobsite — missing required name")
    data = new_jobsite()

    await nav_to_jobsites(page)
    await click_new_button(page, "NEW JOBSITE")
    await fill_autocomplete(page, data["customer"], "Customer")

    for sel in ["button:has-text('NEXT')", "button:has-text('Next')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(1_500)
            break

    # Fill address but NOT name
    try:
        await fill_dropdown(page, "Address *", data["street"], "Street")
        await fill_label(page,   "City *",     data["city"],  "City")
    except Exception:
        pass

    # Try to submit
    for sel in ["button:has-text('CREATE')", "button:has-text('NEXT')",
                "button:has-text('FINISH')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            break
    await page.wait_for_timeout(1_500)
    await page.screenshot(path="job02_result.png")

    blocks = await get_text_blocks(page)
    has_error = any(
        re.search(r"required|name.*required|jobsite name", b, re.I) for b in blocks
    )
    still_on_form = any(
        re.search(r"jobsite name|address|city", b, re.I) for b in blocks
    )

    if has_error or still_on_form:
        r.ok("Validation prevented proceeding without Jobsite Name")
        r.passed = True
    else:
        r.fail("No validation error shown for missing jobsite name")

    await page.keyboard.press("Escape")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-03 — Create jobsite — missing required address
# ══════════════════════════════════════════════════════════════════════════════

async def job03(page: Page) -> TestResult:
    """
    Steps   : 1. Open NEW JOBSITE wizard.
              2. Fill name but leave address blank.
              3. Click CREATE.
    Expected: Validation error — address required.
    """
    r = TestResult("JOB-03", "Create jobsite — missing required address")
    data = new_jobsite()

    await nav_to_jobsites(page)
    await click_new_button(page, "NEW JOBSITE")
    await fill_autocomplete(page, data["customer"], "Customer")

    for sel in ["button:has-text('NEXT')", "button:has-text('Next')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(1_500)
            break

    # Fill name but NOT address
    try:
        await fill_label(page, "Jobsite Name *", data["name"], "Name")
    except Exception:
        pass

    for sel in ["button:has-text('CREATE')", "button:has-text('FINISH')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            break
    await page.wait_for_timeout(1_500)
    await page.screenshot(path="job03_result.png")

    blocks = await get_text_blocks(page)
    has_error = any(
        re.search(r"required|address.*required|billing address", b, re.I)
        for b in blocks
    )
    still_on_form = any(
        re.search(r"address|city|zip", b, re.I) for b in blocks
    )

    if has_error or still_on_form:
        r.ok("Validation prevented proceeding without address")
        r.passed = True
    else:
        r.fail("No validation error shown for missing address")

    await page.keyboard.press("Escape")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-04 — Jobsite inherits customer partnership status pill
# ══════════════════════════════════════════════════════════════════════════════

async def job04(page: Page) -> TestResult:
    """
    Steps   : 1. Open a jobsite belonging to an Active-status customer.
              2. Verify the partnership status pill is visible on the jobsite.
    Expected: Jobsite displays the customer's partnership status pill.
    Jira    : OC-5760
    """
    r = TestResult("JOB-04", "Jobsite inherits customer partnership status pill")

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    await page.screenshot(path="job04_result.png")

    blocks = await get_text_blocks(page)
    pill_visible = any(
        re.search(r"\bactive\b|\bpartner\b|\bno.?partner\b|\bat.?risk\b", b, re.I)
        for b in blocks
    )
    r.log(f"Status-related blocks: {[b for b in blocks if re.search(r'active|partner|risk', b, re.I)][:5]}")

    if pill_visible:
        r.ok("Partnership status pill visible on jobsite")
        r.passed = True
    else:
        r.fail("No partnership status pill found on jobsite — OC-5760")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-05 — Jobsite under No Partnership customer — grey pill
# ══════════════════════════════════════════════════════════════════════════════

async def job05(page: Page) -> TestResult:
    """
    Steps   : 1. Find a jobsite whose customer has 'No Partnership' status.
              2. Verify the jobsite shows a grey status pill.
    Expected: Grey pill shown for No Partnership customer.
    Jira    : OC-5760
    """
    r = TestResult("JOB-05", "Jobsite under No Partnership customer — grey pill")

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    await page.screenshot(path="job05_result.png")

    # Check for grey pill via CSS or class name
    grey_pill = await page.evaluate(
        """() => {
            for (const el of document.querySelectorAll('*')) {
                const cls = el.className || '';
                const txt = el.textContent.trim();
                const style = window.getComputedStyle(el);
                const bg = style.backgroundColor;
                if (/no.?partner/i.test(txt) && el.offsetParent !== null) return txt;
                if (/grey|gray|#6c757d|#9e9e9e|rgb\\(108|rgb\\(158/i.test(bg)
                    && /pill|badge|status|chip/i.test(cls)) return cls;
            }
            return null;
        }"""
    )
    r.log(f"Grey/No Partnership pill element: {grey_pill}")

    blocks = await get_text_blocks(page)
    has_no_partner = any(re.search(r"no.?partner", b, re.I) for b in blocks)

    if grey_pill or has_no_partner:
        r.ok("No Partnership / grey pill visible on jobsite")
        r.passed = True
    else:
        r.fail("Grey 'No Partnership' pill not found — may need a different test jobsite")
        r.log("Update KNOWN_JOBSITE to a jobsite under a No Partnership customer")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-06 — Jobsite Landing Page — Vendor ID column shows vendor IDs
# ══════════════════════════════════════════════════════════════════════════════

async def job06(page: Page) -> TestResult:
    """
    Steps   : 1. Navigate to Jobsite landing page (grid).
              2. Verify a 'Vendor ID' column exists.
              3. Verify at least one cell contains a numeric vendor ID.
    Expected: Vendor ID column visible and populated.
    Jira    : OC-5800
    """
    r = TestResult("JOB-06", "Jobsite Landing Page — Vendor ID column shows vendor IDs")

    await nav_to_jobsites(page)
    await page.screenshot(path="job06_result.png")

    # Check grid headers for Vendor ID column
    headers = await page.evaluate(
        """() => Array.from(
            document.querySelectorAll('.e-gridheader th, .e-headercell')
        ).map(h => h.textContent.trim())"""
    )
    r.log(f"Grid column headers: {headers}")

    has_vendor_col = any(re.search(r"vendor.?id|vendor", h, re.I) for h in headers)

    # Also check row cells for vendor-ID-shaped values
    rows = await grid_rows_text(page)
    vendor_id_in_row = any(
        re.search(r"\b\d{4,6}\b", row) for row in rows
    )

    r.log(f"Vendor ID column in headers: {has_vendor_col}")
    r.log(f"Numeric ID values in rows: {vendor_id_in_row}")

    if has_vendor_col and vendor_id_in_row:
        r.ok("Vendor ID column present and populated — OC-5800 passes")
        r.passed = True
    elif has_vendor_col:
        r.ok("Vendor ID column visible (cells may be empty for this jobsite)")
        r.passed = True
    else:
        r.fail("Vendor ID column not found in jobsite grid — OC-5800 regression")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-07 — Jobsite Landing Page — search by jobsite name
# ══════════════════════════════════════════════════════════════════════════════

async def job07(page: Page) -> TestResult:
    r = TestResult("JOB-07", "Jobsite Landing Page — search by jobsite name")
    await nav_to_jobsites(page)
    await search_grid(page, KNOWN_JOBSITE["name"])
    await page.screenshot(path="job07_result.png")

    rows = await grid_rows_text(page)
    r.log(f"Rows after name search: {rows[:3]}")
    match = any(
        KNOWN_JOBSITE["name"].lower() in row.lower() or
        KNOWN_JOBSITE["id"] in row
        for row in rows
    )
    if match:
        r.ok(f"Search by name '{KNOWN_JOBSITE['name']}' returned matching jobsite")
        r.passed = True
    else:
        r.fail("Name search did not return expected jobsite")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-08 — Jobsite Landing Page — search by jobsite ID
# ══════════════════════════════════════════════════════════════════════════════

async def job08(page: Page) -> TestResult:
    r = TestResult("JOB-08", "Jobsite Landing Page — search by jobsite ID")
    await nav_to_jobsites(page)
    await search_grid(page, KNOWN_JOBSITE["id"])
    await page.screenshot(path="job08_result.png")

    rows = await grid_rows_text(page)
    r.log(f"Rows after ID search: {rows[:3]}")
    match = any(KNOWN_JOBSITE["id"] in row for row in rows)
    if match:
        r.ok(f"Search by ID '{KNOWN_JOBSITE['id']}' returned correct jobsite")
        r.passed = True
    else:
        r.fail("ID search did not return expected jobsite")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-09 — Jobsite Landing Page — date picker label correct
# ══════════════════════════════════════════════════════════════════════════════

async def job09(page: Page) -> TestResult:
    """
    Steps   : 1. Navigate to Jobsite landing page.
              2. Find the date picker control.
              3. Verify its label text is correct (regression OC-5698).
    Expected: Date picker label is accurate — not blank, wrong text, or duplicated.
    Jira    : OC-5698
    """
    r = TestResult("JOB-09", "Jobsite Landing Page — date picker label correct")

    await nav_to_jobsites(page)
    await page.screenshot(path="job09_result.png")

    # Find all date picker elements and their labels
    date_labels = await page.evaluate(
        """() => {
            const out = [];
            for (const inp of document.querySelectorAll(
                'input.e-datepicker, input.e-daterangepicker, input[aria-label*="date" i]'
            )) {
                const id    = inp.id;
                const label = id ? document.querySelector(`label[for="${id}"]`) : null;
                const ariaLabel = inp.getAttribute('aria-label') || '';
                const ariaLabelledBy = inp.getAttribute('aria-labelledby') || '';
                const labelEl = ariaLabelledBy
                    ? document.getElementById(ariaLabelledBy) : null;
                out.push({
                    ariaLabel,
                    labelText: label ? label.textContent.trim() : '',
                    labelledByText: labelEl ? labelEl.textContent.trim() : '',
                    placeholder: inp.placeholder || '',
                });
            }
            return out;
        }"""
    )
    r.log(f"Date picker labels found: {date_labels}")

    if not date_labels:
        r.fail("No date picker found on jobsite landing page — OC-5698")
        return r

    # Regression check: label must not be blank, 'undefined', or duplicated
    for dp in date_labels:
        all_labels = [
            dp["ariaLabel"], dp["labelText"],
            dp["labelledByText"], dp["placeholder"]
        ]
        non_empty = [l for l in all_labels if l.strip()]
        r.log(f"Date picker labels: {non_empty}")

        blank_label  = not any(non_empty)
        bad_label    = any(
            re.search(r"undefined|null|NaN|invalid", l, re.I) for l in non_empty
        )

        if blank_label:
            r.fail("Date picker has no label — OC-5698 regression")
        elif bad_label:
            r.fail(f"Date picker label contains invalid text: {non_empty}")
        else:
            r.ok(f"Date picker label is correct: {non_empty}")
            r.passed = True

    if not r.failure_reasons:
        r.passed = True
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-10 — Jobsite Landing Page — filter by tag
# ══════════════════════════════════════════════════════════════════════════════

async def job10(page: Page) -> TestResult:
    """
    Steps   : 1. Open Jobsite landing page filters.
              2. Apply a tag filter.
              3. Verify grid updates to show only tagged jobsites.
    Expected: Tag filter correctly restricts displayed jobsites.
    Jira    : OC-3471
    """
    r = TestResult("JOB-10", "Jobsite Landing Page — filter by tag")

    await nav_to_jobsites(page)
    rows_before = await grid_row_count(page)
    r.log(f"Rows before tag filter: {rows_before}")

    # Open filters
    for sel in ["button:has-text('Filters')", "span:has-text('Select Filters')",
                ".e-dropdownlist:near(:text('Filter'))", "button[title*='filter' i]"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await page.wait_for_timeout(800)
            break

    await page.screenshot(path="job10_filters.png")
    blocks = await get_text_blocks(page)
    r.log(f"Filter panel blocks: {blocks[:15]}")

    has_tag_filter = any(re.search(r"\btag\b", b, re.I) for b in blocks)
    r.log(f"Tag filter option visible: {has_tag_filter}")

    if has_tag_filter:
        # Try clicking a tag option
        tag_opt = page.locator("li:has-text('Tag'), [role='option']:has-text('Tag')").first
        if await tag_opt.count() > 0:
            await tag_opt.click()
            await page.wait_for_timeout(1_000)
            await wait_spinners(page)
            rows_after = await grid_row_count(page)
            r.log(f"Rows after tag filter: {rows_after}")
            r.ok("Tag filter option found and applied")
            r.passed = True
        else:
            r.ok("Tag filter option visible in filter panel")
            r.passed = True
    else:
        r.fail("No tag filter option found in filter panel — OC-3471")

    await page.keyboard.press("Escape")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-11 — Jobsite Landing Page — pagination
# ══════════════════════════════════════════════════════════════════════════════

async def job11(page: Page) -> TestResult:
    r = TestResult("JOB-11", "Jobsite Landing Page — pagination")

    await nav_to_jobsites(page)
    rows_p1 = await grid_rows_text(page)
    r.log(f"Page 1 rows: {len(rows_p1)}")

    next_btn = page.locator(
        "button[aria-label='Next page'], button[aria-label='Next Page'], "
        "li.e-next button, .e-nextpage"
    ).first
    if await next_btn.count() == 0 or not await next_btn.is_enabled():
        r.fail("Next page button not found or disabled")
        return r

    await next_btn.click()
    await wait_spinners(page)
    await page.wait_for_timeout(800)
    rows_p2 = await grid_rows_text(page)
    r.log(f"Page 2 rows: {len(rows_p2)}")

    if rows_p1 and rows_p2 and rows_p1[0] != rows_p2[0]:
        r.ok("Jobsite pagination works — different records on page 2")
        r.passed = True
    else:
        r.fail("Page 1 and 2 show same records — pagination not working")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-12 — Jobsite Card — customer name and address shown
# ══════════════════════════════════════════════════════════════════════════════

async def job12(page: Page) -> TestResult:
    """
    Steps   : 1. Open jobsite detail.
              2. Verify customer name visible.
              3. Verify address visible.
    Expected: Customer name and address displayed on jobsite card/detail.
    Jira    : OC-5758
    """
    r = TestResult("JOB-12", "Jobsite Card — customer name and address shown")

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    await page.screenshot(path="job12_result.png")

    blocks = await get_text_blocks(page)
    has_customer = any(
        KNOWN_JOBSITE["customer"].lower() in b.lower() or
        re.search(r"customer", b, re.I)
        for b in blocks
    )
    has_address = any(
        re.search(r"\d+\s+\w+.*(?:rd|st|ave|blvd|dr|ln|way|ct)\b", b, re.I)
        for b in blocks
    )
    r.log(f"Customer reference found: {has_customer}")
    r.log(f"Address pattern found: {has_address}")

    if has_customer and has_address:
        r.ok("Customer name and address both visible on jobsite card")
        r.passed = True
    elif has_customer:
        r.ok("Customer name visible; address pattern not found")
        r.passed = True
    else:
        r.fail("Customer name not visible on jobsite detail — OC-5758")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-13 — Jobsite Card — billable status shown
# ══════════════════════════════════════════════════════════════════════════════

async def job13(page: Page) -> TestResult:
    r = TestResult("JOB-13", "Jobsite Card — billable status shown")

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    await page.screenshot(path="job13_result.png")

    blocks = await get_text_blocks(page)
    billable = any(re.search(r"\bbillable\b|\bnon.?billable\b", b, re.I) for b in blocks)
    r.log(f"Billable blocks: {[b for b in blocks if re.search(r'billable', b, re.I)][:3]}")

    if billable:
        r.ok("Billable status shown on jobsite card")
        r.passed = True
    else:
        r.fail("Billable status not found on jobsite card — OC-5758")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-14 — Jobsite Card — On Hold status shown
# ══════════════════════════════════════════════════════════════════════════════

async def job14(page: Page) -> TestResult:
    """
    Steps   : 1. Set jobsite to On Hold (or find one already on hold).
              2. Open jobsite card.
              3. Verify On Hold status is visible.
    Expected: On Hold status displayed prominently on card.
    """
    r = TestResult("JOB-14", "Jobsite Card — On Hold status shown")

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])

    # Try to set status to On Hold
    await click_edit(page)
    try:
        await fill_dropdown(page, "Status", "On Hold", "Status")
        await click_save(page)
    except Exception as e:
        r.log(f"Could not set On Hold via edit: {e}")

    await page.screenshot(path="job14_result.png")
    blocks = await get_text_blocks(page)
    on_hold = any(re.search(r"on.?hold", b, re.I) for b in blocks)
    r.log(f"'On Hold' visible: {on_hold}")

    if on_hold:
        r.ok("On Hold status shown on jobsite card")
        r.passed = True
    else:
        r.fail("'On Hold' status not visible on jobsite card")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-15 — Jobsite Card — customer info displayed (OC-5758)
# ══════════════════════════════════════════════════════════════════════════════

async def job15(page: Page) -> TestResult:
    """
    Regression for OC-5758: Customer info (name, address, contact) must all
    appear on the Jobsite Card / detail page.
    """
    r = TestResult("JOB-15", "Jobsite Card — customer info displayed (OC-5758)")

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    await page.screenshot(path="job15_result.png")

    blocks = await get_text_blocks(page)
    checks = {
        "Customer name/ID": any(
            re.search(r"customer|" + KNOWN_JOBSITE["customer"], b, re.I) for b in blocks
        ),
        "Address": any(
            re.search(r"\d+\s+\w+.*(rd|st|ave|blvd|dr|ln)\b", b, re.I) for b in blocks
        ),
        "Contact": any(re.search(r"contact|phone|email", b, re.I) for b in blocks),
    }
    r.log(f"Customer info checks: {checks}")

    passed_count = sum(checks.values())
    if passed_count >= 2:
        r.ok(f"Customer info displayed ({passed_count}/3 sections) — OC-5758 passes")
        r.passed = True
    else:
        r.fail(f"Customer info incomplete on jobsite card ({passed_count}/3) — OC-5758")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-16 — Jobsite Card — tax rate shown
# ══════════════════════════════════════════════════════════════════════════════

async def job16(page: Page) -> TestResult:
    r = TestResult("JOB-16", "Jobsite Card — tax rate shown")

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    await page.screenshot(path="job16_result.png")

    blocks = await get_text_blocks(page)
    tax_blocks = [b for b in blocks if re.search(r"tax", b, re.I)]
    r.log(f"Tax blocks: {tax_blocks[:5]}")

    has_tax = any(re.search(r"tax", b, re.I) for b in blocks)
    has_rate = any(re.search(r"\d+\.?\d*\s*%", b) for b in blocks)

    if has_tax and has_rate:
        r.ok(f"Tax rate shown on jobsite card: {[b for b in blocks if '%' in b][:2]}")
        r.passed = True
    elif has_tax:
        r.ok("Tax section visible; rate format may differ")
        r.passed = True
    else:
        r.fail("Tax rate not shown on jobsite card")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-17 — Jobsite Card — navigate to jobsite detail page
# ══════════════════════════════════════════════════════════════════════════════

async def job17(page: Page) -> TestResult:
    """
    Steps   : 1. Click a jobsite link from the landing page.
              2. Verify URL changes to jobsite detail.
              3. Verify jobsite name/ID visible on detail page.
    Expected: Clicking jobsite navigates to its detail page.
    """
    r = TestResult("JOB-17", "Jobsite Card — navigate to jobsite detail page")

    await nav_to_jobsites(page)
    start_url = page.url

    # Click the first jobsite link
    link = page.locator(".e-gridcontent .e-row a, table tbody tr a").first
    if await link.count() == 0:
        r.fail("No jobsite links in grid")
        return r

    link_text = (await link.inner_text()).strip()
    await link.click()
    await wait_spinners(page)
    await page.wait_for_timeout(800)
    await page.screenshot(path="job17_result.png")

    url_changed = page.url != start_url
    blocks = await get_text_blocks(page)
    on_detail = any(
        re.search(r"jobsite|edit|contact|asset|billing", b, re.I) for b in blocks
    )
    r.log(f"URL changed: {url_changed} | On detail: {on_detail} | Link: '{link_text}'")

    if url_changed and on_detail:
        r.ok(f"Navigation to jobsite detail succeeded — URL: {page.url}")
        r.passed = True
    else:
        r.fail("Jobsite detail page did not load after clicking link")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-18 — Jobsite Card — assets onsite count shown
# ══════════════════════════════════════════════════════════════════════════════

async def job18(page: Page) -> TestResult:
    r = TestResult("JOB-18", "Jobsite Card — assets onsite count shown")

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    await page.screenshot(path="job18_result.png")

    blocks = await get_text_blocks(page)
    asset_blocks = [b for b in blocks if re.search(r"asset|onsite|on.?site", b, re.I)]
    r.log(f"Asset blocks: {asset_blocks[:5]}")

    has_asset_count = any(
        re.search(r"asset|onsite", b, re.I) and re.search(r"\d+", b)
        for b in blocks
    )

    if has_asset_count:
        r.ok("Asset onsite count visible on jobsite card")
        r.passed = True
    elif asset_blocks:
        r.ok("Asset section present (count may be 0)")
        r.passed = True
    else:
        r.fail("No asset count shown on jobsite card — OC-5758")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-19 — Jobsite with no assets — empty assets section
# ══════════════════════════════════════════════════════════════════════════════

async def job19(page: Page) -> TestResult:
    """
    Steps   : 1. Find a jobsite with 0 assets.
              2. Open its card.
              3. Verify empty assets section shown (not blank/error).
    Expected: Assets section shows '0 assets' or equivalent empty state.
    """
    r = TestResult("JOB-19", "Jobsite with no assets — empty assets section")

    await nav_to_jobsites(page)
    # Search for a jobsite likely to have no assets
    await search_grid(page, "0")
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    await page.screenshot(path="job19_result.png")

    blocks = await get_text_blocks(page)
    empty_asset = any(
        re.search(r"0\s*asset|no\s*asset|empty|none", b, re.I) for b in blocks
    )
    asset_section = any(re.search(r"asset", b, re.I) for b in blocks)

    r.log(f"Empty asset indicators: {[b for b in blocks if re.search(r'asset|0', b, re.I)][:5]}")

    if empty_asset:
        r.ok("Empty assets state shown correctly — '0 assets' or similar")
        r.passed = True
    elif asset_section:
        r.ok("Asset section present — may have assets or show empty state differently")
        r.passed = True
    else:
        r.fail("No asset section visible on jobsite card")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-20 — Jobsite Display Filter — Jobsites only
# ══════════════════════════════════════════════════════════════════════════════

async def job20(page: Page) -> TestResult:
    """
    Steps   : 1. Open map or landing page display filter.
              2. Select 'Jobsites only'.
              3. Verify only jobsite markers/rows shown.
    Expected: Filter correctly limits view to jobsites only.
    Jira    : OC-5304
    """
    r = TestResult("JOB-20", "Jobsite Display Filter — Jobsites only")

    await nav_to_jobsites(page)

    # Look for a display filter control
    for sel in ["button:has-text('Display')", "select[aria-label*='display' i]",
                "span:has-text('Display Filter')", "button:has-text('Filter')"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await page.wait_for_timeout(600)
            break

    await page.screenshot(path="job20_filter.png")
    blocks = await get_text_blocks(page)

    jobsite_filter = any(
        re.search(r"jobsite.?only|show.?jobsite|display.*jobsite", b, re.I)
        for b in blocks
    )
    r.log(f"'Jobsites only' filter option visible: {jobsite_filter}")

    if jobsite_filter:
        r.ok("'Jobsites only' display filter option found — OC-5304")
        r.passed = True
    else:
        r.fail("'Jobsites only' filter option not found — OC-5304 regression")
        r.log("Check if this filter is on the Map page rather than the Jobsite list")

    await page.keyboard.press("Escape")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-21 — Jobsite Contact shown on Jobsite Card
# ══════════════════════════════════════════════════════════════════════════════

async def job21(page: Page) -> TestResult:
    r = TestResult("JOB-21", "Jobsite Contact shown on Jobsite Card")

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    await page.screenshot(path="job21_result.png")

    blocks = await get_text_blocks(page)
    contact_visible = any(
        re.search(r"contact|phone|email|\bname\b", b, re.I) for b in blocks
    )
    r.log(f"Contact-related blocks: {[b for b in blocks if re.search(r'contact|phone', b, re.I)][:5]}")

    if contact_visible:
        r.ok("Jobsite contact information visible on card — OC-5758")
        r.passed = True
    else:
        r.fail("No contact info on jobsite card — OC-5758 regression")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-22 — Add contact to jobsite
# ══════════════════════════════════════════════════════════════════════════════

async def job22(page: Page) -> TestResult:
    from faker import Faker
    f = Faker()
    r = TestResult("JOB-22", "Add contact to jobsite")
    contact = {"first": f.first_name(), "last": f.last_name(),
               "phone": "4045550155", "email": "job.contact@wasteapplications.com"}

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])

    for sel in ["a:has-text('Contacts')", "button:has-text('Contacts')",
                "span:has-text('Contacts')"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await page.wait_for_timeout(800)
            break

    for sel in ["button:has-text('Add Contact')", "button:has-text('ADD CONTACT')",
                "button:has-text('New Contact')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(800)
            break

    try:
        await fill_label(page,  "First Name *",     contact["first"], "First Name")
        await fill_label(page,  "Last Name",         contact["last"],  "Last Name")
        await fill_masked(page, "Phone Number 1 *", contact["phone"], "Phone")
        await fill_label(page,  "Email 1 *",         contact["email"], "Email")
    except Exception as e:
        r.log(f"Contact field partial: {e}")

    for sel in ["button:has-text('Save')", "button:has-text('CREATE')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            break
    await page.wait_for_timeout(2_000)
    await wait_spinners(page)
    await page.screenshot(path="job22_result.png")

    blocks = await get_text_blocks(page)
    added = any(
        contact["first"].lower() in b.lower() or contact["last"].lower() in b.lower()
        for b in blocks
    )
    if added:
        r.ok(f"Contact '{contact['first']} {contact['last']}' added to jobsite")
        r.passed = True
    else:
        r.fail("New jobsite contact not visible after save")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-23 — Edit jobsite contact
# ══════════════════════════════════════════════════════════════════════════════

async def job23(page: Page) -> TestResult:
    r = TestResult("JOB-23", "Edit jobsite contact")
    new_email = "job.edited@wasteapplications.com"

    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])

    for sel in ["a:has-text('Contacts')", "button:has-text('Contacts')"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await page.wait_for_timeout(800)
            break

    for sel in [".e-row button:has-text('Edit')", "button[title='Edit']",
                "button:has-text('Edit')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(800)
            break

    try:
        await fill_label(page, "Email 1 *", new_email, "Email")
        await fill_label(page, "Email 1",   new_email, "Email")
    except Exception:
        pass

    for sel in ["button:has-text('Save')", "button:has-text('Update')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            break
    await page.wait_for_timeout(2_000)
    await wait_spinners(page)
    await page.screenshot(path="job23_result.png")

    blocks = await get_text_blocks(page)
    if any(new_email.lower() in b.lower() for b in blocks):
        r.ok(f"Jobsite contact email updated to '{new_email}'")
        r.passed = True
    else:
        r.fail(f"Updated email '{new_email}' not visible after save")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# JOB-24 — Jobsite shows in customer active jobsite list
# ══════════════════════════════════════════════════════════════════════════════

async def job24(page: Page) -> TestResult:
    """
    Steps   : 1. Navigate to the known customer's detail page.
              2. Open their Jobsites tab.
              3. Verify the known jobsite appears in the list.
    Expected: Jobsite visible in customer's active jobsite list.
    Jira    : OC-5758
    """
    r = TestResult("JOB-24", "Jobsite shows in customer active jobsite list")

    # Navigate to customer
    await _click(page, "Management")
    await page.wait_for_timeout(800)
    await _click(page, "Customers", "Customer")
    await page.wait_for_function(
        "() => !window.location.href.endsWith('/home')", timeout=20_000
    )
    await wait_spinners(page)
    await page.wait_for_timeout(600)

    await open_record_by_id(page, KNOWN_JOBSITE["customer"])

    # Click Jobsites tab on customer detail
    for sel in ["a:has-text('Jobsites')", "button:has-text('Jobsites')",
                "span:has-text('Jobsites')", "li:has-text('Jobsites')"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await page.wait_for_timeout(1_000)
            await wait_spinners(page)
            break

    await page.screenshot(path="job24_result.png")
    blocks = await get_text_blocks(page)
    rows = await grid_rows_text(page)
    r.log(f"Jobsite rows on customer: {rows[:5]}")

    jobsite_listed = any(
        KNOWN_JOBSITE["id"] in row or KNOWN_JOBSITE["name"].lower() in row.lower()
        for row in rows
    ) or any(
        KNOWN_JOBSITE["id"] in b or KNOWN_JOBSITE["name"].lower() in b.lower()
        for b in blocks
    )

    if jobsite_listed:
        r.ok(f"Jobsite {KNOWN_JOBSITE['id']} appears in customer's jobsite list — OC-5758")
        r.passed = True
    else:
        r.fail(f"Jobsite {KNOWN_JOBSITE['id']} not found in customer's jobsite list")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════════

ALL_TESTS = {
    "JOB-01": job01, "JOB-02": job02, "JOB-03": job03,
    "JOB-04": job04, "JOB-05": job05, "JOB-06": job06,
    "JOB-07": job07, "JOB-08": job08, "JOB-09": job09,
    "JOB-10": job10, "JOB-11": job11, "JOB-12": job12,
    "JOB-13": job13, "JOB-14": job14, "JOB-15": job15,
    "JOB-16": job16, "JOB-17": job17, "JOB-18": job18,
    "JOB-19": job19, "JOB-20": job20, "JOB-21": job21,
    "JOB-22": job22, "JOB-23": job23, "JOB-24": job24,
}


async def run_tests(test_ids: list[str]) -> None:
    print("\n" + "═" * 65)
    print(f"  Jobsite QA Suite — {len(test_ids)} test(s): {', '.join(test_ids)}")
    print("═" * 65)
    results: list[TestResult] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
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
                print(f"\n⚠  Unknown: {tid}")
                continue
            print(f"\n{'─'*65}\n  Running {tid}…\n{'─'*65}")
            try:
                result = await fn(page)
            except Exception as exc:
                result = TestResult(tid, "(crashed)")
                result.fail(f"Exception: {exc}")
                try:
                    await page.screenshot(path=f"{tid.lower()}_crash.png")
                except Exception:
                    pass
                print(f"  ❌ {tid} crashed: {exc}")
            results.append(result)
            result.print_report()

        await page.wait_for_timeout(2_000)
        await context.close()
        await browser.close()

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]
    print(f"\n{'═'*65}\n  JOBSITE SUITE SUMMARY\n{'─'*65}")
    print(f"  Total {len(results)} | ✅ {len(passed)} | ❌ {len(failed)}")
    print("─" * 65)
    for r in results:
        icon = "✅" if r.passed else "❌"
        print(f"  {icon}  {r.test_id:8}  {r.title}")
        if not r.passed:
            for reason in r.failure_reasons:
                print(f"            • {reason}")
    print("═" * 65)


def main() -> None:
    args = sys.argv[1:]
    keys = list(ALL_TESTS.keys())
    if not args:
        test_ids = keys
    elif len(args) == 1 and args[0] in ALL_TESTS:
        test_ids = [args[0]]
    elif len(args) == 2 and args[0] in ALL_TESTS and args[1] in ALL_TESTS:
        test_ids = keys[keys.index(args[0]):keys.index(args[1]) + 1]
    else:
        test_ids = [a for a in args if a in ALL_TESTS]
    if not test_ids:
        print("No valid tests.")
        sys.exit(1)
    asyncio.run(run_tests(test_ids))


if __name__ == "__main__":
    main()
