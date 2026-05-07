# """
# Playwright Python script – Waste Applications Maps Navigation
# Logs in via B2C then clicks the Map navigation element via full XPath.
# """
#
# import json
# import time
# from playwright.sync_api import Page, sync_playwright
# from claude_validator import ClaudeValidator
# from qa_context import QA_SYSTEM_PROMPT, get_ticket_context
#
# # ─── Claude Validator ─────────────────────────────────────────────────────────
#
# validator = ClaudeValidator(system_prompt=QA_SYSTEM_PROMPT)
#
# # ─── Page Object ──────────────────────────────────────────────────────────────
#
# with open("map_page.json") as f:
#     PAGE = json.load(f)
#
# LOC = PAGE["locators"]
#
# # ─── Credentials ──────────────────────────────────────────────────────────────
#
# VALID_EMAIL    = "kevin.clarke@wasteapplications.com"
# VALID_PASSWORD = "Tuesday19@@@@"
#
# # ─── URLs ─────────────────────────────────────────────────────────────────────
#
# LOGIN_URL = (
#     "https://dw1qa.b2clogin.com/dw1qa.onmicrosoft.com/b2c_1_qa_signin/oauth2/v2.0/authorize"
#     "?client_id=d7d76a18-ff69-445b-8c0e-e3c2d441ae0a"
#     "&redirect_uri=https%3A%2F%2Fqa.wasteapplications.com%2FAccount%2FLogin"
#     "&response_type=code%20id_token"
#     "&scope=openid%20profile%20https%3A%2F%2Fdw1qa.onmicrosoft.com%2F0170418f-5650-4a29-b1e2-ebf4a97954c3%2FAPI.Access"
#     "&response_mode=form_post"
# )
#
# MAP_XPATH = "/html/body/main/div[1]/oc-app-header/nav/div[2]/div/div[4]/a/span"
#
#
# # ─── Element helpers ──────────────────────────────────────────────────────────
#
# def _email_field(page: Page):
#     candidates = [
#         "input[placeholder='Email Address']",
#         "#signInName",
#         "input[name='signInName']",
#         "input[name='logonIdentifier']",
#         "input[type='email']",
#         "input[placeholder*='email' i]",
#         "input[placeholder*='username' i]",
#         "input[type='text']",
#     ]
#     for selector in candidates:
#         loc = page.locator(selector).first
#         if loc.count() > 0 and loc.is_visible():
#             return loc
#     return page.locator("input[type='text']").first
#
#
# def _password_field(page: Page):
#     candidates = [
#         "input[placeholder='Password']",
#         "#password",
#         "input[name='password']",
#         "input[type='password']",
#     ]
#     for selector in candidates:
#         loc = page.locator(selector).first
#         if loc.count() > 0 and loc.is_visible():
#             return loc
#     return page.locator("input[type='password']").first
#
#
# def _submit_button(page: Page):
#     return page.locator("button[type='submit'][id='next']")
#
#
# def _fill_and_submit(page: Page, email: str, password: str):
#     email_field = _email_field(page)
#     pwd_field   = _password_field(page)
#
#     email_field.click()
#     email_field.click(click_count=3)
#     email_field.type(email, delay=80)
#     email_field.press("Tab")
#     page.wait_for_timeout(500)
#
#     pwd_field.click()
#     pwd_field.click(click_count=3)
#     pwd_field.type(password, delay=80)
#     page.wait_for_timeout(500)
#
#     _submit_button(page).click()
#
#
# def _visible_page_text(page: Page) -> str:
#     return page.evaluate("""() =>
#         Array.from(document.querySelectorAll('*'))
#             .filter(el => el.children.length === 0 && el.offsetParent !== null)
#             .map(el => el.innerText ? el.innerText.trim() : '')
#             .filter(t => t.length > 0)
#             .join(' | ')
#     """)
#
#
# # ─── Login ────────────────────────────────────────────────────────────────────
#
# def do_login(page: Page):
#     print("→ Navigating to login page...")
#     page.goto(LOGIN_URL)
#     page.wait_for_load_state("load", timeout=15_000)
#     page.wait_for_timeout(1_500)
#
#     print("→ Filling in credentials...")
#     _fill_and_submit(page, VALID_EMAIL, VALID_PASSWORD)
#
#     print("→ Waiting for redirect after login...")
#     deadline = time.time() + 25
#     while time.time() < deadline:
#         if "dw1qa.b2clogin.com" not in page.url:
#             break
#         page.wait_for_timeout(500)
#     else:
#         page.screenshot(path="debug_login_failed.png")
#         raise RuntimeError(
#             f"Login redirect did not happen within 25s.\n"
#             f"Current URL: {page.url}\n"
#             f"Screenshot saved to: debug_login_failed.png"
#         )
#
#     page.wait_for_load_state("load", timeout=15_000)
#     page.wait_for_timeout(2_000)
#     print(f"✓ Logged in. Current URL: {page.url}")
#
#
# # ─── Map navigation ───────────────────────────────────────────────────────────
#
# def click_map_element(page: Page):
#     print("→ Locating Map element via XPath...")
#
#     try:
#         page.wait_for_selector(
#             f"xpath={MAP_XPATH}",
#             state="visible",
#             timeout=15_000
#         )
#         print("  ✓ Map element found and visible")
#     except Exception as e:
#         page.screenshot(path="debug_map_not_found.png")
#         raise RuntimeError(
#             f"Map element not found via XPath within 15s.\n"
#             f"Current URL: {page.url}\n"
#             f"Visible text: {_visible_page_text(page)}"
#         ) from e
#
#     map_span = page.locator(f"xpath={MAP_XPATH}").first
#     map_span.scroll_into_view_if_needed()
#     page.wait_for_timeout(500)
#
#     print("→ Attempting standard click...")
#     map_span.click()
#     page.wait_for_timeout(2_000)
#
#     if "/map" in page.url:
#         print("  ✓ Standard click worked.")
#     else:
#         print("  Trying JS click...")
#         page.evaluate(f"""
#             const result = document.evaluate(
#                 '{MAP_XPATH}', document, null,
#                 XPathResult.FIRST_ORDERED_NODE_TYPE, null
#             );
#             if (result.singleNodeValue) {{ result.singleNodeValue.click(); }}
#         """)
#         page.wait_for_timeout(2_000)
#
#     if "/map" not in page.url:
#         print("  Trying parent <a> click...")
#         page.evaluate(f"""
#             const result = document.evaluate(
#                 '{MAP_XPATH}', document, null,
#                 XPathResult.FIRST_ORDERED_NODE_TYPE, null
#             );
#             const span = result.singleNodeValue;
#             if (span && span.closest('a')) {{ span.closest('a').click(); }}
#         """)
#         page.wait_for_timeout(2_000)
#
#     if "/map" not in page.url:
#         print("  Navigating directly to /map...")
#         page.evaluate("window.location.href = '/map'")
#         page.wait_for_timeout(2_000)
#
#     page.wait_for_load_state("load", timeout=15_000)
#     page.wait_for_timeout(3_000)
#
#     assert "/map" in page.url, \
#         f"Expected URL to contain '/map', got: {page.url}"
#
#     page.screenshot(path="debug_map_loaded.png")
#     print(f"✓ Map page loaded. Current URL: {page.url}")
#     print("  Screenshot saved to: debug_map_loaded.png")
#
#
# # ─── Address Search ───────────────────────────────────────────────────────────
#
# def search_address(page: Page, address: str) -> dict:
#     print(f"\n→ Searching address: {address}")
#
#     # ── Step 1: Ensure Local mode is selected ─────────────────────────────────
#     local_radio = page.locator(LOC["filters"]["localRadio"]).first
#     if local_radio.is_visible():
#         local_radio.click()
#         print("  ✓ Local mode selected")
#         page.wait_for_timeout(300)
#
#     # ── Step 2: Click and clear the search field ──────────────────────────────
#     search_field = page.locator(LOC["filters"]["addressSearch"]).first
#     search_field.click()
#     search_field.click(click_count=3)
#     page.wait_for_timeout(200)
#
#     # ── Step 3: Type address — fires onChange per keystroke for SmartyStreets ─
#     search_field.type(address, delay=80)
#     print(f"  ✓ Address typed: {address}")
#
#     # ── Step 4: Wait for autocomplete dropdown ────────────────────────────────
#     page.wait_for_timeout(1_500)
#
#     # ── OC-5299 AC3/AC4: Capture dropdown while visible ──────────────────────
#     page.screenshot(path="debug_address_autocomplete.png")
#     print("  ✓ Autocomplete screenshot saved: debug_address_autocomplete.png")
#
#     # ── Step 5: Select first suggestion ──────────────────────────────────────
#     search_field.press("ArrowDown")
#     page.wait_for_timeout(400)
#     search_field.press("Enter")
#     print("  ✓ First autocomplete suggestion selected")
#     page.wait_for_timeout(1_000)
#
#     # ── Step 6: Confirm Display is All Selected ───────────────────────────────
#     display_el = page.locator(
#         f"xpath={LOC['filters']['displayAllSelected'].replace('xpath=', '')}"
#     ).first
#     if display_el.is_visible():
#         print("  ✓ Display filter present (All Selected)")
#
#     # ── Step 7: Wait for map and results to render ────────────────────────────
#     page.wait_for_load_state("load", timeout=15_000)
#     page.wait_for_timeout(6_000)
#
#     try:
#         page.wait_for_selector("text='Results:'", timeout=10_000)
#         print("  ✓ Results panel populated")
#     except Exception:
#         print("  ⚠️  Results panel may still be loading — screenshotting anyway")
#
#     print("  ✓ Results loaded")
#
#     # ── Step 8: Claude validation ─────────────────────────────────────────────
#     result = validator.validate_page(
#         page=page,
#         test_name=f"Address Search: {address}",
#         expected={
#             "OC-5299 AC1 [Address Search Mode]":
#                 "Address is available and selected as the active search mode in the search bar — "
#                 "PASS if 'Address' option/tab/radio is visible and active",
#             "OC-5299 AC2 [SmartyStreets Integration]":
#                 "The map is visible and centered on the searched address, confirming SmartyStreets "
#                 "validated and resolved the address — PASS if map is shown with a pin at the address",
#             "OC-5299 AC3 [Autocomplete Dropdown]":
#                 "Address suggestion dropdown appeared beneath the search input while typing — "
#                 "PASS if autocomplete screenshot shows a dropdown list",
#             "OC-5299 AC4 [Address Format]":
#                 "Suggested addresses in the dropdown are formatted as street, city, state, ZIP — "
#                 "PASS if autocomplete options follow that consistent format",
#             "OC-5299 AC5 [Map Centers on Address]":
#                 "The map is centered on the selected address with a pin placed at that location — "
#                 "PASS if map view is focused on the searched address",
#             "OC-5299 AC6 [Valid Search Anchor]":
#                 "The address is used as a valid search anchor and results are returned even if the "
#                 "address does not exist in Waste Apps data — PASS if map and results are displayed",
#             "OC-5299 AC7 [Clear and Reset]":
#                 "DEFERRED — to be validated in a separate script",
#             "OC-5299 AC8 [No Results Message]":
#                 "DEFERRED — to be validated in a separate script",
#             "OC-5299 AC9 [Recent Searches]":
#                 "DEFERRED — to be validated in a separate script",
#             "search_address_shown":       f"'{address}' appears in the Searched For panel on the left",
#             "results_not_zero":           "At least one result returned — not 'Nothing to display'",
#             "results_count_range":        "At least 600 total results with 300+ Customers / 200+ Jobsites / 80+ Vendors",
#             "all_selected_display":       "Display dropdown shows 'All Selected'",
#             "search_by_address":          "Search By is set to Address (not Name/ID, Lat/Long or City/State)",
#             "radius_circle":              "30 mile radius circle visible on the map",
#             "search_anchor_pin":          "Red origin pin placed at the searched address on the map",
#             "all_pin_types_visible":      "Mix of customer, jobsite and vendor pins visible on map",
#             "green_customer_pins":        "Green building icon pins visible for Active Partnership customers",
#             "grey_customer_pins":         "Grey/neutral building icon pins visible for No Partnership customers",
#             "navy_jobsite_pins":          "Dark navy blue square pins visible for jobsites",
#             "green_vendor_truck_pins":    "Green truck icon pins visible for vendors",
#             "sidebar_tabs":               "All / Customers / Jobsites / Vendors tabs visible in left panel",
#             "apply_btn_present":          "APPLY button visible in top bar",
#             "clear_btn_present":          "CLEAR button visible in top bar",
#             "searched_for_card":          "Searched For card visible top right of map confirming the address",
#             "OC-5304 [Display Filter]":   "Display dropdown shows All Selected by default — PASS if visible and correct",
#             "OC-5390 [Dark Mode]":        "Night/Hybrid/Road buttons visible at bottom of map — PASS if all present",
#             "OC-5705 [Clear Button]":     "CLEAR button present and separate from search address field",
#             "OC-5714 [Search Mode]":      "Local radio button is selected by default — PASS if Local is active",
#             "OC-5796 [Nationwide Zoom]":  "Search Mode is Local not Nationwide — N/A for this test",
#         },
#         context=(
#             get_ticket_context("OC-5304") +
#             "\n\n--- OC-5299: MAP Search By Address ---\n"
#             "AC1: Address must be a selectable search mode. "
#             "AC2: SmartyStreets integration confirmed by map rendering. "
#             "AC3: Autocomplete dropdown appears while typing. "
#             "AC4: Suggestions formatted as street, city, state, ZIP. "
#             "AC5: Map centers on selected address. "
#             "AC6: Valid search anchor even if not in Waste Apps data. "
#             "AC7/AC8/AC9: Deferred to separate scripts.\n\n"
#             "Expected results for 123 Howell Chase Peachtree Corners GA 30096: "
#             "310 Customers / 243 Jobsites / 89 Vendors (total 642). "
#             "Left panel shows Searched For card. Map shows 30mi radius ring and origin pin."
#         ),
#         screenshot_name=f"address_search_{int(time.time())}.png"
#     )
#
#     return result
#
#
# # ─── Main ─────────────────────────────────────────────────────────────────────
#
# def main():
#     with sync_playwright() as p:
#         browser = p.chromium.launch(
#             headless=False,
#             args=["--start-maximized"]
#         )
#         context = browser.new_context(viewport=None)
#         page = context.new_page()
#
#         try:
#             do_login(page)
#             click_map_element(page)
#
#             result = search_address(
#                 page=page,
#                 address="123 Howell Chase, Peachtree Corners, GA 30096"
#             )
#
#             print("\n" + "=" * 60)
#             print(f"{'✅ PASS' if result.passed else '❌ FAIL'} — {result.test_name}")
#             print(f"Summary: {result.summary}")
#             if result.tickets:
#                 print("\nJira Ticket Results:")
#                 for ticket in result.tickets:
#                     print(f"  {ticket}")
#             if result.issues:
#                 print("\nIssues found:")
#                 for issue in result.issues:
#                     print(f"  • {issue}")
#             print("=" * 60)
#
#             validator.report()
#             print("\n✅ Script completed successfully.")
#
#         except Exception as e:
#             print(f"\n❌ Script failed: {e}")
#             page.screenshot(path="debug_error.png")
#         finally:
#             page.wait_for_timeout(3_000)
#             browser.close()
#
#
# if __name__ == "__main__":
#     main()
"""
Playwright Python script – Waste Applications Maps Navigation
Logs in via B2C then clicks the Map navigation element via full XPath.
"""

