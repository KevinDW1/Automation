"""
qa_context.py
─────────────
Full QA session knowledge base for Waste Applications Map testing.
Built from Sprint 7 QA testing session — April 14/15, 2026.

This module provides a rich system prompt that gives Claude the same
context a QA engineer has after a full day of manual testing.
Pass QA_SYSTEM_PROMPT to ClaudeValidator so every validation call
is grounded in real Jira tickets, acceptance criteria, known test data,
and observed production behavior.

Usage:
    from qa_context import QA_SYSTEM_PROMPT, get_ticket_context
    from claude_validator import ClaudeValidator

    validator = ClaudeValidator(system_prompt=QA_SYSTEM_PROMPT)

    # Or get context for a specific ticket
    result = validator.validate_page(
        page=page,
        test_name="OC-5304 Display Filter",
        expected={...},
        context=get_ticket_context("OC-5304")
    )
"""

# ─── JIRA TICKETS & ACCEPTANCE CRITERIA ──────────────────────────────────────

TICKETS = {

    "OC-5304": {
        "summary": "MAP Search Display option",
        "status": "Awaiting Next Release",
        "assignee": "Unassigned",
        "type": "Story",
        "description": "Enable users to change the map display context to view Customers, Jobsites, Vendors, or All entities. Default is All Selected.",
        "acceptance_criteria": [
            "Display filter control shows 4 options: All, Customers, Jobsites, Vendors",
            "Default display selection is All Selected",
            "Changing display selection updates visible map pins",
            "Changing display selection updates results shown in left panel",
            "Selecting Customers shows only customer pins and results",
            "Selecting Jobsites shows only jobsite pins and results",
            "Selecting Vendors shows only vendor pins and results",
            "Display filter does NOT alter search anchor, radius, or other filters",
            "Display selection persists when adjusting radius or refining filters",
            "Clearing search resets display selection to All",
            "Selected display option is saved with Recent Searches",
        ],
        "test_notes": [
            "VALIDATED in production — All Selected default confirmed",
            "Customers only: 310C/0J/0V confirmed with address 123 Howell Chase Peachtree Corners GA",
            "Display dropdown shows '1 Selected' when filtering",
            "Requires clicking Apply after changing Display — does not auto-apply",
            "Display going blank with nothing selected = expected behavior (0 results is correct)",
        ],
        "known_pass": True,
    },

    "OC-5390": {
        "summary": "MAP Dark Mode",
        "status": "Awaiting Next Release",
        "assignee": "Chris Rowe",
        "type": "Story",
        "description": "When user switches to dark mode, apply dark theme to the map.",
        "acceptance_criteria": [
            "Map supports dark mode visual theme via Night button at bottom of map",
            "Night mode renders map background, roads, geographic features in dark palette",
            "All pin types remain clearly visible in dark mode",
            "Entity pins maintain visual distinction from each other in dark mode",
            "Detail cards, tooltips, map controls render in dark mode styling",
            "Switching light/dark mode updates map WITHOUT page refresh",
            "Dark mode does not affect map functionality or data accuracy",
            "Map defaults to user's saved/last theme",
        ],
        "test_notes": [
            "Dark mode toggle is the NIGHT button at bottom of map — NOT a global app setting",
            "Other map modes: Gray, Satellite, Road, Night, Hybrid",
            "Validated in production — Night button works correctly",
            "All pin types visible on Hybrid/satellite background",
        ],
        "known_pass": True,
    },

    "OC-5705": {
        "summary": "MAP - Clear Button should not clear Search, only Filters",
        "status": "Awaiting Next Release",
        "assignee": "Josh Fuqua",
        "type": "Bug",
        "description": "Clear button was wiping the search field. It should only clear filters.",
        "acceptance_criteria": [
            "Clicking Clear removes all filter selections (More Filters, Display, etc.)",
            "Clicking Clear does NOT clear the search address field",
            "Clicking Clear does NOT remove the search anchor pin from the map",
            "Map results remain showing after Clear — only filters reset",
            "Display resets to All Selected after Clear",
        ],
        "test_notes": [
            "Previously Clear was wiping everything including the search",
            "Fix confirmed in Awaiting Next Release status",
        ],
        "known_pass": True,
    },

    "OC-5714": {
        "summary": "MAP Search Mode - Clear previous search when toggling",
        "status": "Awaiting Next Release",
        "assignee": "Chris Rowe",
        "type": "Bug",
        "description": "Switching between Local and Nationwide should clear the previous search.",
        "acceptance_criteria": [
            "Switching from Local to Nationwide clears the previous Local search",
            "Switching from Nationwide to Local clears the previous Nationwide search",
            "Map resets cleanly when toggling search modes",
        ],
        "test_notes": [
            "Fix confirmed in Awaiting Next Release",
        ],
        "known_pass": True,
    },

    "OC-5744": {
        "summary": "MAP - Search Field Behavior Adjustment",
        "status": "Awaiting Next Release",
        "assignee": "Josh Fuqua",
        "type": "Story",
        "description": "Search field behavior adjustment for improved UX.",
        "acceptance_criteria": [
            "Search field behaves consistently across all search modes",
            "Field clears appropriately when switching search types",
        ],
        "test_notes": [
            "Fix confirmed in Awaiting Next Release",
        ],
        "known_pass": True,
    },

    "OC-5755": {
        "summary": "MAP - City, State Search Results not centered on map",
        "status": "Ready for Development",
        "assignee": "Chris Rowe (Mrin will check)",
        "type": "Bug",
        "description": "City/State search doesn't center the map on the searched city.",
        "acceptance_criteria": [
            "Searching 'Chicago IL' centers map on Chicago",
            "Searched For card shows correct city searched",
            "Map navigates to correct geographic location",
        ],
        "test_notes": [
            "CONFIRMED BUG in production — searching 'Chicago IL' showed 'Tallahasse FL' in Searched For card",
            "Map stayed on previous location (Peachtree Corners GA) instead of navigating to Chicago",
            "Chicago DOES have data — 112 results confirmed via Name/ID search for vendor 3957",
            "Bug is in geocoding/location lookup, not in the data",
            "Status: Ready for Development — NOT yet fixed",
        ],
        "known_pass": False,
    },

    "OC-5761": {
        "summary": "MAP - Yard Cards - Showing Contacts Behavior",
        "status": "Ready for Development",
        "assignee": "Unassigned",
        "type": "Story",
        "description": "Define behavior for showing contacts on Yard Cards.",
        "acceptance_criteria": [
            "Yard cards show correct contact information",
            "Vendor Contact pill appears when no yard-specific contact exists",
        ],
        "test_notes": [
            "Status: Ready for Development — NOT yet implemented",
            "OC-5764 Scenario 3 validated: JFL Environmental shows Vendor Contact pill (Jeff Lipscomb) when no yard contacts",
        ],
        "known_pass": False,
    },

    "OC-5783": {
        "summary": "New 'No Partnership' status missing from 'More Filters => Customer Filter'",
        "status": "Awaiting PR Review",
        "assignee": "Chris Rowe",
        "type": "Bug",
        "description": "Customer Filter in More Filters was missing No Partnership Customers option.",
        "acceptance_criteria": [
            "Customer Filter shows exactly 6 options: Active, Inactive, At Risk, Out of Business, Terminated Partnership, No Partnership Customers",
            "Selecting No Partnership Customers only shows grey-pinned customers",
            "No Partnership works in combination with other statuses",
            "Deselecting No Partnership removes those pins",
            "Pins match No Partnership pin style shown in legend",
            "Filter persists on new search",
            "All 6 can be selected simultaneously",
            "Clear resets to default",
        ],
        "test_notes": [
            "Status: Awaiting PR Review — NOT yet testable",
            "Known No Partnership customers: Bojangles of WNC LLC (16119), Climate Pros, DF Floor Covering, S.M. Wilson & Co, Southern State Services",
            "No Partnership pin = grey/neutral color",
        ],
        "known_pass": False,
    },

    "OC-5791": {
        "summary": "Search shows 'No results found' before API response completes",
        "status": "Ready for QA",
        "assignee": "Chris Rowe",
        "type": "Bug",
        "description": "The 'No results found' message flashes before the API has finished returning results.",
        "acceptance_criteria": [
            "No results message should NOT appear while API is still loading",
            "Loading state should be shown while waiting for API response",
            "Results panel should only show 'Nothing to display' after API confirms 0 results",
        ],
        "test_notes": [
            "Status: Ready for QA — needs testing",
            "Look for brief flash of 'Nothing to display' immediately after Apply before results load",
        ],
        "known_pass": False,
    },

    "OC-5796": {
        "summary": "Map Nationwide Search Zoom Level",
        "status": "Ready for QA",
        "assignee": "Chris Rowe",
        "type": "Bug",
        "description": "Nationwide search should zoom to show entire continental US.",
        "acceptance_criteria": [
            "Nationwide search zooms map to show entire continental United States coast to coast",
            "Map should NOT be zoomed to street level after Nationwide search",
            "Zoom level is consistent regardless of which customer/vendor is searched",
            "Camera position is hardcoded to US-level zoom for any Nationwide search",
        ],
        "test_notes": [
            "CONFIRMED BROKEN in both QA and production",
            "Map stays zoomed to street level (shows individual buildings/streets) after Nationwide search",
            "PR is merged but fix not yet deployed to QA environment",
            "Status: Ready for QA",
        ],
        "known_pass": False,
    },

    "OC-5800": {
        "summary": "Jobsite Landing Page Vendor column not showing Vendor IDs",
        "status": "Ready for QA",
        "assignee": "Unassigned",
        "type": "Bug",
        "description": "On the Jobsite Landing Page, the Vendors column is not showing Vendor IDs.",
        "acceptance_criteria": [
            "Vendors column on Jobsite Landing Page shows Vendor ID for each jobsite with a vendor",
            "Jobsites with no vendor show blank or appropriate empty state in Vendors column",
            "Vendor ID shown matches the vendor assigned on the jobsite detail page",
        ],
        "test_notes": [
            "Status: Ready for QA — needs testing",
            "Test via Management → Jobsites landing page grid",
        ],
        "known_pass": False,
    },
}

