"""
claude_validator.py
───────────────────
Reusable Claude AI validation module for Playwright test scripts.
"""

import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Any

import anthropic

# ─── Force-read .env directly — bypasses any cached environment variables ─────
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()

_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not _api_key:
    raise EnvironmentError(
        "\n\n❌ ANTHROPIC_API_KEY not found.\n"
        "Make sure your .env file in the project root contains:\n\n"
        "  ANTHROPIC_API_KEY=sk-ant-...\n"
    )


# ─── OC-5299 Acceptance Criteria ─────────────────────────────────────────────

OC_5299_AC = [
    (
        "OC-5299 AC1 [Address Search Mode]",
        "The Map View search bar supports Address as a selectable search mode",
        None
    ),
    (
        "OC-5299 AC2 [SmartyStreets Integration]",
        "When Address search mode is selected, user input is sent to SmartyStreets for address validation and suggestion",
        None
    ),
    (
        "OC-5299 AC3 [Autocomplete Dropdown]",
        "Address suggestions appear in a dropdown list beneath the search input as the user types",
        None
    ),
    (
        "OC-5299 AC4 [Address Format]",
        "Suggested addresses are formatted consistently (street, city, state, ZIP)",
        None
    ),
    (
        "OC-5299 AC5 [Map Centers on Address]",
        "Selecting an address from the results centers the map on the selected address",
        None
    ),
    (
        "OC-5299 AC6 [Valid Search Anchor]",
        "The selected address is treated as a valid search anchor even if it does not exist in Waste Apps data",
        None
    ),
    (
        "OC-5299 AC7 [Clear and Reset]",
        "The search input supports clearing the current address and resetting the map state",
        "DEFERRED"
    ),
    (
        "OC-5299 AC8 [No Results Message]",
        'If no valid address suggestions are returned, a clear "No results found" message is displayed',
        "DEFERRED"
    ),
    (
        "OC-5299 AC9 [Recent Searches]",
        "The selected address is saved to Recent Searches with its associated display and filter context",
        "DEFERRED"
    ),
]


# ─── Result Object ────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    test_name: str
    passed: bool
    summary: str
    issues: list[str]
    full_response: str
    screenshot_path: Optional[str] = None
    duration_ms: int = 0
    tickets: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)

    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        lines = [
            f"{status} — {self.test_name}",
            f"  Summary: {self.summary}",
        ]
        if self.tickets:
            lines.append("  Tickets:")
            for ticket in self.tickets:
                lines.append(f"    {ticket}")
        if self.issues:
            lines.append("  Issues:")
            for issue in self.issues:
                lines.append(f"    • {issue}")
        if self.screenshot_path:
            lines.append(f"  Screenshot: {self.screenshot_path}")
        lines.append(f"  Duration: {self.duration_ms}ms")
        return "\n".join(lines)


# ─── Claude Validator ─────────────────────────────────────────────────────────