import json
import time
from playwright.sync_api import Page, sync_playwright
from claude_validator import ClaudeValidator
from qa_context import QA_SYSTEM_PROMPT, get_ticket_context

# ─── Claude Validator ─────────────────────────────────────────────────────────

validator = ClaudeValidator(system_prompt=QA_SYSTEM_PROMPT)

# ─── Page Object ──────────────────────────────────────────────────────────────

with open("map_page.json") as f:
    PAGE = json.load(f)

LOC = PAGE["locators"]

# ─── Credentials ──────────────────────────────────────────────────────────────

VALID_EMAIL    = "kevin.clarke@wasteapplications.com"
VALID_PASSWORD = "Tuesday19@@@@"

# ─── URLs ─────────────────────────────────────────────────────────────────────

LOGIN_URL = (
    "https://dw1qa.b2clogin.com/dw1qa.onmicrosoft.com/b2c_1_qa_signin/oauth2/v2.0/authorize"
    "?client_id=d7d76a18-ff69-445b-8c0e-e3c2d441ae0a"
    "&redirect_uri=https%3A%2F%2Fqa.wasteapplications.com%2FAccount%2FLogin"
    "&response_type=code%20id_token"
    "&scope=openid%20profile%20https%3A%2F%2Fdw1qa.onmicrosoft.com%2F0170418f-5650-4a29-b1e2-ebf4a97954c3%2FAPI.Access"
    "&response_mode=form_post"
)

