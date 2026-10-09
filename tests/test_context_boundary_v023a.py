import re
from grantops.ga_review import (
    _nearest_heading,
    _context_window,
    _analyze_completeness,
)

# 1) Article references inside body must not masquerade as structural heading.
page = """
ARTICLE 9 — OTHER PARTICIPANTS INVOLVED IN THE ACTION
9.1 Associated partners
The beneficiaries must ensure that their contractual obligations under Articles 11, 12, 13 and 20 also apply.
The beneficiaries must ensure that the bodies mentioned in Article 25 (e.g. granting authority, OLAF, Court of Auditors (ECA), etc.) can exercise their rights also towards the associated partners.
[OPTION 2: Not applicable] 9.2 Third parties giving in-kind contributions to the action
Other third parties may give in-kind contributions to the action if necessary for the implementation.
"""
quote = "The beneficiaries must ensure that the bodies mentioned in Article 25 (e."
article, heading = _nearest_heading(page, quote)
assert article == "Article 9", (article, heading)
assert heading.startswith("ARTICLE 9"), heading

# 2) Recovery must stop before the following OPTION/subsection.
window = _context_window(page, quote)
assert "granting authority" in window["current"]
assert "associated partners" in window["current"]
assert "OPTION 2" not in window["current"]
assert "if necessary for the implementation" not in window["current"]

candidate = {
    "source_quote": quote,
    "candidate_action": "ensure that the bodies mentioned in Article 25 (e.",
    "candidate_subject": "The beneficiaries",
}
analysis = _analyze_completeness(
    candidate,
    window,
    "UNKNOWN",
    source_heading=heading,
)
assert analysis["trigger_text"] is None, analysis
assert analysis["applicability"] == "ALWAYS", analysis
assert "SOURCE_QUOTE_TRUNCATION_RECOVERED" in analysis["warnings"], analysis

# 3) A trigger inside the same clause must still be captured.
page2 = """
ARTICLE 32 — TERMINATION
The coordinator must — within 60 days from when termination takes effect — submit: a report on the work carried out.
"""
quote2 = "The coordinator must — within 60 days from when termination takes effect — submit:"
w2 = _context_window(page2, quote2)
a2 = _analyze_completeness(
    {
        "source_quote": quote2,
        "candidate_action": "— within 60 days from when termination takes effect — submit:",
        "candidate_subject": "The coordinator",
    },
    w2,
    "UNKNOWN",
    source_heading="ARTICLE 32 — TERMINATION",
)
assert a2["trigger_text"] and "within 60 days" in a2["trigger_text"].lower(), a2
assert a2["applicability"] == "IF_EVENT", a2

print("PASS_MVP_V0_2_3A_SEMANTIC_BOUNDARIES")