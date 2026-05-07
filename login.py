"""
Playwright Python test suite – Waste Applications Login Page
Generated from: https://qa.wasteapplications.com/Account/Login (B2C login)
Covers: 16 test steps (9 positive / 7 negative)
"""

import os
import re
import pytest
from playwright.sync_api import Page, expect

# ─── Credentials ──────────────────────────────────────────────────────────────

VALID_EMAIL    = "kevin.clarke@wasteapplications.com"
VALID_PASSWORD = "Tuesday19@@@@"

# ─── Login URL ────────────────────────────────────────────────────────────────

LOGIN_URL = (
    "https://dw1qa.b2clogin.com/dw1qa.onmicrosoft.com/b2c_1_qa_signin/oauth2/v2.0/authorize"
    "?client_id=d7d76a18-ff69-445b-8c0e-e3c2d441ae0a"
    "&redirect_uri=https%3A%2F%2Fqa.wasteapplications.com%2FAccount%2FLogin"
    "&response_type=code%20id_token"
    "&scope=openid%20profile%20https%3A%2F%2Fdw1qa.onmicrosoft.com%2F0170418f-5650-4a29-b1e2-ebf4a97954c3%2FAPI.Access"
    "&response_mode=form_post"
)

# ─── Email pattern (from the original JSON spec) ──────────────────────────────

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9!#$%&'+^_`{}~-]+"
    r"(?:\.[a-zA-Z0-9!#$%&'+^_`{}~-]+)*"
    r"@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$"
)

XSS_PAYLOAD = "<script>alert(1)</script>"

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def login_page(page: Page) -> Page:
    """Navigate to the B2C login page and return the Page object."""
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")
    return page


# ─── Element helpers ──────────────────────────────────────────────────────────

def _email_field(page: Page):
    """Find the email/username input using a cascade of selectors."""
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
    """Find the password input."""
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
    """
    Reliably fill and submit the B2C login form.

    B2C's JS validation fires on each keystroke. Using .fill() dumps the whole
    value instantly before those handlers run — causing silent failures like
    "can't find your account" even with correct credentials.
    We type slowly (delay=80ms) so onChange/onInput fire per character.
    """
    email_field = _email_field(page)
    pwd_field   = _password_field(page)

    email_field.click()
    email_field.click(click_count=3)   # select all existing text
    email_field.type(email, delay=80)  # type slowly, firing JS handlers
    email_field.press("Tab")           # commit and move focus to password

    page.wait_for_timeout(500)         # let B2C JS validate the email

    pwd_field.click()
    pwd_field.click(click_count=3)
    pwd_field.type(password, delay=80)

    page.wait_for_timeout(500)         # let B2C JS validate the password

    _submit_button(page).click()


def _error_message(page: Page):
    """Find a visible B2C error message element, or return None."""
    candidates = [
        "#errorText",
        "#claimVerificationServerError",
        "[role='alert']",
        ".error",
        ".alert",
        "p.error",
        "div.error",
        "span.error",
    ]
    for selector in candidates:
        loc = page.locator(selector).first
        if loc.count() > 0 and loc.is_visible():
            return loc
    return None


def _visible_page_text(page: Page) -> str:
    """Return all visible leaf-node text on the page, pipe-separated."""
    return page.evaluate("""() =>
        Array.from(document.querySelectorAll('*'))
            .filter(el => el.children.length === 0 && el.offsetParent !== null)
            .map(el => el.innerText ? el.innerText.trim() : '')
            .filter(t => t.length > 0)
            .join(' | ')
    """)


# ─── Email field tests ────────────────────────────────────────────────────────