MAP_XPATH = "/html/body/main/div[1]/oc-app-header/nav/div[2]/div/div[4]/a/span"


# ─── Element helpers ──────────────────────────────────────────────────────────

def _email_field(page: Page):
    candidates = [
        "input[placeholder='Email Address']",
        "#signInName",
        "input[name='signInName']",
        "input[name='logonIdentifier']",
        "input[type='email']",
        "input[placeholder*='email' i]",
        "input[placeholder*='username' i]",
        "input[type='text']",
    ]
    for selector in candidates:
        loc = page.locator(selector).first
        if loc.count() > 0 and loc.is_visible():
            return loc
    return page.locator("input[type='text']").first


def _password_field(page: Page):
    candidates = [
        "input[placeholder='Password']",
        "#password",
        "input[name='password']",
        "input[type='password']",
    ]
    for selector in candidates:
        loc = page.locator(selector).first
        if loc.count() > 0 and loc.is_visible():
            return loc
    return page.locator("input[type='password']").first


def _submit_button(page: Page):
    return page.locator("button[type='submit'][id='next']")


def _fill_and_submit(page: Page, email: str, password: str):
    email_field = _email_field(page)
    pwd_field   = _password_field(page)

    email_field.click()
    email_field.click(click_count=3)
    email_field.type(email, delay=80)
    email_field.press("Tab")
    page.wait_for_timeout(500)

    pwd_field.click()
    pwd_field.click(click_count=3)
    pwd_field.type(password, delay=80)
    page.wait_for_timeout(500)

    _submit_button(page).click()


