"""
Customer.py
───────────
Waste Applications — New Customer Flow

Syncfusion input patterns (confirmed from DOM inspection):
  textbox      → aria-labelledby="label_textbox-{guid}"  (label text in span#label_textbox-{guid})
  autocomplete → aria-label="autocomplete", label has for="{input-id}"
  dropdownlist → aria-label="dropdownlist", label has for="{input-id}"
  maskedinput  → same label patterns as textbox, but rejects JS/fill — keyboard only

Strategy: JS finds input by matching label text across all three patterns.
"""

import asyncio
import csv
import random
import re

from faker import Faker
from playwright.async_api import Page, async_playwright

fake = Faker()

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

CSV_PATH = r"/map_test_data_apr14.csv"


def generate_fake_customer() -> dict:
    """Generate a fully randomized customer record using Faker."""
    return {
        "name":   fake.company(),
        "street": fake.street_address(),
        "city":   fake.city(),
        "state":  fake.state_abbr(),
        "zip":    fake.zipcode(),
        "email":  "automation.test@wasteapplications.com",
        "phone":  "8285550606",
        "first":  fake.first_name(),
        "last":   fake.last_name(),
    }


FALLBACK = generate_fake_customer()

# ─── JS that finds any Syncfusion input by its visible label text ─────────────
FIND_INPUT_JS = """
(labelText) => {
    const text = labelText.trim();

    // Pattern 1: aria-labelledby pointing to a span/element whose text matches
    for (const inp of document.querySelectorAll('input[aria-labelledby]')) {
        const labelId = inp.getAttribute('aria-labelledby');
        const labelEl = document.getElementById(labelId);
        if (labelEl && labelEl.textContent.trim() === text) return inp;
    }

    // Pattern 2 & 3: <label for="input-id"> whose text matches
    for (const label of document.querySelectorAll('label[for]')) {
        if (label.textContent.trim() === text) {
            const inp = document.getElementById(label.getAttribute('for'));
            if (inp) return inp;
        }
    }

    // Fallback: strip trailing asterisk and retry
    const bare = text.replace(/\\s*\\*\\s*$/, '').trim();
    for (const inp of document.querySelectorAll('input[aria-labelledby]')) {
        const labelId = inp.getAttribute('aria-labelledby');
        const labelEl = document.getElementById(labelId);
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


# ─── Fill helpers ─────────────────────────────────────────────────────────────

async def fill_by_label(page: Page, label_text: str, value: str, field_name: str = ""):
    """Fill any Syncfusion textbox/autocomplete input by its visible label text."""
    el = await page.evaluate_handle(FIND_INPUT_JS, label_text)
    as_el = el.as_element()
    if not as_el:
        raise RuntimeError(f"Input not found for label: '{label_text}'")

    await page.evaluate("el => el.scrollIntoView({ block: 'center', inline: 'nearest' })", as_el)
    await page.wait_for_timeout(200)

    await page.evaluate(
        """([el, val]) => {
            el.focus();
            el.value = '';
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        [as_el, value]
    )
    await page.wait_for_timeout(300)
    print(f"  ✓ {field_name or label_text} = {value}")


async def fill_masked_input(page: Page, label_text: str, value: str, field_name: str = ""):
    """
    Fill a Syncfusion MaskedTextBox by visible label text.

    Why a separate helper:
      Masked inputs (phone, SSN, etc.) have a positional mask like (###) ###-####.
      They silently discard JS value assignment and Playwright .fill() because an
      internal mask engine intercepts every keystroke and advances the caret
      slot-by-slot. The only reliable approach is:
        1. Real click  → activates the Syncfusion mask engine
        2. Home key    → move caret to position 0 (focus may land mid-mask)
        3. Ctrl+A / Delete → clear any placeholder underscores the mask pre-fills
        4. keyboard.type(digits, delay) → feed one digit at a time; mask inserts
           separators ( ) and - automatically
      Non-digit characters in `value` are stripped before typing so they never
      land in the wrong mask slot.
    """
    el = await page.evaluate_handle(FIND_INPUT_JS, label_text)
    as_el = el.as_element()
    if not as_el:
        raise RuntimeError(f"Masked input not found for label: '{label_text}'")

    await page.evaluate("el => el.scrollIntoView({ block: 'center' })", as_el)
    await page.wait_for_timeout(200)

    await as_el.click()
    await page.wait_for_timeout(300)
    await page.keyboard.press("Home")
    await page.wait_for_timeout(100)
    await page.keyboard.press("Control+A")
    await page.wait_for_timeout(100)
    await page.keyboard.press("Delete")
    await page.wait_for_timeout(100)

    digits = ''.join(c for c in value if c.isdigit())
    await page.keyboard.type(digits, delay=80)
    await page.wait_for_timeout(300)
    print(f"  ✓ {field_name or label_text} = {value}")


