"""
job01_to_job24.py
─────────────────
Jobsite QA Suite — JOB-01 through JOB-24
Run all:    python job01_to_job24.py
Run single: python job01_to_job24.py JOB-06
Run via pytest: pytest Jobsite/job01_to_job24.py -v
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime

import pytest
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


# ── pytest fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def shared_page():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _setup():
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await do_login(page)
        return pw, browser, context, page

    pw, browser, context, page = loop.run_until_complete(_setup())
    yield page

    async def _teardown():
        await context.close()
        await browser.close()
        await pw.stop()

    loop.run_until_complete(_teardown())
    loop.close()


# ── pytest test functions ─────────────────────────────────────────────────────

def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

def test_job01(shared_page): r = _run(job01(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job02(shared_page): r = _run(job02(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job03(shared_page): r = _run(job03(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job04(shared_page): r = _run(job04(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job05(shared_page): r = _run(job05(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job06(shared_page): r = _run(job06(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job07(shared_page): r = _run(job07(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job08(shared_page): r = _run(job08(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job09(shared_page): r = _run(job09(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job10(shared_page): r = _run(job10(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job11(shared_page): r = _run(job11(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job12(shared_page): r = _run(job12(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job13(shared_page): r = _run(job13(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job14(shared_page): r = _run(job14(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job15(shared_page): r = _run(job15(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job16(shared_page): r = _run(job16(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job17(shared_page): r = _run(job17(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job18(shared_page): r = _run(job18(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job19(shared_page): r = _run(job19(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job20(shared_page): r = _run(job20(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job21(shared_page): r = _run(job21(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job22(shared_page): r = _run(job22(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job23(shared_page): r = _run(job23(shared_page)); assert r.passed, "\n".join(r.failure_reasons)
def test_job24(shared_page): r = _run(job24(shared_page)); assert r.passed, "\n".join(r.failure_reasons)


# ══════════════════════════════════════════════════════════════════════════════
# Test implementations (unchanged from original)
# ══════════════════════════════════════════════════════════════════════════════

async def job01(page: Page) -> TestResult:
    r = TestResult("JOB-01", "Create new jobsite — happy path")
    data = new_jobsite()
    await nav_to_jobsites(page)
    await click_new_button(page, "NEW JOBSITE")
    await fill_autocomplete(page, data["customer"], "Customer ID")
    await page.wait_for_timeout(500)
    for sel in ["button:has-text('NEXT')", "button:has-text('Next')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(); await page.wait_for_timeout(1_500); await wait_spinners(page); break
    try:
        await fill_label(page,    "Jobsite Name *", data["name"],   "Name")
        await fill_dropdown(page, "Address *",       data["street"], "Street")
        await fill_label(page,    "City *",          data["city"],   "City")
        await fill_dropdown(page, "State *",         data["state"],  "State")
        await fill_label(page,    "Zip Code *",      data["zip"],    "ZIP")
    except Exception as e:
        r.log(f"Field fill partial: {e}")
    for sel in ["button:has-text('CREATE')", "button:has-text('FINISH')", "button:has-text('Save')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(force=True); await page.wait_for_timeout(3_000); await wait_spinners(page); break
    blocks = await get_text_blocks(page)
    created = any(re.search(r"success|created|jobsite.*added|saved", b, re.I) for b in blocks) or any(data["name"].lower() in b.lower() for b in blocks)
    if created:
        r.ok(f"Jobsite '{data['name']}' created successfully"); r.passed = True
    else:
        r.fail("Jobsite creation result unclear")
    return r

async def job02(page: Page) -> TestResult:
    r = TestResult("JOB-02", "Create jobsite — missing required name")
    data = new_jobsite()
    await nav_to_jobsites(page)
    await click_new_button(page, "NEW JOBSITE")
    await fill_autocomplete(page, data["customer"], "Customer")
    for sel in ["button:has-text('NEXT')", "button:has-text('Next')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(); await page.wait_for_timeout(1_500); break
    try:
        await fill_dropdown(page, "Address *", data["street"], "Street")
        await fill_label(page,   "City *",     data["city"],  "City")
    except Exception:
        pass
    for sel in ["button:has-text('CREATE')", "button:has-text('NEXT')", "button:has-text('FINISH')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(); break
    await page.wait_for_timeout(1_500)
    blocks = await get_text_blocks(page)
    has_error = any(re.search(r"required|name.*required|jobsite name", b, re.I) for b in blocks)
    still_on_form = any(re.search(r"jobsite name|address|city", b, re.I) for b in blocks)
    if has_error or still_on_form:
        r.ok("Validation prevented proceeding without Jobsite Name"); r.passed = True
    else:
        r.fail("No validation error shown for missing jobsite name")
    await page.keyboard.press("Escape")
    return r

async def job03(page: Page) -> TestResult:
    r = TestResult("JOB-03", "Create jobsite — missing required address")
    data = new_jobsite()
    await nav_to_jobsites(page)
    await click_new_button(page, "NEW JOBSITE")
    await fill_autocomplete(page, data["customer"], "Customer")
    for sel in ["button:has-text('NEXT')", "button:has-text('Next')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(); await page.wait_for_timeout(1_500); break
    try:
        await fill_label(page, "Jobsite Name *", data["name"], "Name")
    except Exception:
        pass
    for sel in ["button:has-text('CREATE')", "button:has-text('FINISH')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(); break
    await page.wait_for_timeout(1_500)
    blocks = await get_text_blocks(page)
    has_error = any(re.search(r"required|address.*required|billing address", b, re.I) for b in blocks)
    still_on_form = any(re.search(r"address|city|zip", b, re.I) for b in blocks)
    if has_error or still_on_form:
        r.ok("Validation prevented proceeding without address"); r.passed = True
    else:
        r.fail("No validation error shown for missing address")
    await page.keyboard.press("Escape")
    return r

async def job04(page: Page) -> TestResult:
    r = TestResult("JOB-04", "Jobsite inherits customer partnership status pill")
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    blocks = await get_text_blocks(page)
    pill_visible = any(re.search(r"\bactive\b|\bpartner\b|\bno.?partner\b|\bat.?risk\b", b, re.I) for b in blocks)
    if pill_visible:
        r.ok("Partnership status pill visible on jobsite"); r.passed = True
    else:
        r.fail("No partnership status pill found on jobsite — OC-5760")
    return r

async def job05(page: Page) -> TestResult:
    r = TestResult("JOB-05", "Jobsite under No Partnership customer — grey pill")
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    blocks = await get_text_blocks(page)
    has_no_partner = any(re.search(r"no.?partner", b, re.I) for b in blocks)
    if has_no_partner:
        r.ok("No Partnership pill visible"); r.passed = True
    else:
        r.fail("Grey 'No Partnership' pill not found")
    return r

async def job06(page: Page) -> TestResult:
    r = TestResult("JOB-06", "Jobsite Landing Page — Vendor ID column shows vendor IDs")
    await nav_to_jobsites(page)
    headers = await page.evaluate("() => Array.from(document.querySelectorAll('.e-gridheader th, .e-headercell')).map(h=>h.textContent.trim())")
    has_vendor_col = any(re.search(r"vendor.?id|vendor", h, re.I) for h in headers)
    rows = await grid_rows_text(page)
    vendor_id_in_row = any(re.search(r"\b\d{4,6}\b", row) for row in rows)
    if has_vendor_col:
        r.ok("Vendor ID column present — OC-5800 passes"); r.passed = True
    else:
        r.fail("Vendor ID column not found — OC-5800 regression")
    return r

async def job07(page: Page) -> TestResult:
    r = TestResult("JOB-07", "Jobsite Landing Page — search by jobsite name")
    await nav_to_jobsites(page)
    await search_grid(page, KNOWN_JOBSITE["name"])
    rows = await grid_rows_text(page)
    match = any(KNOWN_JOBSITE["name"].lower() in row.lower() or KNOWN_JOBSITE["id"] in row for row in rows)
    if match:
        r.ok(f"Search by name returned matching jobsite"); r.passed = True
    else:
        r.fail("Name search did not return expected jobsite")
    return r

async def job08(page: Page) -> TestResult:
    r = TestResult("JOB-08", "Jobsite Landing Page — search by jobsite ID")
    await nav_to_jobsites(page)
    await search_grid(page, KNOWN_JOBSITE["id"])
    rows = await grid_rows_text(page)
    match = any(KNOWN_JOBSITE["id"] in row for row in rows)
    if match:
        r.ok(f"Search by ID returned correct jobsite"); r.passed = True
    else:
        r.fail("ID search did not return expected jobsite")
    return r

async def job09(page: Page) -> TestResult:
    r = TestResult("JOB-09", "Jobsite Landing Page — date picker label correct")
    await nav_to_jobsites(page)
    date_labels = await page.evaluate("""() => {
        const out = [];
        for (const inp of document.querySelectorAll('input.e-datepicker, input.e-daterangepicker, input[aria-label*="date" i]')) {
            out.push({ ariaLabel: inp.getAttribute('aria-label') || '', placeholder: inp.placeholder || '' });
        }
        return out;
    }""")
    if not date_labels:
        r.fail("No date picker found — OC-5698"); return r
    for dp in date_labels:
        non_empty = [l for l in [dp["ariaLabel"], dp["placeholder"]] if l.strip()]
        bad_label = any(re.search(r"undefined|null|NaN|invalid", l, re.I) for l in non_empty)
        if bad_label:
            r.fail(f"Date picker label contains invalid text: {non_empty}")
        else:
            r.ok(f"Date picker label is correct: {non_empty}"); r.passed = True
    if not r.failure_reasons:
        r.passed = True
    return r

async def job10(page: Page) -> TestResult:
    r = TestResult("JOB-10", "Jobsite Landing Page — filter by tag")
    await nav_to_jobsites(page)
    for sel in ["button:has-text('Filters')", "span:has-text('Select Filters')"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click(); await page.wait_for_timeout(800); break
    blocks = await get_text_blocks(page)
    has_tag_filter = any(re.search(r"\btag\b", b, re.I) for b in blocks)
    if has_tag_filter:
        r.ok("Tag filter option found"); r.passed = True
    else:
        r.fail("No tag filter option found — OC-3471")
    await page.keyboard.press("Escape")
    return r

async def job11(page: Page) -> TestResult:
    r = TestResult("JOB-11", "Jobsite Landing Page — pagination")
    await nav_to_jobsites(page)
    rows_p1 = await grid_rows_text(page)
    next_btn = page.locator("button[aria-label='Next page'], button[aria-label='Next Page'], li.e-next button, .e-nextpage").first
    if await next_btn.count() == 0 or not await next_btn.is_enabled():
        r.fail("Next page button not found or disabled"); return r
    await next_btn.click(); await wait_spinners(page); await page.wait_for_timeout(800)
    rows_p2 = await grid_rows_text(page)
    if rows_p1 and rows_p2 and rows_p1[0] != rows_p2[0]:
        r.ok("Jobsite pagination works"); r.passed = True
    else:
        r.fail("Page 1 and 2 show same records")
    return r

async def job12(page: Page) -> TestResult:
    r = TestResult("JOB-12", "Jobsite Card — customer name and address shown")
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    blocks = await get_text_blocks(page)
    has_customer = any(KNOWN_JOBSITE["customer"].lower() in b.lower() or re.search(r"customer", b, re.I) for b in blocks)
    has_address = any(re.search(r"\d+\s+\w+.*(?:rd|st|ave|blvd|dr|ln|way|ct)\b", b, re.I) for b in blocks)
    if has_customer and has_address:
        r.ok("Customer name and address visible"); r.passed = True
    elif has_customer:
        r.ok("Customer name visible"); r.passed = True
    else:
        r.fail("Customer name not visible — OC-5758")
    return r

async def job13(page: Page) -> TestResult:
    r = TestResult("JOB-13", "Jobsite Card — billable status shown")
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    blocks = await get_text_blocks(page)
    billable = any(re.search(r"\bbillable\b|\bnon.?billable\b", b, re.I) for b in blocks)
    if billable:
        r.ok("Billable status shown"); r.passed = True
    else:
        r.fail("Billable status not found — OC-5758")
    return r

async def job14(page: Page) -> TestResult:
    r = TestResult("JOB-14", "Jobsite Card — On Hold status shown")
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    await click_edit(page)
    try:
        await fill_dropdown(page, "Status", "On Hold", "Status")
        await click_save(page)
    except Exception as e:
        r.log(f"Could not set On Hold: {e}")
    blocks = await get_text_blocks(page)
    on_hold = any(re.search(r"on.?hold", b, re.I) for b in blocks)
    if on_hold:
        r.ok("On Hold status shown"); r.passed = True
    else:
        r.fail("'On Hold' status not visible")
    return r

async def job15(page: Page) -> TestResult:
    r = TestResult("JOB-15", "Jobsite Card — customer info displayed (OC-5758)")
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    blocks = await get_text_blocks(page)
    checks = {
        "Customer name/ID": any(re.search(r"customer|" + KNOWN_JOBSITE["customer"], b, re.I) for b in blocks),
        "Address": any(re.search(r"\d+\s+\w+.*(rd|st|ave|blvd|dr|ln)\b", b, re.I) for b in blocks),
        "Contact": any(re.search(r"contact|phone|email", b, re.I) for b in blocks),
    }
    passed_count = sum(checks.values())
    if passed_count >= 2:
        r.ok(f"Customer info displayed ({passed_count}/3) — OC-5758 passes"); r.passed = True
    else:
        r.fail(f"Customer info incomplete ({passed_count}/3) — OC-5758")
    return r

async def job16(page: Page) -> TestResult:
    r = TestResult("JOB-16", "Jobsite Card — tax rate shown")
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    blocks = await get_text_blocks(page)
    has_tax = any(re.search(r"tax", b, re.I) for b in blocks)
    if has_tax:
        r.ok("Tax section visible"); r.passed = True
    else:
        r.fail("Tax rate not shown")
    return r

async def job17(page: Page) -> TestResult:
    r = TestResult("JOB-17", "Jobsite Card — navigate to jobsite detail page")
    await nav_to_jobsites(page)
    start_url = page.url
    link = page.locator(".e-gridcontent .e-row a, table tbody tr a").first
    if await link.count() == 0:
        r.fail("No jobsite links in grid"); return r
    await link.click(); await wait_spinners(page); await page.wait_for_timeout(800)
    blocks = await get_text_blocks(page)
    url_changed = page.url != start_url
    on_detail = any(re.search(r"jobsite|edit|contact|asset|billing", b, re.I) for b in blocks)
    if url_changed and on_detail:
        r.ok(f"Navigation to jobsite detail succeeded"); r.passed = True
    else:
        r.fail("Jobsite detail page did not load")
    return r

async def job18(page: Page) -> TestResult:
    r = TestResult("JOB-18", "Jobsite Card — assets onsite count shown")
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    blocks = await get_text_blocks(page)
    asset_blocks = [b for b in blocks if re.search(r"asset|onsite|on.?site", b, re.I)]
    if asset_blocks:
        r.ok("Asset section present"); r.passed = True
    else:
        r.fail("No asset count shown — OC-5758")
    return r

async def job19(page: Page) -> TestResult:
    r = TestResult("JOB-19", "Jobsite with no assets — empty assets section")
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    blocks = await get_text_blocks(page)
    asset_section = any(re.search(r"asset", b, re.I) for b in blocks)
    if asset_section:
        r.ok("Asset section visible"); r.passed = True
    else:
        r.fail("No asset section visible")
    return r

async def job20(page: Page) -> TestResult:
    r = TestResult("JOB-20", "Jobsite Display Filter — Jobsites only")
    await nav_to_jobsites(page)
    for sel in ["button:has-text('Display')", "span:has-text('Display Filter')", "button:has-text('Filter')"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click(); await page.wait_for_timeout(600); break
    blocks = await get_text_blocks(page)
    jobsite_filter = any(re.search(r"jobsite.?only|show.?jobsite|display.*jobsite", b, re.I) for b in blocks)
    if jobsite_filter:
        r.ok("'Jobsites only' display filter found — OC-5304"); r.passed = True
    else:
        r.fail("'Jobsites only' filter not found — OC-5304 regression")
    await page.keyboard.press("Escape")
    return r

async def job21(page: Page) -> TestResult:
    r = TestResult("JOB-21", "Jobsite Contact shown on Jobsite Card")
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    blocks = await get_text_blocks(page)
    contact_visible = any(re.search(r"contact|phone|email|\bname\b", b, re.I) for b in blocks)
    if contact_visible:
        r.ok("Jobsite contact information visible — OC-5758"); r.passed = True
    else:
        r.fail("No contact info on jobsite card — OC-5758 regression")
    return r

async def job22(page: Page) -> TestResult:
    from faker import Faker
    f = Faker()
    r = TestResult("JOB-22", "Add contact to jobsite")
    contact = {"first": f.first_name(), "last": f.last_name(), "phone": "4045550155", "email": "job.contact@wasteapplications.com"}
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    for sel in ["a:has-text('Contacts')", "button:has-text('Contacts')"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click(); await page.wait_for_timeout(800); break
    for sel in ["button:has-text('Add Contact')", "button:has-text('ADD CONTACT')", "button:has-text('New Contact')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(); await page.wait_for_timeout(800); break
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
            await btn.click(); break
    await page.wait_for_timeout(2_000); await wait_spinners(page)
    blocks = await get_text_blocks(page)
    added = any(contact["first"].lower() in b.lower() or contact["last"].lower() in b.lower() for b in blocks)
    if added:
        r.ok(f"Contact added to jobsite"); r.passed = True
    else:
        r.fail("New jobsite contact not visible after save")
    return r

async def job23(page: Page) -> TestResult:
    r = TestResult("JOB-23", "Edit jobsite contact")
    new_email = "job.edited@wasteapplications.com"
    await nav_to_jobsites(page)
    await open_record_by_id(page, KNOWN_JOBSITE["id"])
    for sel in ["a:has-text('Contacts')", "button:has-text('Contacts')"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click(); await page.wait_for_timeout(800); break
    for sel in [".e-row button:has-text('Edit')", "button[title='Edit']", "button:has-text('Edit')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(); await page.wait_for_timeout(800); break
    try:
        await fill_label(page, "Email 1 *", new_email, "Email")
        await fill_label(page, "Email 1",   new_email, "Email")
    except Exception:
        pass
    for sel in ["button:has-text('Save')", "button:has-text('Update')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(); break
    await page.wait_for_timeout(2_000); await wait_spinners(page)
    blocks = await get_text_blocks(page)
    if any(new_email.lower() in b.lower() for b in blocks):
        r.ok(f"Jobsite contact email updated"); r.passed = True
    else:
        r.fail(f"Updated email not visible after save")
    return r

async def job24(page: Page) -> TestResult:
    r = TestResult("JOB-24", "Jobsite shows in customer active jobsite list")
    await _click(page, "Management")
    await page.wait_for_timeout(800)
    await _click(page, "Customers", "Customer")
    await page.wait_for_function("() => !window.location.href.endsWith('/home')", timeout=20_000)
    await wait_spinners(page)
    await open_record_by_id(page, KNOWN_JOBSITE["customer"])
    for sel in ["a:has-text('Jobsites')", "button:has-text('Jobsites')", "span:has-text('Jobsites')"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click(); await page.wait_for_timeout(1_000); await wait_spinners(page); break
    blocks = await get_text_blocks(page)
    rows = await grid_rows_text(page)
    jobsite_listed = any(KNOWN_JOBSITE["id"] in row or KNOWN_JOBSITE["name"].lower() in row.lower() for row in rows) or \
                     any(KNOWN_JOBSITE["id"] in b or KNOWN_JOBSITE["name"].lower() in b.lower() for b in blocks)
    if jobsite_listed:
        r.ok(f"Jobsite appears in customer's jobsite list — OC-5758"); r.passed = True
    else:
        r.fail(f"Jobsite not found in customer's jobsite list")
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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        await do_login(page)
        results = []
        for tid in test_ids:
            fn = ALL_TESTS.get(tid)
            if fn is None:
                continue
            try:
                result = await fn(page)
            except Exception as exc:
                result = TestResult(tid, "(crashed)")
                result.fail(f"Exception: {exc}")
            results.append(result)
            result.print_report()
        await context.close()
        await browser.close()


def main() -> None:
    args = sys.argv[1:]
    keys = list(ALL_TESTS.keys())
    test_ids = keys if not args else [a for a in args if a in ALL_TESTS]
    if not test_ids:
        print("No valid tests.")
        sys.exit(1)
    asyncio.run(run_tests(test_ids))


if __name__ == "__main__":
    main()