# ─── KNOWN TEST DATA ──────────────────────────────────────────────────────────

TEST_DATA = {
    "addresses": {
        "peachtree_corners": {
            "address": "123 Howell Chase, Peachtree Corners, GA 30096",
            "expected_customers": 310,
            "expected_jobsites": 243,
            "expected_vendors": 89,
            "expected_total": 642,
            "lat": 33.9659,
            "lng": -84.2219,
            "notes": "Primary production regression address. With Show Secondary Locations ON = 651 results.",
        },
        "jefferson_ga": {
            "address": "34.1371, -83.6007",
            "search_by": "Latitude/Longitude",
            "expected_customers": 60,
            "expected_jobsites": 44,
            "expected_vendors": 22,
            "expected_total": 126,
            "notes": "Jefferson GA lat/long. Warren Construction is 0mi away.",
        },
        "nashville_tn": {
            "address": "36.15828, -86.783502",
            "search_by": "Latitude/Longitude",
            "expected_customers": 16,
            "expected_jobsites": 36,
            "expected_vendors": 60,
            "expected_total": 112,
            "notes": "Nashville TN lat/long. Used for OC-5304 display filter testing.",
        },
    },

    "customers": {
        "10420": {
            "name": "Global Retail Partners LLC",
            "address": "71 Adventure Trl, Jefferson GA 30549",
            "partnership_status": "Active",
            "pin_color": "Green",
            "pill_color": "Green",
        },
        "10295": {
            "name": "Pedal Valves INC",
            "address": "258 Marlowe Dr, Mills River NC 28759",
            "partnership_status": "Active",
            "pin_color": "Green",
            "pill_color": "Green",
        },
        "14534": {
            "name": "United Rentals - Branch K46",
            "address": "3700 Victory Drive, Columbus GA 31903",
            "partnership_status": "Active",
            "pin_color": "Green",
            "pill_color": "Green",
        },
        "16119": {
            "name": "Bojangles of WNC LLC",
            "address": "131 Glenn Bridge Rd, Arden NC 28704",
            "partnership_status": "No Partnership",
            "pin_color": "Grey/Neutral",
            "pill_color": "Grey",
            "jobsite_count": 16,
            "notes": "Key No Partnership test customer. 16 jobsites nationwide.",
        },
        "15823": {
            "name": "Warren Construction Services LLC",
            "address": "71 Adventure Trl, Jefferson GA 30549",
            "partnership_status": "Active",
            "jobsites": ["15823-11 The Bagel Hole", "15823-12 Firehouse Subs", "15823-13 Paris Baguette"],
            "jobsite_count": 3,
            "am": "Lath Guyer",
            "revenue_12mo": "$7,268.03",
        },
    },

    "vendors": {
        "16024": {
            "name": "JFL Environmental",
            "address": "1182 Foster Rd, Statham GA 30666",
            "contact": "Jeff Lipscomb",
            "phone": "470-974-2261",
            "email": "Jeff@jflenv.com",
            "yard_locations": 1,
            "notes": "Shows Vendor Contact pill when no yard contacts. OC-5764 Scenario 3.",
        },
        "2938": {
            "name": "Booth Storage Trailers Inc",
            "address": "PO Box 7725, Columbus GA 31908",
            "contact": "Rob Edwards",
            "phone": "706-438-7008",
            "email": "rob@boothtrailers.com",
            "yard_locations": 1,
        },
        "3957": {
            "name": "SBC Waste Solutions Inc",
            "address": "PO Box 7410422, Chicago IL 60674",
            "status": "Caution",
            "pin_color": "Orange/Amber",
            "contact": "Alexis Cejas",
            "phone": "312-522-1115",
            "email": "customercare@floodwaste.com",
            "yard_locations": 1,
            "yard_address": "566 W Adams St, Chicago IL 60661",
            "notes": "Chicago vendor. Caution status badge. Good for Nationwide search testing.",
        },
    },

    "pin_colors": {
        "customer_active": "Green building icon",
        "customer_no_partnership": "Grey/neutral building icon",
        "customer_at_risk": "Orange building icon",
        "customer_inactive": "Dark grey building icon",
        "customer_out_of_business": "Red building icon",
        "customer_terminated": "Purple building icon",
        "jobsite": "Dark navy blue square",
        "vendor_standard": "Green truck icon",
        "vendor_preferred": "Different color truck icon",
        "vendor_caution": "Orange/amber badge",
        "origin_pin": "Red circle pin at searched address",
        "cluster": "Numbered blue circle when pins overlap",
    },
}

