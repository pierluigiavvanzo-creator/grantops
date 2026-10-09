from grantops.annex1 import (
    _parse_wp_page,
    _parse_deliverable_page,
    _parse_milestone_page,
    _parse_reporting_period_page,
)

def page(num, text):
    return {"page_number": num, "text_sha256": f"sha{num}", "text": text}

wp = page(74, """
Work package WP1 - Need of analysis for capacity and competence building
Work Package Number WP1 Lead Beneficiary 1 - UPCE
Work Package Name Need of analysis for capacity and competence building
Start Month 1 End Month 7
Objectives
""")
wps = _parse_wp_page(wp)
assert len(wps) == 1
assert wps[0]["wp_code"] == "WP1"
assert wps[0]["start_month"] == 1 and wps[0]["end_month"] == 7

deliverables = page(86, """
Deliverable D4.2 - R&I infrastructure online platform
Deliverable Number D4.2 Lead Beneficiary 2 - UKIM
Deliverable Name R&I infrastructure online platform
Type DEC — Websites, patent filings, videos, etc
Dissemination Level PU - Public
Due Date (month) 12 Work Package No WP4
Description
Deliverable D5.1 - Plan for dissemination and exploitation including communication activitiesplan
Deliverable Number D5.1 Lead Beneficiary 3 - ZPSU
Deliverable Name Plan for dissemination and exploitation including communication activitiesplan
Type DEC — Websites, patent filings, videos, etc
Dissemination Level PU - Public
Due Date (month) 6 Work Package No WP5
Description
""")
ds = _parse_deliverable_page(deliverables)
assert [x["deliverable_code"] for x in ds] == ["D4.2", "D5.1"]
assert ds[1]["due_month"] == 6

d11 = page(85, """
Deliverable D l.l - Analysis of the needs, requirements and expectations of target groups
Deliverable Number D l.l Lead Beneficiary 1 - UPCE
Deliverable Name Analysis of the needs, requirements and expectations of target groups
Type R — Document, report Dissemination Level PU - Public
Due Date (month) 7 Work Package No WP1
Description
""")
d11rows = _parse_deliverable_page(d11)
assert len(d11rows) == 1 and d11rows[0]["deliverable_code"] == "D1.1"

milestones = page(89, """
LIST OF MILESTONES
Milestones
Grant Preparation (Milestones screen) — Enter the info.
Milestone
No
Milestone Name Work Package No Lead Beneficiary Means of Verification Due Date
(month)
1 Pre-analysis of the needs, requirements and
expectations of the target groups completed
WP6, WP4, WP1, WP5
1 - UPCE D l.l Analysis of the needs, requirements and
expectations of target groups
14
2 First certificates from training WP2 1 - UPCE First target groups have been awarded WIDE
AcrossEU certificates
24
3 Joint priorities and infrastructure platform WP3, WP6, WP4, WP1, WP5
2 - UKIM D4.1 Joint R&I international strategic priorities and D4.2 R&I infrastructure online platform
28
4 Demonstrated exploitation WP3, WP6, WP4, WP5, WP2
2 - UKIM Funding proposals submitted 36
5 Successful final conference - end of the project
WP6, WP5 1 - UPCE Number of participants D6.2 Report from the final conference
40
LIST OF CRITICAL RISKS
""")
ms = _parse_milestone_page(milestones)
assert len(ms) == 5, ms
assert [x["due_month"] for x in ms] == [14,24,28,36,40], ms
assert ms[0]["milestone_code"] == "M1"
assert "WP1" in ms[0]["work_package_codes"]

reporting = page(10, """
4.2 Periodic reporting and payments
Reporting and payment schedule (art 21, 22):
Reporting Payments
Reporting periods Type Deadline Type Deadline
(time to pay)
RP No Month from Month to
Initial prefinancing
30 days from entry into force
1 1 15 Periodic report 60 days after end of reporting period Interim payment 90 days from receiving periodic report
2 16 40 Periodic report 60 days after end of reporting period Final payment 90 days from receiving periodic report
Prefinancing payments and guarantees:
""")
rp = _parse_reporting_period_page(reporting)
assert len(rp) == 2, rp
assert [(x["month_from"], x["month_to"]) for x in rp] == [(1,15),(16,40)]
assert all(x["report_deadline_rule"] == "60 days after end of reporting period" for x in rp)

print("PASS_MVP_V0_3_ANNEX1_STRUCTURAL_PARSER")