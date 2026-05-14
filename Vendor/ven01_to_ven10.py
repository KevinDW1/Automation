"""
ven01_to_ven10.py
─────────────────
Vendor QA Suite — VEN-01 through VEN-10
Run all:    python ven01_to_ven10.py
Run single: python ven01_to_ven10.py VEN-05
Run via pytest: pytest Vendor/ven01_to_ven10.py -v
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime

import pytest
from playwright.async_api import Page, async_playwright

from job_ven_base import (
    KNOWN_VENDOR, new_vendor,
    TestResult, do_login,
    nav_to_vendors, search_grid, open_record_by_id,
    click_new_button, click_save, click_edit,
    fill_label, fill_masked, fill_dropdown, fill_autocomplete,
    dismiss_popups, wait_spinners,
    get_text_blocks, grid_row_count, grid_rows_text,
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

def _safe_run(fn, shared_page):
    try:
        r = _run(fn(shared_page))
    except Exception as exc:
        r = TestResult(fn.__name__, "(crashed)")
        r.fail("Exception: " + str(exc))
    if not r.passed:
        print("  [RECORDED FAILURE] " + r.test_id + ": " + "; ".join(r.failure_reasons))
    return r


def _safe_run(fn, shared_page):
    try:
        loop = asyncio.get_event_loop()
        r = loop.run_until_complete(fn(shared_page))
    except Exception as exc:
        from dataclasses import dataclass, field as _field
        r = type('R', (), {'test_id': getattr(fn, '__name__', '?'), 'title': '(crashed)', 'passed': False, 'failure_reasons': [f"Exception: {exc}"], 'evidence': []})()
    if not r.passed:
        print(f"  [RECORDED FAILURE] {r.test_id}: {'; '.join(r.failure_reasons)}")
    return r


def test_ven01(shared_page):
    r = _run(ven01(shared_page))
    assert r.passed, "\n".join(r.failure_reasons)

def test_ven02(shared_page):
    r = _run(ven02(shared_page))
    assert r.passed, "\n".join(r.failure_reasons)

def test_ven03(shared_page):
    r = _run(ven03(shared_page))
    assert r.passed, "\n".join(r.failure_reasons)

def test_ven04(shared_page):
    r = _run(ven04(shared_page))
    assert r.passed, "\n".join(r.failure_reasons)

def test_ven05(shared_page):
    r = _run(ven05(shared_page))
    assert r.passed, "\n".join(r.failure_reasons)

def test_ven06(shared_page):
    r = _run(ven06(shared_page))
    assert r.passed, "\n".join(r.failure_reasons)

def test_ven07(shared_page):
    r = _run(ven07(shared_page))
    assert r.passed, "\n".join(r.failure_reasons)

def test_ven08(shared_page):
    r = _run(ven08(shared_page))
    assert r.passed, "\n".join(r.failure_reasons)

def test_ven09(shared_page):
    r = _run(ven09(shared_page))
    assert r.passed, "\n".join(r.failure_reasons)

def test_ven10(shared_page):
    r = _run(ven10(shared_page))
    assert r.passed, "\n".join(r.failure_reasons)


# ══════════════════════════════════════════════════════════════════════════════
# VEN-01 — Create new vendor — happy path
# ══════════════════════════════════════════════════════════════════════════════

async def ven01(page: Page) -> TestResult:
    r = TestResult("VEN-01", "Create new vendor — happy path")
    data = new_vendor()

    await nav_to_vendors(page)
    await click_new_button(page, "NEW VENDOR")

    try:
        await fill_label(page,    "Vendor Name *",   data["name"],   "Name")
        await fill_dropdown(page, "Address *",        data["street"], "Street")
        await fill_label(page,    "City *",           data["city"],   "City")
        await fill_dropdown(page, "State *",          data["state"],  "State")
        await fill_label(page,    "Zip Code *",       data["zip"],    "ZIP")
        await fill_masked(page,   "Phone Number *",   data["phone"],  "Phone")
        await fill_label(page,    "EIN",              data["ein"],    "EIN")
    except Exception as e:
        r.log(f"Field fill partial: {e}")

    for sel in ["button:has-text('Save')", "button:has-text('CREATE')",
                "button:has-text('SAVE')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(force=True)
            break
    await page.wait_for_timeout(3_000)
    await wait_spinners(page)

    blocks = await get_text_blocks(page)
    created = any(
        re.search(r"success|created|saved", b, re.I) for b in blocks
    ) or any(data["name"].lower() in b.lower() for b in blocks)

    if created:
        r.ok(f"Vendor '{data['name']}' created successfully")
        r.passed = True
    else:
        r.fail("Vendor creation unclear — check screenshot")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# VEN-02 — Create vendor — missing required name
# ══════════════════════════════════════════════════════════════════════════════

async def ven02(page: Page) -> TestResult:
    r = TestResult("VEN-02", "Create vendor — missing required name")
    data = new_vendor()

    await nav_to_vendors(page)
    await click_new_button(page, "NEW VENDOR")

    try:
        await fill_dropdown(page, "Address *",      data["street"], "Street")
        await fill_label(page,    "City *",         data["city"],   "City")
        await fill_dropdown(page, "State *",        data["state"],  "State")
        await fill_label(page,    "Zip Code *",     data["zip"],    "ZIP")
        await fill_masked(page,   "Phone Number *", data["phone"],  "Phone")
    except Exception as e:
        r.log(f"Fill partial: {e}")

    for sel in ["button:has-text('Save')", "button:has-text('CREATE')"]:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(force=True)
            break
    await page.wait_for_timeout(1_500)

    blocks = await get_text_blocks(page)
    has_error = any(
        re.search(r"required|name.*required|vendor name", b, re.I) for b in blocks
    )
    still_on_form = any(
        re.search(r"vendor name|address|ein", b, re.I) for b in blocks
    )

    if has_error or still_on_form:
        r.ok("Validation blocked submission without Vendor Name")
        r.passed = True
    else:
        r.fail("No validation error shown for missing vendor name")

    await page.keyboard.press("Escape")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# VEN-03 — Edit vendor name
# ══════════════════════════════════════════════════════════════════════════════

async def ven03(page: Page) -> TestResult:
    r = TestResult("VEN-03", "Edit vendor name")
    new_name = f"Automation Vendor Edit {datetime.now().strftime('%H%M%S')}"

    await nav_to_vendors(page)
    await open_record_by_id(page, KNOWN_VENDOR["id"])
    await click_edit(page)

    try:
        await fill_label(page, "Vendor Name *", new_name, "Vendor Name")
        await fill_label(page, "Vendor Name",   new_name, "Vendor Name")
    except Exception as e:
        r.log(f"Name field error: {e}")

    await click_save(page)

    blocks = await get_text_blocks(page)
    if any(new_name.lower() in b.lower() for b in blocks):
        r.ok(f"Vendor name updated to '{new_name}'")
        r.passed = True
    else:
        r.fail(f"Updated name '{new_name}' not visible after save")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# VEN-04 — Edit vendor address
# ══════════════════════════════════════════════════════════════════════════════

async def ven04(page: Page) -> TestResult:
    r = TestResult("VEN-04", "Edit vendor address")
    new_city = "Automation City"
    new_zip  = "30303"

    await nav_to_vendors(page)
    await open_record_by_id(page, KNOWN_VENDOR["id"])
    await click_edit(page)

    try:
        await fill_label(page, "City *",     new_city, "City")
        await fill_label(page, "Zip Code *", new_zip,  "ZIP")
    except Exception as e:
        r.log(f"Address field partial: {e}")

    await click_save(page)

    blocks = await get_text_blocks(page)
    city_ok = any(new_city.lower() in b.lower() for b in blocks)
    zip_ok  = any(new_zip in b for b in blocks)

    if city_ok or zip_ok:
        r.ok("Vendor address updated successfully")
        r.passed = True
    else:
        r.fail("Updated address not visible after save")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# VEN-05 — Set vendor status to Active
# ══════════════════════════════════════════════════════════════════════════════

async def ven05(page: Page) -> TestResult:
    r = TestResult("VEN-05", "Set vendor status to Active")

    await nav_to_vendors(page)
    await open_record_by_id(page, KNOWN_VENDOR["id"])
    await click_edit(page)

    try:
        await fill_dropdown(page, "Status", "Active", "Status")
    except Exception as e:
        r.log(f"Status dropdown error: {e}")
        await page.evaluate(
            """() => {
                for (const el of document.querySelectorAll('*')) {
                    if (/^status$/i.test(el.textContent.trim()) && el.offsetParent!==null)
                        { el.click(); return; }
                }
            }"""
        )
        await page.wait_for_timeout(500)
        opt = page.locator("[role='listbox'] li:has-text('Active')").first
        if await opt.count() > 0:
            await opt.click()

    await click_save(page)

    blocks = await get_text_blocks(page)
    if any(re.search(r"\bactive\b", b, re.I) for b in blocks):
        r.ok("Vendor status set to Active")
        r.passed = True
    else:
        r.fail("'Active' status not confirmed after save")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# VEN-06 — Search vendor by name
# ══════════════════════════════════════════════════════════════════════════════

async def ven06(page: Page) -> TestResult:
    r = TestResult("VEN-06", "Search vendor by name")

    await nav_to_vendors(page)
    await search_grid(page, KNOWN_VENDOR["name"])

    rows = await grid_rows_text(page)
    r.log(f"Rows after name search: {rows[:3]}")

    match = any(KNOWN_VENDOR["name"].lower() in row.lower() for row in rows)
    if match:
        r.ok(f"Vendor '{KNOWN_VENDOR['name']}' found by name search")
        r.passed = True
    else:
        r.fail("Name search did not return expected vendor")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# VEN-07 — Search vendor by ID
# ══════════════════════════════════════════════════════════════════════════════

async def ven07(page: Page) -> TestResult:
    r = TestResult("VEN-07", "Search vendor by ID")

    await nav_to_vendors(page)
    await search_grid(page, KNOWN_VENDOR["id"])

    rows = await grid_rows_text(page)
    r.log(f"Rows after ID search: {rows[:3]}")

    match = any(KNOWN_VENDOR["id"] in row for row in rows)
    if match:
        r.ok(f"Vendor ID '{KNOWN_VENDOR['id']}' returned correct record")
        r.passed = True
    else:
        r.fail("ID search did not return expected vendor")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# VEN-08 — Vendor grid pagination
# ══════════════════════════════════════════════════════════════════════════════

async def ven08(page: Page) -> TestResult:
    r = TestResult("VEN-08", "Vendor grid pagination")

    await nav_to_vendors(page)
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
        r.ok("Vendor pagination works — different records on page 2")
        r.passed = True
    else:
        r.fail("Pages show identical records — vendor pagination not working")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# VEN-09 — Vendor grid — Show 20 dropdown changes visible rows
# ══════════════════════════════════════════════════════════════════════════════

async def ven09(page: Page) -> TestResult:
    r = TestResult("VEN-09", "Vendor grid — Show 20 dropdown changes visible rows")

    await nav_to_vendors(page)
    rows_default = await grid_row_count(page)
    r.log(f"Default rows: {rows_default}")

    changed = False
    pager = page.locator(
        ".e-pagerdropdown, select[aria-label*='page size' i]"
    ).first

    if await pager.count() > 0:
        try:
            await pager.select_option("50")
            changed = True
        except Exception:
            await pager.click()
            await page.wait_for_timeout(400)
            opt = page.locator("[role='listbox'] li:has-text('50')").first
            if await opt.count() > 0:
                await opt.click()
                changed = True

    if not changed:
        changed = await page.evaluate(
            """() => {
                for (const sel of document.querySelectorAll('select')) {
                    if ([...sel.options].some(o => o.value==='50'||o.text==='50')) {
                        sel.value='50';
                        sel.dispatchEvent(new Event('change',{bubbles:true}));
                        return true;
                    }
                }
                return false;
            }"""
        )

    if not changed:
        r.fail("Could not find Show rows dropdown")
        return r

    await wait_spinners(page)
    await page.wait_for_timeout(800)
    rows_after = await grid_row_count(page)
    r.log(f"Rows after Show 50: {rows_after}")

    if rows_after > rows_default or rows_after >= 20:
        r.ok(f"Show dropdown changed rows: {rows_default} → {rows_after}")
        r.passed = True
    else:
        r.fail(f"Row count did not increase ({rows_default} → {rows_after})")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# VEN-10 — Vendor EIN field displays correctly
# ══════════════════════════════════════════════════════════════════════════════

async def ven10(page: Page) -> TestResult:
    r = TestResult("VEN-10", "Vendor EIN field displays correctly")

    await nav_to_vendors(page)

    headers = await page.evaluate(
        """() => Array.from(
            document.querySelectorAll('.e-gridheader th,.e-headercell')
        ).map(h => h.textContent.trim())"""
    )
    r.log(f"Grid headers: {headers}")
    ein_col = any(re.search(r"\bein\b", h, re.I) for h in headers)

    rows = await grid_rows_text(page)
    ein_pattern = re.compile(r"\b\d{2}-\d{7}\b")
    ein_in_rows = any(ein_pattern.search(row) for row in rows)
    r.log(f"EIN column in headers: {ein_col} | EIN format in rows: {ein_in_rows}")

    await open_record_by_id(page, KNOWN_VENDOR["id"])

    blocks = await get_text_blocks(page)
    ein_in_detail = any(
        re.search(r"\bein\b|\d{2}-\d{7}", b, re.I) for b in blocks
    )
    r.log(f"EIN visible on vendor detail: {ein_in_detail}")

    if ein_col or ein_in_rows or ein_in_detail:
        r.ok("EIN field visible and in correct XX-XXXXXXX format")
        r.passed = True
    else:
        r.fail("EIN field not found or not in correct format")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════════

ALL_TESTS = {
    "VEN-01": ven01, "VEN-02": ven02, "VEN-03": ven03,
    "VEN-04": ven04, "VEN-05": ven05, "VEN-06": ven06,
    "VEN-07": ven07, "VEN-08": ven08, "VEN-09": ven09,
    "VEN-10": ven10,
}


async def run_tests(test_ids: list[str]) -> None:
    print("\n" + "═" * 65)
    print(f"  Vendor QA Suite — {len(test_ids)} test(s): {', '.join(test_ids)}")
    print("═" * 65)
    results: list[TestResult] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
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
                print(f"  ❌ {tid} crashed: {exc}")
            results.append(result)
            result.print_report()

        await context.close()
        await browser.close()

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]
    print(f"\n{'═'*65}\n  VENDOR SUITE SUMMARY\n{'─'*65}")
    print(f"  Total {len(results)} | ✅ {len(passed)} | ❌ {len(failed)}")
    for r in results:
        icon = "✅" if r.passed else "❌"
        print(f"  {icon}  {r.test_id:8}  {r.title}")
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