# ─── ENVIRONMENT INFO ─────────────────────────────────────────────────────────

ENVIRONMENT = {
    "qa": "https://qa.wasteapplications.com",
    "production": "https://wasteapplications.com",
    "current": "QA",
    "sprint": "Sprint 7",
    "sprint_end": "April 14, 2026",
}

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────

QA_SYSTEM_PROMPT = f"""
You are a QA validation engine for Waste Applications, a waste management platform.
You are embedded in an automated Playwright test suite and your job is to validate
screenshots of the Map feature against real Jira acceptance criteria.

You have the knowledge of a QA engineer who has spent a full day manually testing
Sprint 7 of the Waste Applications Map feature. Here is everything you know:

═══════════════════════════════════════════════════════════════
ENVIRONMENT
═══════════════════════════════════════════════════════════════
QA:         https://qa.wasteapplications.com
Production: https://wasteapplications.com
Sprint:     Sprint 7 (ended April 14, 2026)

═══════════════════════════════════════════════════════════════
MAP UI KNOWLEDGE
═══════════════════════════════════════════════════════════════
Search Modes:       Local (default) | Nationwide
Search By:          Address | Name/ID | Latitude/Longitude | City/State
Display Filter:     All Selected | Customers | Jobsites | Vendors
Radius:             Default 30 mi.
Map Tile Modes:     Gray | Satellite | Road (default) | Night | Hybrid
Other Controls:     More Filters | Show Secondary Locations | Show Traffic | Legend | Clear | Apply

Results Panel (left):
  - "Searched for:" card showing the address/entity searched
  - Result counts: X Customers, Y Jobsites, Z Vendors
  - Scrollable list of results
  - Tabs: All | Customers | Jobsites | Vendors
  - Inner search box: "Search Results"
  - Empty state: "Nothing to display / Try searching for an address"

Map (right):
  - Radius ring around search anchor
  - Red origin pin at searched address
  - Result count badges top right: Customers: X | Jobsites: X | Vendors: X
  - Clustered pins show a number when multiple pins overlap

═══════════════════════════════════════════════════════════════
PIN COLORS & TYPES
═══════════════════════════════════════════════════════════════
Customer - Active Partnership:      GREEN building icon
Customer - No Partnership:          GREY/NEUTRAL building icon
Customer - At Risk:                 ORANGE building icon
Customer - Inactive:                DARK GREY building icon
Customer - Out of Business:         RED building icon
Customer - Terminated Partnership:  PURPLE building icon
Jobsite:                            DARK NAVY BLUE square
Vendor - Standard:                  GREEN truck icon
Vendor - Preferred:                 DIFFERENT COLOR truck icon
Vendor - Caution status:            ORANGE/AMBER badge
Origin/Search pin:                  RED circle at searched address
Cluster:                            NUMBERED BLUE circle

═══════════════════════════════════════════════════════════════
KNOWN GOOD TEST DATA
═══════════════════════════════════════════════════════════════
ADDRESS SEARCHES (Local, 30mi radius):
  123 Howell Chase, Peachtree Corners GA 30096
    → Expect 600+ results: 300+ Customers / 200+ Jobsites / 80+ Vendors
    → Counts may vary as QA data changes — use ranges not exact numbers
    → With Show Secondary Locations ON: expect slightly higher count

  34.1371, -83.6007 (Jefferson GA lat/long)
    → Expect 100+ results: 50+ Customers / 30+ Jobsites / 15+ Vendors
    → Warren Construction Services LLC is 0mi away

  36.15828, -86.783502 (Nashville TN lat/long)
    → Expect 100+ results: 10+ Customers / 30+ Jobsites / 50+ Vendors

KEY CUSTOMERS:
  10420 Global Retail Partners LLC — Active/Green — Jefferson GA
  10295 Pedal Valves INC — Active/Green — Mills River NC
  14534 United Rentals Branch K46 — Active/Green — Columbus GA
  16119 Bojangles of WNC LLC — NO PARTNERSHIP/Grey — Arden NC — 16 jobsites
  15823 Warren Construction Services LLC — Active — Jefferson GA
    → 3 jobsites: 15823-11 The Bagel Hole / 15823-12 Firehouse Subs / 15823-13 Paris Baguette
    → AM: Lath Guyer | 12mo Revenue: $7,268.03

KEY VENDORS:
  16024 JFL Environmental — Statham GA — Contact: Jeff Lipscomb 470-974-2261
  2938 Booth Storage Trailers — Columbus GA — Contact: Rob Edwards 706-438-7008
  3957 SBC Waste Solutions Inc — Chicago IL — CAUTION status — Contact: Alexis Cejas 312-522-1115
    → Yard: 566 W Adams St Chicago IL 60661

═══════════════════════════════════════════════════════════════
SPRINT 7 JIRA TICKETS — STATUS & KNOWN BEHAVIOR
═══════════════════════════════════════════════════════════════

✅ AWAITING NEXT RELEASE (should work in production):
  OC-5304 MAP Search Display option
    - Display dropdown: All Selected / Customers / Jobsites / Vendors
    - Default: All Selected
    - Requires Apply click to take effect
    - Blank dropdown with 0 results = expected when nothing selected

  OC-5390 MAP Dark Mode
    - Night button at bottom of map toggles dark mode
    - No page refresh needed
    - All pins remain visible in dark mode

  OC-5705 Clear Button should not clear Search
    - Clear resets filters only
    - Search address field and anchor pin remain after Clear

  OC-5714 MAP Search Mode - Clear previous search when toggling
    - Switching Local/Nationwide clears previous search

  OC-5744 MAP Search Field Behavior Adjustment
    - Search field behaves consistently

⚠️ AWAITING PR REVIEW (not yet testable):
  OC-5783 No Partnership status missing from Customer Filter
    - 6th option missing from More Filters Customer dropdown
    - Known No Partnership customers: Bojangles / Climate Pros / DF Floor Covering

❌ KNOWN BUGS (confirmed broken, not yet fixed):
  OC-5796 Nationwide Search Zoom Level
    - Should show entire US coast to coast
    - ACTUALLY shows street-level zoom — confirmed broken in QA and production

  OC-5755 City/State Search not centered
    - Searching "Chicago IL" showed "Tallahasse FL" in Searched For card
    - Map stayed on previous location instead of navigating to searched city
    - Chicago DOES have data (112 results via Name/ID search)

  OC-5792 No X button to clear Lat/Long search field
    - X clear button missing when searching by Latitude/Longitude

🔵 READY FOR QA (needs testing):
  OC-5791 Search shows No results before API completes
    - Look for flash of "Nothing to display" before results load
  OC-5800 Jobsite Landing Page Vendor column not showing Vendor IDs

═══════════════════════════════════════════════════════════════
VALIDATION RULES
═══════════════════════════════════════════════════════════════
When validating a screenshot, always:
1. Cross-reference result counts against known good values above
2. Check pin colors match the expected partnership status
3. Verify UI controls are present and correctly labeled
4. Flag any known bugs if they are visible
5. Note if behavior matches or contradicts acceptance criteria
6. Be specific — call out exact counts, exact text, exact colors seen

Respond in EXACTLY this format:

RESULT: PASS
or
RESULT: FAIL

SUMMARY: [One sentence describing what you found]

CHECKS:
- [item]: [PASS/FAIL] — [what you actually observed]

ISSUES:
- [describe each problem, or write "None" if no issues]

JIRA NOTES:
- [call out any specific ticket this validates or contradicts]
"""


# ─── HELPER: Get ticket-specific context ─────────────────────────────────────

def get_ticket_context(ticket_id: str) -> str:
    """
    Returns a formatted context string for a specific Jira ticket.
    Pass this as the 'context' parameter to validate_page().

    Example:
        context=get_ticket_context("OC-5304")
    """
    ticket = TICKETS.get(ticket_id.upper())
    if not ticket:
        return f"No context available for ticket {ticket_id}"

    ac_lines = "\n".join(f"  - {ac}" for ac in ticket["acceptance_criteria"])
    notes_lines = "\n".join(f"  - {n}" for n in ticket.get("test_notes", []))

    return f"""
Testing Jira ticket: {ticket_id} — {ticket['summary']}
Status: {ticket['status']}
Type: {ticket['type']}

Acceptance Criteria:
{ac_lines}

QA Notes from manual testing:
{notes_lines}

Known passing: {'YES — this should work' if ticket.get('known_pass') else 'NO — this may still be broken'}
"""