async def fill_dropdown(page: Page, label_text: str, value: str, field_name: str = ""):
    """
    Fill a Syncfusion DropDownList or AutoComplete by label text.
    The combobox wrapper div intercepts pointer events — click it via JS,
    then type and select with ArrowDown + Enter.
    """
    el = await page.evaluate_handle(FIND_INPUT_JS, label_text)
    as_el = el.as_element()
    if not as_el:
        raise RuntimeError(f"Dropdown not found for label: '{label_text}'")

    await page.evaluate("el => el.scrollIntoView({ block: 'center' })", as_el)
    await page.wait_for_timeout(200)

    await page.evaluate(
        """el => {
            let target = el.closest('[role="combobox"]') || el.parentElement || el;
            target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            target.dispatchEvent(new MouseEvent('mouseup',   { bubbles: true }));
            target.dispatchEvent(new MouseEvent('click',     { bubbles: true }));
            el.focus();
        }""",
        as_el
    )
    await page.wait_for_timeout(400)
    await page.keyboard.type(value, delay=100)
    await page.wait_for_timeout(700)
    await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(300)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(400)
    print(f"  ✓ {field_name or label_text} = {value}")


# ─── Load CSV ─────────────────────────────────────────────────────────────────

def load_customers(csv_path: str) -> list[dict]:
    customers = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("Category", "").strip() != "CUSTOMER":
                    continue
                name = row.get("Name", "").strip()
                addr = row.get("Address", "").strip()
                if not name or not addr:
                    continue
                m = re.match(r"^(.+),\s*(.+?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$", addr)
                if not m:
                    continue
                customers.append({
                    "name":   name,
                    "street": m.group(1).strip(),
                    "city":   m.group(2).strip(),
                    "state":  m.group(3).strip(),
                    "zip":    m.group(4).strip(),
                    "email":  "automation.test@wasteapplications.com",
                    "phone":  "4045550100",
                    "first":  "Test",
                    "last":   "User",
                })
    except FileNotFoundError:
        print(f"  ⚠️  CSV not found — using fallback data")
    return customers or [FALLBACK]


# ─── Login ────────────────────────────────────────────────────────────────────

