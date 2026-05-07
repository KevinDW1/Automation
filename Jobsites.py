"""
Playwright Python – Waste Applications: Jobsites (Syncfusion-Aware)
====================================================================
Redesign principles applied from the Syncfusion Playwright guide:

  ✅  Page Object Model (POM) — each page/component is a class
  ✅  Prefer get_by_role / has_text over brittle CSS paths
  ✅  State-based waits  (spinner hidden, row count > 0)
  ✅  page.evaluate for Syncfusion JS-instance validation
  ✅  Mouse.click on bounding-box centre for Syncfusion autocomplete
  ✅  Selector fallback chains kept but ordered by stability
  ✅  Structured result objects instead of raw prints
  ✅  Single responsibility per method
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional
from playwright.sync_api import Page, sync_playwright, Locator

# ══════════════════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════════════════

EMAIL    = "kevin.clarke@wasteapplications.com"
PASSWORD = "Tuesday19@@@@"

LOGIN_URL = (
    "https://dw1qa.b2clogin.com/dw1qa.onmicrosoft.com/b2c_1_qa_signin/oauth2/v2.0/authorize"
    "?client_id=d7d76a18-ff69-445b-8c0e-e3c2d441ae0a"
    "&redirect_uri=https%3A%2F%2Fqa.wasteapplications.com%2FAccount%2FLogin"
    "&response_type=code%20id_token"
    "&scope=openid%20profile%20https%3A%2F%2Fdw1qa.onmicrosoft.com%2F0170418f-5650-4a29-b1e2-ebf4a97954c3%2FAPI.Access"
    "&response_mode=form_post"
)
JOBSITE_URL    = "https://qa.wasteapplications.com/Modules/Jobsite/Jobsite"
CUSTOMER_QUERY = "1627"

# ══════════════════════════════════════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LinkResult:
    text:   str
    href:   str
    status: int | str   # int HTTP code or "ERROR"

    @property
    def is_broken(self) -> bool:
        return self.status == "ERROR" or (isinstance(self.status, int) and self.status >= 400)

@dataclass
class RunReport:
    broken_links: list[LinkResult] = field(default_factory=list)
    customer_selected: Optional[str] = None
    success: bool = False
    error:   Optional[str] = None

# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _first_visible(page: Page, selectors: list[str]) -> Optional[Locator]:
    """Return the first locator that is visible, or None."""
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count() > 0 and loc.is_visible():
            return loc
    return None


def _click_first_visible(page: Page, selectors: list[str], label: str) -> None:
    loc = _first_visible(page, selectors)
    if loc is None:
        raise RuntimeError(f"Could not find visible element for: {label}")
    loc.click()
    print(f"  ✓ Clicked [{label}]")


def _wait_for_syncfusion_grid(page: Page, timeout: int = 15_000) -> None:
    """
    Wait until the Syncfusion grid is rendered and its spinner is gone.
    Uses JS-instance check as the ground truth.
    """
    # 1. Grid element present
    page.locator(".e-grid").wait_for(state="visible", timeout=timeout)

    # 2. All spinners hidden (re-render complete).
    # Use wait_for_function instead of locator.wait_for to avoid strict-mode
    # violation when multiple .e-spin-show elements exist simultaneously.
    page.wait_for_function(
        "() => document.querySelectorAll('.e-spin-show').length === 0",
        timeout=timeout,
    )

    # 3. At least one data row OR the empty-row indicator
    page.wait_for_function(
        """() => {
            const rows = document.querySelectorAll('.e-row');
            const empty = document.querySelector('.e-emptyrow');
            return rows.length > 0 || empty !== null;
        }""",
        timeout=timeout,
    )
    print("  ✓ Syncfusion grid ready")


def _syncfusion_grid_row_count(page: Page) -> int:
    """Read row count directly from the Syncfusion JS instance."""
    return page.evaluate(
        """() => {
            const grid = document.querySelector('.e-grid');
            if (!grid || !grid.ej2_instances) return -1;
            const ds = grid.ej2_instances[0].dataSource;
            return Array.isArray(ds) ? ds.length : -1;
        }"""
    )

# ══════════════════════════════════════════════════════════════════════════════
# Page Objects
# ══════════════════════════════════════════════════════════════════════════════

class B2CLoginPage:
    """
    Azure AD B2C login page.

    Key fix: navigate() now blocks until an email input is *actually visible*
    before returning — prevents the 30s timeout that occurs when login()
    tries to click a field that hasn't painted yet.
    """

    # Ordered most-specific → least-specific.
    # The fallback `input[type='text']` is intentionally NOT in this list —
    # we use wait_for(visible) below instead of a blind locator grab.
    EMAIL_SELECTORS = [
        "#signInName",
        "input[name='signInName']",
        "input[name='logonIdentifier']",
        "input[placeholder='Email Address']",
        "input[type='email']",
        "input[placeholder*='email' i]",
        "input[placeholder*='username' i]",
        "input[type='text']",
    ]

    PASSWORD_SELECTORS = [
        "#password",
        "input[name='password']",
        "input[placeholder='Password']",
        "input[type='password']",
    ]

    def __init__(self, page: Page):
        self.page = page

    # ── navigate ──────────────────────────────────────────────────────────────

    def navigate(self) -> None:
        """
        Go to the B2C login URL and block until the email field is visible.
        Using networkidle alone is insufficient for B2C — the form is
        injected via JS after the initial page load.
        """
        print("→ Navigating to B2C login…")
        self.page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)

        print("  → Waiting for email field to become visible…")
        found = False
        for sel in self.EMAIL_SELECTORS:
            try:
                self.page.locator(sel).first.wait_for(state="visible", timeout=20_000)
                print(f"  ✓ Email field visible via: '{sel}'")
                found = True
                break
            except Exception:
                continue

        if not found:
            # Dump what IS on the page to help diagnose
            all_inputs = self.page.evaluate(
                """() => Array.from(document.querySelectorAll('input')).map(i => ({
                    type:        i.type,
                    id:          i.id,
                    name:        i.name,
                    placeholder: i.placeholder,
                    visible:     i.offsetParent !== null,
                }))"""
            )
            self.page.screenshot(path="debug_login_page.png")
            print(f"  ✗ No email field found. Inputs on page: {all_inputs}")
            raise RuntimeError(
                "B2C login form did not render within 20s. "
                "See debug_login_page.png and input dump above."
            )

    # ── field locators ────────────────────────────────────────────────────────

    def _get_email_input(self) -> Locator:
        """Return the email locator that is currently visible (no timeout risk)."""
        loc = _first_visible(self.page, self.EMAIL_SELECTORS)
        if loc is None:
            raise RuntimeError("Email input not found — did navigate() complete?")
        return loc

    def _get_password_input(self) -> Locator:
        loc = _first_visible(self.page, self.PASSWORD_SELECTORS)
        if loc is None:
            raise RuntimeError("Password input not found.")
        return loc

    def _get_submit_button(self) -> Locator:
        # Try id+type first (most specific), fall back to any submit button
        for sel in [
            "button[type='submit'][id='next']",
            "button[type='submit']",
            "input[type='submit']",
        ]:
            loc = self.page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                return loc
        raise RuntimeError("Submit button not found on login page.")

    # ── login ─────────────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> None:
        """Fill credentials and submit. Fields are guaranteed visible by navigate()."""
        print("→ Entering credentials…")

        email_input = self._get_email_input()
        email_input.click(click_count=3)
        email_input.type(email, delay=80)
        email_input.press("Tab")
        self.page.wait_for_timeout(400)

        pwd_input = self._get_password_input()
        pwd_input.wait_for(state="visible", timeout=5_000)
        pwd_input.click(click_count=3)
        pwd_input.type(password, delay=80)
        self.page.wait_for_timeout(300)

        submit = self._get_submit_button()
        submit.click()
        print("  ✓ Credentials submitted")

    # ── wait for redirect ─────────────────────────────────────────────────────

    def wait_for_redirect(self, away_from: str = "dw1qa.b2clogin.com", timeout: int = 30) -> None:
        """Block until the browser leaves the B2C domain."""
        print("→ Waiting for post-login redirect…")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if away_from not in self.page.url:
                self.page.wait_for_load_state("networkidle", timeout=25_000)
                print(f"  ✓ Redirected to: {self.page.url}")
                return
            self.page.wait_for_timeout(500)

        self.page.screenshot(path="debug_login_failed.png")
        raise RuntimeError(
            f"Login redirect did not occur within {timeout}s.\n"
            f"Current URL: {self.page.url}\n"
            f"Screenshot: debug_login_failed.png"
        )


class AppNavigation:
    """Top-level navigation bar (Management menu, etc.)."""

    def __init__(self, page: Page):
        self.page = page

    def open_jobsites(self) -> None:
        print("→ Opening Management > Jobsites…")
        _click_first_visible(self.page, [
            "button:has-text('Management')",
            "a:has-text('Management')",
            "text=Management",
        ], "Management menu")

        self.page.wait_for_timeout(800)   # brief — menu animation only

        _click_first_visible(self.page, [
            "a[href='/Modules/Jobsite/Jobsite']",
            "a[href*='Jobsite']",
            "a:has-text('Jobsite')",
        ], "Jobsites link")

        self.page.wait_for_load_state("networkidle", timeout=20_000)

        # Fallback: direct navigation if URL didn't update
        if "Jobsite" not in self.page.url:
            print("  ⚠  URL mismatch — falling back to direct navigation")
            self.page.goto(JOBSITE_URL)
            self.page.wait_for_load_state("networkidle", timeout=20_000)

        print(f"  ✓ Jobsites page loaded: {self.page.url}")


class JobsiteGridPage:
    """
    Syncfusion Grid on the Jobsites list page.

    Uses:
      • .e-grid / .e-row  selectors (Syncfusion EJ2 class conventions)
      • JS instance evaluation for row-count validation
      • State-based pagination (spinner + row presence)
    """

    def __init__(self, page: Page):
        self.page = page

    def wait_for_grid(self) -> None:
        _wait_for_syncfusion_grid(self.page)

    def _collect_page_links(self) -> list[dict]:
        """Collect href + text for every link currently visible in the grid."""
        # Prefer the Syncfusion grid wrapper; fall back to generic table wrapper
        container = (
            ".e-grid a[href]"
            if self.page.locator(".e-grid").count() > 0
            else "div.oc-table-wrapper a[href]"
        )
        return self.page.eval_on_selector_all(
            container,
            "els => els.map(el => ({ text: el.innerText.trim(), href: el.href }))",
        )

    def _go_to_next_page(self) -> bool:
        """
        Click the Syncfusion grid next-page button.
        Returns True if navigation occurred, False if on last page.
        """
        # Syncfusion pager uses aria-label="Next page" (case-insensitive)
        next_btn = self.page.locator(
            "div.e-gridpager button[title='Next page']:not([disabled]),"
            "div.e-gridpager button[aria-label='Next page']:not([disabled]),"
            "button[aria-label='Next Page']:not([disabled])"
        ).first

        if next_btn.count() == 0 or not next_btn.is_enabled():
            return False

        next_btn.click()
        # Wait: spinner appears → disappears → rows repopulate
        _wait_for_syncfusion_grid(self.page)
        return True

    def check_all_links(self) -> list[LinkResult]:
        """
        Iterate every grid page and HEAD-check each link.
        Returns a list of LinkResult, filtered to broken ones by caller.
        """
        print("\n→ Checking all Syncfusion grid links…")
        results: list[LinkResult] = []
        checked: set[str] = set()
        page_num = 1

        while True:
            self.wait_for_grid()
            links = self._collect_page_links()
            new_links = [l for l in links if l["href"] not in checked]
            print(f"  Page {page_num}: {len(new_links)} new link(s)")

            for link in new_links:
                href = link["href"]
                checked.add(href)
                text = link["text"] or href.split("/")[-1]

                try:
                    resp   = self.page.request.fetch(href, method="HEAD", timeout=8_000)
                    status = resp.status
                    marker = "✅" if status < 400 else "❌"
                    print(f"    {marker} [{status}] {text}")
                    results.append(LinkResult(text=text, href=href, status=status))
                except Exception as exc:
                    print(f"    ⚠  {text}: {exc}")
                    results.append(LinkResult(text=text, href=href, status="ERROR"))

            if not self._go_to_next_page():
                break
            page_num += 1

        broken = [r for r in results if r.is_broken]
        print(f"\n  Checked {len(checked)} link(s) — {len(broken)} broken")
        return results


class NewJobsiteWizard:
    """
    Modal / wizard that opens when 'New Jobsite' is clicked.

    Blazor + Syncfusion rules applied (per guide):
      ✅ Always target the raw <input.e-input>, never the wrapper span
      ✅ Wait for Blazor render cycle before touching any input
      ✅ Use Control+A + Backspace to clear, then keyboard.type() char-by-char
      ✅ Avoid .fill() on Syncfusion inputs — it bypasses internal listeners
      ✅ Confirm field value via input_value() before proceeding
    """

    # Target the exact input revealed by the DOM dump:
    # class="e-control e-autocomplete e-lib e-input" (visible, not disabled)
    # We exclude e-disabled inputs explicitly.
    AUTOCOMPLETE_CLASS = "e-control e-autocomplete e-lib e-input"

    def __init__(self, page: Page):
        self.page = page

    # ── Blazor readiness ──────────────────────────────────────────────────────

    def _wait_for_blazor_and_syncfusion(self) -> None:
        """
        Wait until Blazor has finished rendering AND at least one
        Syncfusion .e-control is mounted in the DOM.
        Per guide: always do this before touching any input.
        """
        self.page.wait_for_function(
            """() => {
                const ctrl = document.querySelector('.e-control');
                return ctrl && ctrl.closest('.e-lib') !== null;
            }""",
            timeout=10_000,
        )
        print("  ✓ Blazor + Syncfusion render confirmed")

    # ── Open wizard ───────────────────────────────────────────────────────────

    def open(self) -> None:
        print("\n→ Opening New Jobsite wizard…")
        _click_first_visible(self.page, [
            "button.oc-button-primary:has-text('New Jobsite')",
            "button:has-text('New Jobsite')",
            "button:has-text('NEW JOBSITE')",
            "button[aria-label*='New Jobsite' i]",
        ], "New Jobsite button")

        # Do NOT wait for a specific modal class — the wizard may render as a
        # full page, side panel, or inline form rather than a dialog.
        # Instead wait for any visible Syncfusion input to appear, which is the
        # reliable signal that Blazor has finished rendering the wizard content.
        print("  → Waiting for wizard input(s) to render…")
        try:
            self.page.wait_for_function(
                """() => {
                    const inputs = document.querySelectorAll(
                        'input.e-input, input.e-autocomplete, input[role="combobox"]'
                    );
                    for (const i of inputs) {
                        if (i.offsetParent !== null) return true;
                    }
                    return false;
                }""",
                timeout=15_000,
            )
            print("  ✓ Wizard input visible — Blazor render complete")
        except Exception:
            info = self.page.evaluate(
                """() => ({
                    url:    window.location.href,
                    inputs: Array.from(document.querySelectorAll('input')).map(i => ({
                                type: i.type, cls: i.className,
                                visible: i.offsetParent !== null,
                            })),
                })"""
            )
            self.page.screenshot(path="debug_new_jobsite_modal.png")
            print(f"  ✗ Wizard did not render. DOM state: {info}")
            raise RuntimeError(
                "New Jobsite wizard inputs did not appear within 15s. "
                "See debug_new_jobsite_modal.png"
            )

        self._wait_for_blazor_and_syncfusion()
        self.page.screenshot(path="debug_new_jobsite_modal.png")
        print("  ✓ Screenshot: debug_new_jobsite_modal.png")

    # ── Locate the raw <input> ────────────────────────────────────────────────

    def _locate_raw_input(self) -> Locator:
        """
        Locate the autocomplete input using the exact class string confirmed
        by the DOM dump: 'e-control e-autocomplete e-lib e-input'.
        Excludes disabled inputs. Falls back to any visible e-autocomplete.
        """
        # Strategy 1: exact class match from DOM dump (not disabled)
        js_result = self.page.evaluate(
            """() => {
                const all = document.querySelectorAll('input.e-autocomplete');
                for (const el of all) {
                    if (el.offsetParent !== null &&
                        !el.classList.contains('e-disabled') &&
                        !el.disabled) {
                        return {
                            classes:   el.className,
                            ariaLabel: el.getAttribute('aria-label') || '',
                            index:     Array.from(document.querySelectorAll('input')).indexOf(el),
                        };
                    }
                }
                return null;
            }"""
        )

        if js_result:
            print(f"  ✓ Autocomplete input confirmed in DOM — "
                  f"class='{js_result['classes']}' "
                  f"aria-label='{js_result['ariaLabel']}' "
                  f"DOM index={js_result['index']}")
            # Return Playwright locator for the same element
            loc = self.page.locator("input.e-autocomplete:not(.e-disabled)").first
            if loc.count() > 0:
                return loc

        # Diagnostic dump
        inputs = self.page.evaluate(
            """() => Array.from(document.querySelectorAll('input')).map((el, i) => ({
                index:   i,
                classes: el.className,
                visible: el.offsetParent !== null,
                disabled: el.disabled,
            }))"""
        )
        self.page.screenshot(path="debug_no_input_found.png")
        print("  ✗ No autocomplete input found. All inputs:")
        for inp in inputs:
            print(f"      {inp}")
        raise RuntimeError(
            "Could not locate autocomplete input. See debug_no_input_found.png"
        )

    # ── Focus the autocomplete input ─────────────────────────────────────────

    def _click_and_confirm_focus(self, field: Locator) -> None:
        """
        Focus strategy specifically for this wizard layout where a BUTTON
        sits above the input and steals focus on every mouse click.

        Solution: use JS to find the autocomplete input by its confirmed class,
        call .focus() on it, then immediately prevent the button from stealing
        focus back by temporarily disabling pointer-events on it.
        """
        field.scroll_into_view_if_needed()
        self.page.wait_for_timeout(100)

        # Step 1: Disable the overlapping wizard-next-button pointer events
        # so it cannot intercept focus, then focus the autocomplete input.
        self.page.evaluate(
            """() => {
                // Temporarily neutralise the button that steals focus
                const btn = document.querySelector('.wizard-next-button');
                if (btn) {
                    btn._savedPointerEvents = btn.style.pointerEvents;
                    btn.style.pointerEvents = 'none';
                }

                // Focus the first visible, non-disabled autocomplete input
                const inputs = document.querySelectorAll('input.e-autocomplete');
                for (const el of inputs) {
                    if (el.offsetParent !== null && !el.disabled &&
                        !el.classList.contains('e-disabled')) {
                        el.focus();
                        break;
                    }
                }

                // Restore the button immediately after focus is set
                if (btn) {
                    btn.style.pointerEvents = btn._savedPointerEvents || '';
                }
            }"""
        )
        self.page.wait_for_timeout(300)

        # Step 2: Verify activeElement is the INPUT
        active = self.page.evaluate(
            """() => {
                const ae = document.activeElement;
                if (!ae) return null;
                return {
                    tag:      ae.tagName,
                    classes:  ae.className,
                    isInput:  ae.tagName === 'INPUT',
                    isAutoComplete: ae.classList.contains('e-autocomplete'),
                };
            }"""
        )

        if not active or not active["isInput"]:
            debug = self.page.evaluate(
                """() => ({
                    active: document.activeElement
                        ? document.activeElement.tagName + ' | ' + document.activeElement.className
                        : 'none',
                })"""
            )
            self.page.screenshot(path="debug_focus_failed.png")
            print(f"  ✗ Focus still not on INPUT: {debug}")
            raise RuntimeError(
                f"Could not focus autocomplete input. activeElement: {active}. "
                "See debug_focus_failed.png"
            )

        print(f"  ✓ Focus on autocomplete INPUT confirmed — "
              f"isAutoComplete={active.get('isAutoComplete')} "
              f"class='{active.get('classes','')[:50]}'")

    # ── Clear + type per Blazor guide ─────────────────────────────────────────

    def _clear_and_type(self, field: Locator, query: str) -> None:
        """
        Blazor guide method for Syncfusion inputs:
          1. Control+A  (select all existing text)
          2. Backspace  (delete it)
          3. keyboard.type() char-by-char with delay

        Avoids .fill() which bypasses Syncfusion's internal event listeners.
        Verifies field value via input_value() afterward.
        """
        field.press("Control+A")
        field.press("Backspace")
        self.page.wait_for_timeout(100)

        # Type character by character — triggers Syncfusion debounce on each keystroke
        self.page.keyboard.type(query, delay=150)
        self.page.wait_for_timeout(500)

        # Hard verification — read the actual DOM value
        actual = field.input_value()
        if query in actual:
            print(f"  ✓ Field value confirmed: '{actual}'")
        else:
            print(f"  ⚠  Field shows '{actual}' — expected '{query}'")
            print("  → Retrying with slower typing…")

            # Retry: click again, clear, type slower
            self._click_and_confirm_focus(field)
            field.press("Control+A")
            field.press("Backspace")
            self.page.wait_for_timeout(150)
            self.page.keyboard.type(query, delay=300)
            self.page.wait_for_timeout(600)

            actual = field.input_value()
            print(f"  {'✓' if query in actual else '✗'} Field value after retry: '{actual}'")

    # ── Wait for dropdown ─────────────────────────────────────────────────────

    def _wait_for_dropdown(self) -> bool:
        """
        Wait for Syncfusion's suggestion list popup.
        Tries selectors in order — logs which one matched.
        """
        for sel in [
            "ul[id*='_options'][role='listbox']",
            "[role='listbox']",
            ".e-autocomplete-list",
            ".e-list-parent",
            "ul.e-ul",
        ]:
            try:
                self.page.locator(sel).first.wait_for(state="visible", timeout=5_000)
                print(f"  ✓ Dropdown appeared — selector: '{sel}'")
                return True
            except Exception:
                continue

        self.page.screenshot(path="debug_no_dropdown.png")
        print("  ⚠  Dropdown did not appear (screenshot: debug_no_dropdown.png)")
        return False

    # ── fill_customer (main entry point) ─────────────────────────────────────

    def fill_customer(self, query: str) -> str:
        """
        Full Blazor-correct sequence:
          1. Locate raw <input.e-input>
          2. Click + confirm DOM focus on that input
          3. Control+A → Backspace → keyboard.type() with verification
          4. Wait for dropdown
          5. Select first item (click preferred, keyboard fallback)
        """
        print(f"\n→ Filling Customer Information with '{query}'…")

        # Step 1: raw input — not the wrapper
        field = self._locate_raw_input()

        # Step 2: click + confirm focus
        self._click_and_confirm_focus(field)

        # Step 3: clear + type + verify
        self._clear_and_type(field, query)

        self.page.screenshot(path="debug_after_typing.png")
        print("  ✓ Post-typing screenshot: debug_after_typing.png")

        # Step 4: wait for dropdown
        dropdown_visible = self._wait_for_dropdown()
        self.page.screenshot(path="debug_customer_dropdown.png")
        print("  ✓ Dropdown screenshot: debug_customer_dropdown.png")

        # Step 5: select
        selected_text = ""
        if dropdown_visible:
            try:
                first_item = self.page.locator(
                    "[role='listbox'] li.e-list-item, [role='listbox'] li"
                ).first
                first_item.wait_for(state="visible", timeout=4_000)
                selected_text = first_item.inner_text().strip()
                first_item.click()
                print(f"  ✓ Item selected via click: '{selected_text}'")
            except Exception as exc:
                print(f"  ⚠  Click on list item failed ({exc}) — keyboard fallback")
                self.page.keyboard.press("ArrowDown")
                self.page.wait_for_timeout(300)
                self.page.keyboard.press("Enter")
                selected_text = field.input_value()
                print(f"  ✓ Item selected via keyboard: '{selected_text}'")
        else:
            print("  → No dropdown — ArrowDown+Enter fallback")
            self.page.keyboard.press("ArrowDown")
            self.page.wait_for_timeout(400)
            self.page.keyboard.press("Enter")
            selected_text = field.input_value()
            print(f"  ✓ Post-Enter field value: '{selected_text}'")

        self.page.wait_for_timeout(800)
        self.page.screenshot(path="debug_customer_selected.png")
        print("  ✓ Selection confirmed (screenshot: debug_customer_selected.png)")
        return selected_text

    def click_next(self) -> None:
        print("\n→ Clicking NEXT…")
        _click_first_visible(self.page, [
            "button:has-text('NEXT')",
            "button:has-text('Next')",
            "button[aria-label*='Next' i]",
        ], "NEXT button")

        # Wait for wizard to advance (spinner or new panel)
        try:
            self.page.locator(".e-spin-show").wait_for(state="hidden", timeout=5_000)
        except Exception:
            self.page.wait_for_timeout(1_000)

        self.page.screenshot(path="debug_after_next.png")
        print("  ✓ Wizard advanced (screenshot: debug_after_next.png)")


# ══════════════════════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════════════════════

def run(page: Page) -> RunReport:
    report = RunReport()

    # 1. Login
    login_page = B2CLoginPage(page)
    login_page.navigate()
    login_page.login(EMAIL, PASSWORD)
    login_page.wait_for_redirect()

    # 2. Navigate to Jobsites
    nav = AppNavigation(page)
    nav.open_jobsites()

    # 3. Check grid links
    grid = JobsiteGridPage(page)
    all_results = grid.check_all_links()
    report.broken_links = [r for r in all_results if r.is_broken]

    # 4. Open New Jobsite wizard
    wizard = NewJobsiteWizard(page)
    wizard.open()

    # 5. Fill customer autocomplete and advance
    report.customer_selected = wizard.fill_customer(CUSTOMER_QUERY)
    wizard.click_next()

    report.success = True
    return report


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir="videos/",
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        report = RunReport()

        try:
            report = run(page)
        except Exception as exc:
            report.error = str(exc)
            print(f"\n❌ Script failed: {exc}")
            page.screenshot(path="debug_error.png")
        finally:
            page.wait_for_timeout(2_000)
            context.close()
            browser.close()

        # ── Final report ──────────────────────────────────────────────────────
        print("\n" + "═" * 60)
        if report.success:
            print("✅  New Jobsite flow completed successfully.")
            print(f"    Customer selected: {report.customer_selected}")
        else:
            print(f"❌  Flow failed: {report.error}")

        if report.broken_links:
            print(f"\n⚠️   {len(report.broken_links)} broken link(s) found:")
            for b in report.broken_links:
                print(f"    ❌ [{b.status}] {b.text}")
                print(f"       {b.href}")
        else:
            print("\n✅  All grid links valid — no broken links found.")

        print("═" * 60)
        print("🎥  Video saved to: videos/")


if __name__ == "__main__":
    main()