class ClaudeValidator:

    def __init__(
        self,
        model: str = "claude-opus-4-6",
        max_tokens: int = 1024,
        screenshot_dir: str = "screenshots",
        verbose: bool = True,
        system_prompt: str = None
    ):
        self.client = anthropic.Anthropic(api_key=_api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.screenshot_dir = screenshot_dir
        self.verbose = verbose
        self.system_prompt = system_prompt
        self.results: list[ValidationResult] = []

        os.makedirs(self.screenshot_dir, exist_ok=True)

    # ── Core internal call ────────────────────────────────────────────────────

    def _ask_claude(
        self,
        prompt: str,
        screenshot_path: Optional[str] = None
    ) -> str:
        if screenshot_path and os.path.exists(screenshot_path):
            with open(screenshot_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data,
                    },
                },
                {"type": "text", "text": prompt}
            ]
        else:
            content = prompt

        create_kwargs = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": content}]
        )
        if self.system_prompt:
            create_kwargs["system"] = self.system_prompt

        response = self.client.messages.create(**create_kwargs)
        return response.content[0].text

    # ── Prompt builder ────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        test_name: str,
        expected: dict,
        context: Optional[str] = None
    ) -> str:
        expected_lines = "\n".join(f"  - {k}: {v}" for k, v in expected.items())
        context_section = f"\nAdditional context:\n{context}\n" if context else ""

        return f"""You are a QA validator for Waste Applications, a waste management platform.
Analyze the provided information and validate the test: {test_name}
{context_section}
Expected values to check:
{expected_lines}

Respond in EXACTLY this format — do not deviate:

RESULT: PASS
or
RESULT: FAIL

SUMMARY: [One sentence describing what you found]

CHECKS:
- [expected item]: [PASS/FAIL] — [what you actually observed]
- [expected item]: [PASS/FAIL] — [what you actually observed]

ISSUES:
- [describe each problem found, or write "None" if no issues]

TICKETS VALIDATED:
- [OC-XXXX]: PASSES — [one line reason]
- [OC-XXXX]: FAILS — [one line reason]
- [OC-XXXX]: PARTIAL — [one line reason]
"""

    # ── Parse Claude response ─────────────────────────────────────────────────

    def _parse_response(
        self,
        test_name: str,
        response: str,
        screenshot_path: Optional[str],
        duration_ms: int
    ) -> ValidationResult:
        lines = response.strip().split("\n")

        passed = any("RESULT: PASS" in line.upper() for line in lines)

        summary = "No summary provided"
        for line in lines:
            if line.upper().startswith("SUMMARY:"):
                summary = line.split(":", 1)[1].strip()
                break

        checks = {}
        in_checks = False
        for line in lines:
            if line.upper().startswith("CHECKS:"):
                in_checks = True
                continue
            if in_checks and line.strip().startswith("-"):
                body = line.strip().lstrip("- ").strip()
                if ":" in body:
                    key_part, rest = body.split(":", 1)
                    key = key_part.strip()
                    rest = rest.strip()
                    if " — " in rest:
                        status, observation = rest.split(" — ", 1)
                    elif " - " in rest:
                        status, observation = rest.split(" - ", 1)
                    else:
                        status, observation = rest, ""
                    checks[key] = (status.strip(), observation.strip())
            elif in_checks and line.strip() and not line.strip().startswith("-"):
                in_checks = False

        issues = []
        in_issues = False
        for line in lines:
            if line.upper().startswith("ISSUES:"):
                in_issues = True
                continue
            if in_issues and line.strip().startswith("-"):
                issue = line.strip().lstrip("- ").strip()
                if issue.lower() != "none":
                    issues.append(issue)
            elif in_issues and line.strip() and not line.strip().startswith("-"):
                in_issues = False

        tickets = []
        in_tickets = False
        for line in lines:
            if line.upper().startswith("TICKETS VALIDATED"):
                in_tickets = True
                continue
            if in_tickets and line.strip().startswith("-"):
                ticket_line = line.strip().lstrip("- ").strip()
                if ticket_line:
                    if "PASSES" in ticket_line.upper():
                        tickets.append(f"✅ {ticket_line}")
                    elif "FAILS" in ticket_line.upper():
                        tickets.append(f"❌ {ticket_line}")
                    elif "N/A" in ticket_line.upper():
                        tickets.append(f"⚪ {ticket_line}")
                    else:
                        tickets.append(f"⚠️  {ticket_line}")
            elif in_tickets and line.strip() and not line.strip().startswith("-"):
                in_tickets = False

        return ValidationResult(
            test_name=test_name,
            passed=passed,
            summary=summary,
            issues=issues,
            tickets=tickets,
            checks=checks,
            full_response=response,
            screenshot_path=screenshot_path,
            duration_ms=duration_ms
        )

    # ── OC-5299 structured AC report block ───────────────────────────────────

    def _print_oc5299_report(self, result: ValidationResult):
        print("\n" + "─" * 60)
        print("  OC-5299 — MAP Search By Address: Acceptance Criteria")
        print("─" * 60)

        checks = result.checks

        for idx, (ac_key, ac_label, override) in enumerate(OC_5299_AC, start=1):
            print(f"\n{idx}  {ac_label}")

            if override == "DEFERRED":
                print("   🔜 Deferred — to be validated in separate script")
                continue

            status, observation = checks.get(ac_key, (None, None))
            if status is None:
                for k, (s, o) in checks.items():
                    if ac_key.lower() in k.lower() or k.lower() in ac_key.lower():
                        status, observation = s, o
                        break

            if status and "PASS" in status.upper():
                icon = "✅ Pass"
            elif status and "FAIL" in status.upper():
                icon = "❌ Fail"
            else:
                icon = "⚠️  Unable to determine"

            obs_text = observation if observation else "see screenshot"
            print(f"   {icon} — {obs_text}")

        print("\n" + "─" * 60)

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC METHODS
    # ─────────────────────────────────────────────────────────────────────────

    def validate(
        self,
        test_name: str,
        expected: dict,
        screenshot_path: Optional[str] = None,
        context: Optional[str] = None
    ) -> ValidationResult:
        if self.verbose:
            print(f"\n🤖 Validating map parameters...")

        start = time.time()
        prompt = self._build_prompt(test_name, expected, context)
        response = self._ask_claude(prompt, screenshot_path)
        duration_ms = int((time.time() - start) * 1000)

        result = self._parse_response(test_name, response, screenshot_path, duration_ms)
        self.results.append(result)

        if self.verbose:
            print(result)

        return result

    def validate_page(
        self,
        page,
        test_name: str,
        expected: dict,
        context: Optional[str] = None,
        screenshot_name: Optional[str] = None
    ) -> ValidationResult:
        if not screenshot_name:
            safe_name = test_name.lower().replace(" ", "_").replace("/", "_")[:50]
            screenshot_name = f"{safe_name}_{int(time.time())}.png"

        screenshot_path = os.path.join(self.screenshot_dir, screenshot_name)
        page.screenshot(path=screenshot_path)

        if self.verbose:
            print(f"  📸 Screenshot saved: {screenshot_path}")

        return self.validate(
            test_name=test_name,
            expected=expected,
            screenshot_path=screenshot_path,
            context=context
        )

    def validate_text(
        self,
        test_name: str,
        actual_data: Any,
        expected: dict,
        context: Optional[str] = None
    ) -> ValidationResult:
        actual_str = json.dumps(actual_data, indent=2) if isinstance(actual_data, (dict, list)) else str(actual_data)
        full_context = f"Actual data returned:\n{actual_str}"
        if context:
            full_context += f"\n\n{context}"

        return self.validate(
            test_name=test_name,
            expected=expected,
            screenshot_path=None,
            context=full_context
        )

    def validate_map_search(
        self,
        page,
        test_name: str,
        expected_customers: int = 0,
        expected_jobsites: int = 0,
        expected_vendors: int = 0,
        exact_match: bool = False,
        extra_checks: Optional[dict] = None
    ) -> ValidationResult:
        match_type = "exactly" if exact_match else "at least"

        expected = {
            "customers_count": f"{match_type} {expected_customers} customers shown",
            "jobsites_count":  f"{match_type} {expected_jobsites} jobsites shown",
            "vendors_count":   f"{match_type} {expected_vendors} vendors shown",
        }

        if extra_checks:
            expected.update(extra_checks)

        return self.validate_page(
            page=page,
            test_name=test_name,
            expected=expected,
            context="This is a Waste Applications map search result page. Check the results panel on the left and the counter in the top right of the map."
        )

    # ─── Reporting ────────────────────────────────────────────────────────────

    def report(self) -> dict:
        passed = [r for r in self.results if r.passed]
        failed = [r for r in self.results if not r.passed]

        print("\n" + "=" * 60)
        print("  CLAUDE AI VALIDATION REPORT")
        print("=" * 60)
        print(f"  Total:   {len(self.results)}")
        print(f"  ✅ Pass: {len(passed)}")
        print(f"  ❌ Fail: {len(failed)}")
        print("-" * 60)

        for result in self.results:
            print(f"\n{'✅' if result.passed else '❌'} {result.test_name}")
            print(f"   {result.summary}")
            if result.tickets:
                for ticket in result.tickets:
                    print(f"   {ticket}")
            for issue in result.issues:
                print(f"   ⚠️  {issue}")

            if "Address Search" in result.test_name:
                self._print_oc5299_report(result)

        print("\n" + "=" * 60)

        return {
            "total":   len(self.results),
            "passed":  len(passed),
            "failed":  len(failed),
            "results": self.results
        }

    def reset(self):
        """Clear all stored results."""
        self.results = []