class TestEmailField:

    def test_valid_email_accepted(self, login_page: Page):
        """V · Well-formed email: field accepts it, checkValidity passes."""
        email = _email_field(login_page)
        email.fill(VALID_EMAIL)
        email.evaluate("el => el.blur()")
        assert email.evaluate("el => el.checkValidity()"), \
            "Expected email field to be valid"

    def test_email_missing_at_symbol(self, login_page: Page):
        """I · Email without '@': B2C rejects it after submit.

        Field is type=text so the browser won't catch this natively.
        B2C validates server-side and stays on the login page or shows an error.
        """
        email = _email_field(login_page)
        email.fill("userexample.com")
        email.evaluate("el => el.blur()")
        _submit_button(login_page).click()
        login_page.wait_for_load_state("networkidle", timeout=10_000)

        stayed      = "dw1qa.b2clogin.com" in login_page.url
        error_shown = _error_message(login_page) is not None
        assert stayed or error_shown, \
            "Expected B2C to reject a value missing '@'"

    def test_email_missing_domain(self, login_page: Page):
        """I · Email without domain part: field invalid."""
        email = _email_field(login_page)
        email.fill("user@")
        email.evaluate("el => el.blur()")
        assert not email.evaluate("el => el.checkValidity()"), \
            "Expected email field to be invalid (missing domain)"

    def test_email_empty_required(self, login_page: Page):
        """I · Required email left empty: native constraint or visible error."""
        email = _email_field(login_page)
        email.fill("")
        _submit_button(login_page).click()
        native_invalid = email.evaluate("el => el.validity.valueMissing || !el.checkValidity()")
        error_visible  = _error_message(login_page) is not None
        assert native_invalid or error_visible, \
            "Expected either a valueMissing constraint or a visible error message"

    def test_email_matches_pattern(self, login_page: Page):
        """V · Email matching the site's pattern regex: no error."""
        assert EMAIL_PATTERN.match(VALID_EMAIL), \
            f"Test value '{VALID_EMAIL}' should match the expected pattern"
        email = _email_field(login_page)
        email.fill(VALID_EMAIL)
        email.evaluate("el => el.blur()")
        assert email.evaluate("el => el.checkValidity()"), \
            "Expected email to satisfy the pattern constraint"

    def test_email_does_not_match_pattern(self, login_page: Page):
        """I · Value not matching the pattern: rejected by field or server."""
        bad_value = "notavalidemail"
        assert not EMAIL_PATTERN.match(bad_value)
        email = _email_field(login_page)
        email.fill(bad_value)
        email.evaluate("el => el.blur()")
        is_invalid = email.evaluate("el => !el.checkValidity()")
        if not is_invalid:
            _submit_button(login_page).click()
            login_page.wait_for_load_state("networkidle", timeout=10_000)
            assert _error_message(login_page) is not None, \
                "Expected a server-side error for a non-email value, but none appeared"

    def test_email_xss_injection(self, login_page: Page):
        """I · XSS payload in email field: stored as plain text, not executed."""
        email = _email_field(login_page)
        email.fill(XSS_PAYLOAD)
        email.evaluate("el => el.blur()")
        assert email.input_value() == XSS_PAYLOAD, \
            "XSS payload must be stored verbatim"
        assert login_page.locator("script:has-text('alert(1)')").count() == 0, \
            "XSS script must not be injected into the DOM"


# ─── Password field tests ─────────────────────────────────────────────────────

class TestPasswordField:

    def test_valid_password_accepted(self, login_page: Page):
        """V · Non-empty password: checkValidity passes."""
        pwd = _password_field(login_page)
        pwd.fill(VALID_PASSWORD)
        pwd.evaluate("el => el.blur()")
        assert pwd.evaluate("el => el.checkValidity()"), \
            "Expected password field to be valid"

    def test_password_empty_required(self, login_page: Page):
        """I · Required password left empty: native constraint or visible error."""
        pwd = _password_field(login_page)
        pwd.fill("")
        _submit_button(login_page).click()
        native_invalid = pwd.evaluate("el => el.validity.valueMissing || !el.checkValidity()")
        error_visible  = _error_message(login_page) is not None
        assert native_invalid or error_visible, \
            "Expected either a valueMissing constraint or a visible error message"

    def test_password_xss_injection(self, login_page: Page):
        """I · XSS payload in password field: stored as plain text, not executed."""
        pwd = _password_field(login_page)
        pwd.fill(XSS_PAYLOAD)
        pwd.evaluate("el => el.blur()")
        assert pwd.input_value() == XSS_PAYLOAD, \
            "XSS payload must be stored verbatim"
        assert login_page.locator("script:has-text('alert(1)')").count() == 0, \
            "XSS script must not be injected into the DOM"


# ─── Submit / Login tests ─────────────────────────────────────────────────────