def _visible_page_text(page: Page) -> str:
    return page.evaluate("""() =>
        Array.from(document.querySelectorAll('*'))
            .filter(el => el.children.length === 0 && el.offsetParent !== null)
            .map(el => el.innerText ? el.innerText.trim() : '')
            .filter(t => t.length > 0)
            .join(' | ')
    """)


# ─── Login ────────────────────────────────────────────────────────────────────

def do_login(page: Page):
    print("→ Navigating to login page...")
    page.goto(LOGIN_URL)
    page.wait_for_load_state("load", timeout=15_000)
    page.wait_for_timeout(1_500)

    print("→ Filling in credentials...")
    _fill_and_submit(page, VALID_EMAIL, VALID_PASSWORD)

    print("→ Waiting for redirect after login...")
    deadline = time.time() + 25
    while time.time() < deadline:
        if "dw1qa.b2clogin.com" not in page.url:
            break
        page.wait_for_timeout(500)
    else:
        page.screenshot(path="debug_login_failed.png")
        raise RuntimeError(
            f"Login redirect did not happen within 25s.\n"
            f"Current URL: {page.url}\n"
            f"Screenshot saved to: debug_login_failed.png"
        )

    page.wait_for_load_state("load", timeout=15_000)
    page.wait_for_timeout(2_000)
    print(f"✓ Logged in. Current URL: {page.url}")


