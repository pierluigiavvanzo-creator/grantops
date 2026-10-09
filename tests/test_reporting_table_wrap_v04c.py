from datetime import date
from pathlib import Path
import sqlite3
import tempfile

import grantops.operational_graph as graph
from grantops.annex1 import _parse_reporting_period_page

graph.audit = lambda *args, **kwargs: None

# 1. Future Annex 1 parser must normalize the wrapped PDF table phrase.
page = {
    "page_number": 10,
    "text_sha256": "sha-page-10",
    "text": """
Reporting periods Type Deadline Type Deadline
RP No Month from Month to
1 1 15 Periodic report 60 days after end Interim payment 90 days from of reporting period receiving periodic report
2 16 40 Periodic report 60 days after end Final payment 90 days from of reporting period receiving periodic report
Prefinancing payments and guarantees:
"""
}
rows = _parse_reporting_period_page(page)
assert len(rows) == 2, rows
assert rows[0]["report_deadline_rule"] == "60 days after end of reporting period"
assert rows[1]["report_deadline_rule"] == "60 days after end of reporting period"

# 2. Existing DB rows with NULL normalized rule must still resolve from source_quote.
tmp = Path(tempfile.mkdtemp()) / "v04c.db"
con = sqlite3.connect(tmp)
con.executescript("""
CREATE TABLE projects(
 id INTEGER PRIMARY KEY, code TEXT, title TEXT, coordinator TEXT, programme TEXT,
 start_date TEXT, end_date TEXT, status TEXT, source_url TEXT, notes TEXT
);
CREATE TABLE annex1_runs(
 id INTEGER PRIMARY KEY, project_id INTEGER, extraction_id INTEGER, parser_version TEXT,
 status TEXT, source_page_from INTEGER, source_page_to INTEGER,
 work_package_count INTEGER, deliverable_count INTEGER, milestone_count INTEGER,
 reporting_period_count INTEGER, created_at TEXT
);
CREATE TABLE annex1_work_packages(
 id INTEGER PRIMARY KEY, run_id INTEGER, project_id INTEGER, wp_code TEXT, name TEXT,
 lead_beneficiary TEXT, start_month INTEGER, end_month INTEGER, source_page INTEGER,
 source_quote TEXT, source_text_sha256 TEXT, entity_sha256 TEXT, review_status TEXT, created_at TEXT
);
CREATE TABLE annex1_deliverables(
 id INTEGER PRIMARY KEY, run_id INTEGER, project_id INTEGER, deliverable_code TEXT, name TEXT,
 work_package_code TEXT, lead_beneficiary TEXT, due_month INTEGER, deliverable_type TEXT,
 dissemination_level TEXT, source_page INTEGER, source_quote TEXT, source_text_sha256 TEXT,
 entity_sha256 TEXT, review_status TEXT, created_at TEXT
);
CREATE TABLE annex1_milestones(
 id INTEGER PRIMARY KEY, run_id INTEGER, project_id INTEGER, milestone_code TEXT,
 milestone_number INTEGER, name TEXT, work_package_codes_json TEXT, lead_beneficiary TEXT,
 means_of_verification TEXT, due_month INTEGER, source_page INTEGER, source_quote TEXT,
 source_text_sha256 TEXT, entity_sha256 TEXT, review_status TEXT, created_at TEXT
);
CREATE TABLE annex1_reporting_periods(
 id INTEGER PRIMARY KEY, run_id INTEGER, project_id INTEGER, rp_code TEXT, rp_number INTEGER,
 month_from INTEGER, month_to INTEGER, report_type TEXT, report_deadline_rule TEXT,
 source_page INTEGER, source_quote TEXT, source_text_sha256 TEXT, entity_sha256 TEXT,
 review_status TEXT, created_at TEXT
);
CREATE TABLE obligations(
 id INTEGER PRIMARY KEY, project_id INTEGER, record_type TEXT, title TEXT, description TEXT,
 due_date TEXT, owner TEXT, status TEXT, verification_status TEXT, source_page TEXT,
 source_section TEXT, source_quote TEXT, source_text_sha256 TEXT, created_at TEXT
);
CREATE TABLE ga_candidates(
 id INTEGER PRIMARY KEY, project_id INTEGER, record_type TEXT, review_status TEXT,
 promoted_record_id INTEGER
);
CREATE TABLE ga_candidate_context(candidate_id INTEGER PRIMARY KEY, trigger_text TEXT);
""")
con.execute("INSERT INTO projects VALUES(1,'WIDE','WIDE','UPCE','HE','2024-05-01','2027-08-31','ACTIVE',NULL,NULL)")
con.execute("INSERT INTO annex1_runs VALUES(1,1,1,'annex1-v1.0','PROPOSED',1,10,0,0,0,2,'x')")
q1 = "1 1 15 Periodic report 60 days after end Interim payment 90 days from of reporting period receiving periodic report"
q2 = "2 16 40 Periodic report 60 days after end Final payment 90 days from of reporting period receiving periodic report"
con.execute("INSERT INTO annex1_reporting_periods VALUES(1,1,1,'RP1',1,1,15,'Periodic report',NULL,10,?,'sha1','e1','PROPOSED','x')", (q1,))
con.execute("INSERT INTO annex1_reporting_periods VALUES(2,1,1,'RP2',2,16,40,'Periodic report',NULL,10,?,'sha2','e2','PROPOSED','x')", (q2,))
con.commit()
con.close()

graph.ensure_schema(tmp)
summary = graph.build_graph(tmp, 1)
deadlines = graph.list_deadlines(tmp, summary["id"])
report_due = {d["node_key"]: d for d in deadlines if d["deadline_kind"] == "REPORT_DUE"}

assert set(report_due) == {"RP:RP1", "RP:RP2"}, report_due
assert report_due["RP:RP1"]["resolved_date"] == "2025-09-29"
assert report_due["RP:RP2"]["resolved_date"] == "2027-10-30"
assert report_due["RP:RP1"]["relative_rule"] == "60 days after end of reporting period"
assert "SOURCE_QUOTE_TABLE_WRAP_REPAIR" in report_due["RP:RP1"]["basis"]

print("PASS_MVP_V0_4C_REPORTING_TABLE_WRAP_REPAIR")