class TestSubmitButton:

    def test_user_can_login_successfully(self, login_page: Page):
        """V · Valid credentials → redirected to wasteapplications.com."""
        _fill_and_submit(login_page, VALID_EMAIL, VALID_PASSWORD)

        # Wait up to 25s for the URL to change away from B2C.
        # We poll rather than using wait_for_url so we don't miss a fast redirect.
        import time
        deadline = time.time() + 25
        while time.time() < deadline:
            if "dw1qa.b2clogin.com" not in login_page.url:
                break
            login_page.wait_for_timeout(500)
        else:
            login_page.screenshot(path="debug_after_login.png")
            pytest.fail(
                f"Redirect away from B2C did not happen within 25s.\n"
                f"Current URL: {login_page.url}\n"
                f"Visible page text: {_visible_page_text(login_page)}\n"
                f"Screenshot saved to: debug_after_login.png"
            )

        # Page landed — wait for it to fully load
        login_page.wait_for_load_state("networkidle", timeout=15_000)
        login_page.screenshot(path="debug_after_login.png")

        assert "wasteapplications.com" in login_page.url, \
            f"Unexpected post-login URL: {login_page.url}"
        assert login_page.evaluate("() => document.readyState") == "complete", \
            "Post-login page did not finish loading"
        error = _error_message(login_page)
        assert error is None, \
            f"Error visible after successful login: '{error.inner_text() if error else ''}'"

    def test_invalid_credentials_show_error(self, login_page: Page):
        """I · Wrong password → stays on login page, error message shown."""
        _fill_and_submit(login_page, VALID_EMAIL, "WrongPassword_NotReal_999!")

        login_page.wait_for_timeout(3_000)
        login_page.screenshot(path="debug_after_bad_login.png")
        login_page.wait_for_load_state("networkidle", timeout=20_000)

        assert "dw1qa.b2clogin.com" in login_page.url, \
            "Page navigated away despite wrong credentials"

        error = _error_message(login_page)
        if error is None:
            pytest.fail(
                f"No error element found after wrong password.\n"
                f"Visible text: {_visible_page_text(login_page)}\n"
                f"Screenshot saved to: debug_after_bad_login.png\n\n"
                f"Add the correct CSS selector to _error_message() in login.py"
            )

    def test_submit_blocked_when_form_invalid(self, login_page: Page):
        """I · Submit clicked on empty form: blocked by browser or error shown."""
        _email_field(login_page).fill("")
        _password_field(login_page).fill("")
        _submit_button(login_page).click()
        login_page.wait_for_load_state("networkidle", timeout=10_000)

        stayed      = "dw1qa.b2clogin.com" in login_page.url
        error_shown = _error_message(login_page) is not None
        assert stayed or error_shown, \
            "Expected form submission to be blocked or an error to be shown"


# ─── Forgot Password link test ────────────────────────────────────────────────

class TestForgotPasswordLink:

    def test_forgot_password_link_reachable(self, login_page: Page):
        """V · 'Forgot Password?' link resolves with HTTP 200."""
        link = login_page.locator(
            'a[href*="CombinedSigninAnd"], a:has-text("Forgot"), a:has-text("forgot")'
        ).first
        href = link.get_attribute("href")
        assert href, "Expected a Forgot Password link to be present"
        if not href.startswith("http"):
            origin = login_page.evaluate("() => window.location.origin")
            href = origin + href
        response = login_page.request.get(href)
        assert response.status == 200, \
            f"Forgot Password link returned HTTP {response.status}, expected 200"


# ─── Image render tests ───────────────────────────────────────────────────────

class TestImages:

    def test_first_image_loads(self, login_page: Page):
        """V · First <img> renders without a broken-image icon."""
        img = login_page.locator("img").nth(0)
        expect(img).to_be_visible()
        assert img.evaluate("el => el.naturalWidth") > 0, \
            "First image has naturalWidth=0 (broken image)"

    def test_second_image_loads(self, login_page: Page):
        """V · Second <img> renders without a broken-image icon."""
        img = login_page.locator("img").nth(1)
        expect(img).to_be_visible()
        assert img.evaluate("el => el.naturalWidth") > 0, \
            "Second image has naturalWidth=0 (broken image)"