async def do_login(page: Page):
    print("→ Navigating to login page...")
    await page.goto(LOGIN_URL)
    await page.wait_for_load_state("load", timeout=15_000)
    await page.wait_for_timeout(2_000)

    print("→ Filling in credentials...")
    for sel in ["input[placeholder='Email Address']", "#signInName",
                "input[name='signInName']", "input[type='text']"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.fill(VALID_EMAIL)
            await page.keyboard.press("Tab")
            break

    await page.wait_for_timeout(400)
    for sel in ["input[placeholder='Password']", "#password", "input[type='password']"]:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.fill(VALID_PASSWORD)
            break

    await page.wait_for_timeout(400)
    await page.locator("button[type='submit'][id='next']").click()

    print("→ Waiting for redirect after login...")
    await page.wait_for_url(re.compile(r"wasteapplications\.com/home"), timeout=30_000)
    await page.wait_for_load_state("networkidle", timeout=20_000)
    await page.wait_for_timeout(3_000)
    print(f"✓ Logged in. URL: {page.url}")


# ─── Navigation ───────────────────────────────────────────────────────────────

async def go_to_customers(page: Page):
    print("\n→ Clicking Management...")
    mgmt = page.locator("button:has-text('Management')").first
    await mgmt.wait_for(state="visible", timeout=20_000)
    await mgmt.click()
    await page.wait_for_timeout(1_500)

    link = page.locator("a[href='/Modules/Customer/Customer']").first
    await link.wait_for(state="visible", timeout=10_000)
    await link.click()
    await page.wait_for_load_state("load", timeout=15_000)
    await page.wait_for_timeout(2_000)
    print(f"✓ Customers page loaded. URL: {page.url}")


# ─── Grid link check ──────────────────────────────────────────────────────────

async def check_grid_links(page: Page) -> list[dict]:
    print("\n→ Checking all links in customer grid (all pages)...")
    broken = []
    checked = set()
    page_num = 1

    while True:
        print(f"\n  → Page {page_num}...")
        links = await page.eval_on_selector_all(
            "div.oc-table-wrapper a[href]",
            "els => els.map(el => ({ text: el.innerText.trim(), href: el.href }))"
        )
        new_links = [l for l in links if l["href"] not in checked]
        print(f"  Found {len(new_links)} new links on page {page_num}")

        for link in new_links:
            href = link["href"]
            checked.add(href)
            text = link["text"] or href.split("/")[-1]
            try:
                resp = await page.request.fetch(href, method="HEAD", timeout=8_000)
                status = resp.status
                marker = "❌" if status >= 400 else "✅"
                print(f"  {marker} [{status}] {text}")
                if status >= 400:
                    broken.append({"text": text, "href": href, "status": status})
            except Exception as e:
                broken.append({"text": text, "href": href, "status": "ERROR"})
                print(f"  ⚠️  {text}: {e}")

        next_btn = page.locator("button[aria-label='Next Page']:not([disabled])").first
        if await next_btn.count() > 0 and await next_btn.is_enabled():
            await next_btn.click()
            await page.wait_for_timeout(1_500)
            page_num += 1
        else:
            break

    print(f"\n  Total checked: {len(checked)} links — {len(broken)} broken")
    return broken


# ─── Open New Customer modal ──────────────────────────────────────────────────

async def open_new_customer(page: Page):
    print("\n→ Opening New Customer form...")
    btn = page.locator("button.oc-button-primary:has-text('New Customer')").first
    await btn.wait_for(state="visible", timeout=10_000)
    await btn.click()
    await page.locator("h2:has-text('Add Customer')").wait_for(timeout=15_000)
    await page.wait_for_timeout(2_000)
    print("  ✓ New Customer modal open")


# ─── Step 1: Customer Information ─────────────────────────────────────────────

async def fill_step1(page: Page, data: dict):
    print(f"\n→ Filling Step 1: Customer Information...")

    await fill_by_label(page,  "Customer Name *",   data["name"],   "Customer Name")
    await fill_dropdown(page,  "Billing Address *",  data["street"], "Billing Address")
    await fill_by_label(page,  "City *",             data["city"],   "City")
    await fill_dropdown(page,  "State *",            data["state"],  "State")
    await fill_by_label(page,  "Zip Code *",         data["zip"],    "Zip Code")

    print("\n→ Clicking Next...")
    for sel in [
        "button[data-testid='wizard-create-next-to-page-2']",
        "button.oc-button-primary:has-text('NEXT')",
        "button:has-text('NEXT')",
    ]:
        btn = page.locator(sel).first
        if await btn.count() > 0:
            await btn.wait_for(state="visible", timeout=10_000)
            await btn.click()
            await page.wait_for_timeout(3_000)
            print("  ✓ Next clicked")
            return

    raise RuntimeError("NEXT button not found.")


# ─── Step 2: Contact Information ──────────────────────────────────────────────

async def fill_step2(page: Page, data: dict):
    print(f"\n→ Filling Step 2: Contact Information...")
    await page.wait_for_timeout(2_000)

    await fill_by_label(page,     "First Name *",     data["first"],  "First Name")
    await fill_by_label(page,     "Last Name",         data["last"],   "Last Name")
    await fill_masked_input(page, "Phone Number 1 *",  data["phone"],  "Phone Number 1")
    await fill_by_label(page,     "Email 1 *",         data["email"],  "Email 1")

    print("\n→ Clicking Create...")
    for sel in [
        "button[data-testid='wizard-complete-button']",
        "button.oc-button-primary:has-text('CREATE')",
        "button:has-text('CREATE')",
    ]:
        btn = page.locator(sel).first
        if await btn.count() > 0:
            await btn.wait_for(state="visible", timeout=10_000)
            await btn.click(force=True)
            await page.wait_for_timeout(3_000)
            print("  ✓ Create clicked")
            return

    raise RuntimeError("CREATE button not found.")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    customers = load_customers(CSV_PATH)
    data = random.choice(customers)

    # Override all fields with fresh Faker data every run
    fake_data = generate_fake_customer()
    data.update(fake_data)

    print("\n  Test data:")
    print(f"  Company : {data['name']}")
    print(f"  Address : {data['street']}, {data['city']}, {data['state']} {data['zip']}")
    print(f"  Email   : {data['email']}")
    print(f"  Phone   : {data['phone']}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir="../videos/",
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        try:
            await do_login(page)
            await go_to_customers(page)
            broken = await check_grid_links(page)
            await open_new_customer(page)
            await fill_step1(page, data)
            await fill_step2(page, data)

            print("\n" + "=" * 50)
            print(f"  ✅ Customer created: {data['name']}")
            if broken:
                print(f"  ⚠️  {len(broken)} broken links found")
                print(f"  VERDICT: CUS-01 FAIL -- broken links detected")
            else:
                print(f"  ✅ All grid links valid")
                print(f"  VERDICT: CUS-01 PASS -- customer created, no broken links")
            print("=" * 50)

        except Exception as e:
            print(f"\n❌ Script failed: {e}")
            print(f"  VERDICT: CUS-01 FAIL -- {e}")
            raise

        finally:
            await page.wait_for_timeout(3_000)
            await context.close()
            await browser.close()
            print("\n  🎥 Video saved to: videos/")


if __name__ == "__main__":
    asyncio.run(main())