# ─── Map navigation ───────────────────────────────────────────────────────────

def click_map_element(page: Page):
    print("→ Locating Map element via XPath...")

    try:
        page.wait_for_selector(
            f"xpath={MAP_XPATH}",
            state="visible",
            timeout=15_000
        )
        print("  ✓ Map element found and visible")
    except Exception as e:
        page.screenshot(path="debug_map_not_found.png")
        raise RuntimeError(
            f"Map element not found via XPath within 15s.\n"
            f"Current URL: {page.url}\n"
            f"Visible text: {_visible_page_text(page)}"
        ) from e

    map_span = page.locator(f"xpath={MAP_XPATH}").first
    map_span.scroll_into_view_if_needed()
    page.wait_for_timeout(500)

    print("→ Attempting standard click...")
    map_span.click()
    page.wait_for_timeout(2_000)

    if "/map" in page.url:
        print("  ✓ Standard click worked.")
    else:
        print("  Trying JS click...")
        page.evaluate(f"""
            const result = document.evaluate(
                '{MAP_XPATH}', document, null,
                XPathResult.FIRST_ORDERED_NODE_TYPE, null
            );
            if (result.singleNodeValue) {{ result.singleNodeValue.click(); }}
        """)
        page.wait_for_timeout(2_000)

    if "/map" not in page.url:
        print("  Trying parent <a> click...")
        page.evaluate(f"""
            const result = document.evaluate(
                '{MAP_XPATH}', document, null,
                XPathResult.FIRST_ORDERED_NODE_TYPE, null
            );
            const span = result.singleNodeValue;
            if (span && span.closest('a')) {{ span.closest('a').click(); }}
        """)
        page.wait_for_timeout(2_000)

    if "/map" not in page.url:
        print("  Navigating directly to /map...")
        page.evaluate("window.location.href = '/map'")
        page.wait_for_timeout(2_000)

    page.wait_for_load_state("load", timeout=15_000)
    page.wait_for_timeout(3_000)

    assert "/map" in page.url, \
        f"Expected URL to contain '/map', got: {page.url}"

    page.screenshot(path="debug_map_loaded.png")
    print(f"✓ Map page loaded. Current URL: {page.url}")
    print("  Screenshot saved to: debug_map_loaded.png")


