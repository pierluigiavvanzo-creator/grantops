from datetime import date
from pathlib import Path
import sqlite3
import tempfile

import grantops.operational_graph as graph

# Test-only: synthetic DB has no production audit table.
graph.audit = lambda *args, **kwargs: None

tmp = Path(tempfile.mkdtemp()) / "v04b.db"
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
con.execute("INSERT INTO projects VALUES(1,'TEST','Test','Coord','HE','2024-05-01','2027-08-31','ACTIVE',NULL,NULL)")
con.execute("INSERT INTO annex1_runs VALUES(1,1,1,'annex1-v1.0','PROPOSED',1,10,0,0,0,2,'x')")
# Deliberately NULL normalized rule; explicit rule remains in authoritative quote.
quote1 = "1 1 15 Periodic report 60 days after end of reporting period Interim payment"
quote2 = "2 16 40 Periodic report 60 days after end of reporting period Final payment"
con.execute("INSERT INTO annex1_reporting_periods VALUES(1,1,1,'RP1',1,1,15,'Periodic report',NULL,10,?,'sha1','e1','PROPOSED','x')", (quote1,))
con.execute("INSERT INTO annex1_reporting_periods VALUES(2,1,1,'RP2',2,16,40,'Periodic report',NULL,10,?,'sha2','e2','PROPOSED','x')", (quote2,))
con.commit()
con.close()

graph.ensure_schema(tmp)
summary = graph.build_graph(tmp, 1)
deadlines = graph.list_deadlines(tmp, summary["id"])

report_due = [d for d in deadlines if d["deadline_kind"] == "REPORT_DUE"]
assert len(report_due) == 2, report_due

by_node = {d["node_key"]: d for d in report_due}
assert by_node["RP:RP1"]["resolved_date"] == "2025-09-29"
assert by_node["RP:RP2"]["resolved_date"] == "2027-10-30"
assert by_node["RP:RP1"]["relative_rule"] == "60 days after end of reporting period"
assert "SOURCE_QUOTE" in by_node["RP:RP1"]["basis"]

print("PASS_MVP_V0_4B_REPORT_DEADLINE_PROVENANCE_FIX")