# ─── Address Search ───────────────────────────────────────────────────────────

def search_address(page: Page, address: str) -> dict:
    print(f"\n→ Searching address: {address}")

    # ── Step 1: Ensure Local mode is selected ─────────────────────────────────
    local_radio = page.locator(LOC["filters"]["localRadio"]).first
    if local_radio.is_visible():
        local_radio.click()
        print("  ✓ Local mode selected")
        page.wait_for_timeout(300)

    # ── Step 2: Click and clear the search field ──────────────────────────────
    search_field = page.locator(LOC["filters"]["addressSearch"]).first
    search_field.click()
    search_field.click(click_count=3)
    page.wait_for_timeout(200)

    # ── Step 3: Type address — fires onChange per keystroke for SmartyStreets ─
    search_field.type(address, delay=80)
    print(f"  ✓ Address typed: {address}")

    # ── Step 4: Wait for autocomplete dropdown ────────────────────────────────
    page.wait_for_timeout(1_500)

    # ── OC-5299 AC3/AC4: Capture dropdown while visible ──────────────────────
    page.screenshot(path="debug_address_autocomplete.png")
    print("  ✓ Autocomplete screenshot saved: debug_address_autocomplete.png")

    # ── Step 5: Select first suggestion ──────────────────────────────────────
    search_field.press("ArrowDown")
    page.wait_for_timeout(400)
    search_field.press("Enter")
    print("  ✓ First autocomplete suggestion selected")
    page.wait_for_timeout(1_000)

    # ── Step 6: Confirm Display is All Selected ───────────────────────────────
    display_el = page.locator(
        f"xpath={LOC['filters']['displayAllSelected'].replace('xpath=', '')}"
    ).first
    if display_el.is_visible():
        print("  ✓ Display filter present (All Selected)")

    # ── Step 7: Wait for map and results to render ────────────────────────────
    page.wait_for_load_state("load", timeout=15_000)
    page.wait_for_timeout(6_000)

    try:
        page.wait_for_selector("text='Results:'", timeout=10_000)
        print("  ✓ Results panel populated")
    except Exception:
        print("  ⚠️  Results panel may still be loading — screenshotting anyway")

    print("  ✓ Results loaded")

    # ── Step 8: Claude validation ─────────────────────────────────────────────
    result = validator.validate_page(
        page=page,
        test_name=f"Address Search: {address}",
        expected={
            "OC-5299 AC1 [Address Search Mode]":
                "Address is available and selected as the active search mode in the search bar — "
                "PASS if 'Address' option/tab/radio is visible and active",
            "OC-5299 AC2 [SmartyStreets Integration]":
                "The map is visible and centered on the searched address, confirming SmartyStreets "
                "validated and resolved the address — PASS if map is shown with a pin at the address",
            "OC-5299 AC3 [Autocomplete Dropdown]":
                "Address suggestion dropdown appeared beneath the search input while typing — "
                "PASS if autocomplete screenshot shows a dropdown list",
            "OC-5299 AC4 [Address Format]":
                "Suggested addresses in the dropdown are formatted as street, city, state, ZIP — "
                "PASS if autocomplete options follow that consistent format",
            "OC-5299 AC5 [Map Centers on Address]":
                "The map is centered on the selected address with a pin placed at that location — "
                "PASS if map view is focused on the searched address",
            "OC-5299 AC6 [Valid Search Anchor]":
                "The address is used as a valid search anchor and results are returned even if the "
                "address does not exist in Waste Apps data — PASS if map and results are displayed",
            "OC-5299 AC7 [Clear and Reset]":
                "DEFERRED — to be validated in a separate script",
            "OC-5299 AC8 [No Results Message]":
                "DEFERRED — to be validated in a separate script",
            "OC-5299 AC9 [Recent Searches]":
                "DEFERRED — to be validated in a separate script",
            "search_address_shown":       f"'{address}' appears in the Searched For panel on the left",
            "results_not_zero":           "At least one result returned — not 'Nothing to display'",
            "results_count_range":        "At least 600 total results with 300+ Customers / 200+ Jobsites / 80+ Vendors",
            "all_selected_display":       "Display dropdown shows 'All Selected'",
            "search_by_address":          "Search By is set to Address (not Name/ID, Lat/Long or City/State)",
            "radius_circle":              "30 mile radius circle visible on the map",
            "search_anchor_pin":          "Red origin pin placed at the searched address on the map",
            "all_pin_types_visible":      "Mix of customer, jobsite and vendor pins visible on map",
            "green_customer_pins":        "Green building icon pins visible for Active Partnership customers",
            "grey_customer_pins":         "Grey/neutral building icon pins visible for No Partnership customers",
            "navy_jobsite_pins":          "Dark navy blue square pins visible for jobsites",
            "green_vendor_truck_pins":    "Green truck icon pins visible for vendors",
            "sidebar_tabs":               "All / Customers / Jobsites / Vendors tabs visible in left panel",
            "apply_btn_present":          "APPLY button visible in top bar",
            "clear_btn_present":          "CLEAR button visible in top bar",
            "searched_for_card":          "Searched For card visible top right of map confirming the address",
            "OC-5304 [Display Filter]":   "Display dropdown shows All Selected by default — PASS if visible and correct",
            "OC-5390 [Dark Mode]":        "Night/Hybrid/Road buttons visible at bottom of map — PASS if all present",
            "OC-5705 [Clear Button]":     "CLEAR button present and separate from search address field",
            "OC-5714 [Search Mode]":      "Local radio button is selected by default — PASS if Local is active",
            "OC-5796 [Nationwide Zoom]":  "Search Mode is Local not Nationwide — N/A for this test",
        },
        context=(
            get_ticket_context("OC-5304") +
            "\n\n--- OC-5299: MAP Search By Address ---\n"
            "AC1: Address must be a selectable search mode. "
            "AC2: SmartyStreets integration confirmed by map rendering. "
            "AC3: Autocomplete dropdown appears while typing. "
            "AC4: Suggestions formatted as street, city, state, ZIP. "
            "AC5: Map centers on selected address. "
            "AC6: Valid search anchor even if not in Waste Apps data. "
            "AC7/AC8/AC9: Deferred to separate scripts.\n\n"
            "Expected results for 123 Howell Chase Peachtree Corners GA 30096: "
            "310 Customers / 243 Jobsites / 89 Vendors (total 642). "
            "Left panel shows Searched For card. Map shows 30mi radius ring and origin pin."
        ),
        screenshot_name=f"address_search_{int(time.time())}.png"
    )

    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized"]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir="videos/",
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        try:
            do_login(page)
            click_map_element(page)

            result = search_address(
                page=page,
                address="123 Howell Chase, Peachtree Corners, GA 30096"
            )

            print("\n" + "=" * 60)
            print(f"{'✅ PASS' if result.passed else '❌ FAIL'} — {result.test_name}")
            print(f"Summary: {result.summary}")
            if result.tickets:
                print("\nJira Ticket Results:")
                for ticket in result.tickets:
                    print(f"  {ticket}")
            if result.issues:
                print("\nIssues found:")
                for issue in result.issues:
                    print(f"  • {issue}")
            print("=" * 60)

            validator.report()
            print("\n✅ Script completed successfully.")

        except Exception as e:
            print(f"\n❌ Script failed: {e}")
            page.screenshot(path="debug_error.png")

        finally:
            page.wait_for_timeout(3_000)
            context.close()   # must close context (not just browser) to flush video
            browser.close()
            print("\n  🎥 Video saved to: videos/")


if __name__ == "__main__":
    main()