from pathlib import Path
import sqlite3
import tempfile

import grantops.operational_graph as graph
import grantops.provenance as prov

graph.audit = lambda *args, **kwargs: None
prov.audit = lambda *args, **kwargs: None

tmp = Path(tempfile.mkdtemp()) / "prov.db"
con = sqlite3.connect(tmp)
con.executescript("""
CREATE TABLE projects(
 id INTEGER PRIMARY KEY, code TEXT, title TEXT, coordinator TEXT, programme TEXT,
 start_date TEXT, end_date TEXT, status TEXT, source_url TEXT, notes TEXT
);
CREATE TABLE grant_documents(
 id INTEGER PRIMARY KEY, project_id INTEGER, filename TEXT, stored_path TEXT,
 sha256 TEXT, byte_count INTEGER, status TEXT, created_at TEXT
);
CREATE TABLE ga_extractions(
 id INTEGER PRIMARY KEY, project_id INTEGER, document_id INTEGER, document_sha256 TEXT,
 backend TEXT, backend_version TEXT, extraction_mode TEXT, page_count INTEGER,
 total_text_chars INTEGER, empty_page_count INTEGER, ocr_used INTEGER,
 network_requests INTEGER, status TEXT, created_at TEXT
);
CREATE TABLE ga_pages(
 id INTEGER PRIMARY KEY, extraction_id INTEGER, page_number INTEGER,
 text_sha256 TEXT, char_count INTEGER, text TEXT
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
 id INTEGER PRIMARY KEY, extraction_id INTEGER, project_id INTEGER, document_id INTEGER,
 record_type TEXT, source_page INTEGER, source_quote TEXT, source_text_sha256 TEXT,
 candidate_subject TEXT, candidate_action TEXT, candidate_trigger_or_due TEXT,
 rule_id TEXT, candidate_sha256 TEXT, review_status TEXT, reviewer TEXT,
 reviewed_at TEXT, review_notes TEXT, promoted_record_id INTEGER, created_at TEXT
);
CREATE TABLE ga_candidate_context(candidate_id INTEGER PRIMARY KEY, trigger_text TEXT);
""")

con.execute("INSERT INTO projects VALUES(1,'T','Test','Coord','HE','2024-05-01','2025-07-31','ACTIVE',NULL,NULL)")
con.execute("INSERT INTO grant_documents VALUES(10,1,'ga.pdf','uploads/ga.pdf','docsha',1000,'EXTRACTED_REVIEW_PENDING','x')")
con.execute("INSERT INTO ga_extractions VALUES(20,1,10,'docsha','pypdf','6.19.0','text',2,100,0,0,0,'SUCCESS','x')")
con.execute("INSERT INTO ga_pages VALUES(30,20,1,'p1sha',50,'wp page')")
con.execute("INSERT INTO ga_pages VALUES(31,20,2,'p2sha',50,'rp page')")
con.execute("INSERT INTO annex1_runs VALUES(40,1,20,'annex1-v1.0','PROPOSED',1,2,1,1,1,1,'x')")
con.execute("INSERT INTO annex1_work_packages VALUES(41,40,1,'WP1','WP','1 - ORG',1,15,1,'wp quote','p1sha','e1','PROPOSED','x')")
con.execute("INSERT INTO annex1_deliverables VALUES(42,40,1,'D1.1','Deliverable','WP1','1 - ORG',6,'R','PU',1,'d quote','p1sha','e2','PROPOSED','x')")
con.execute("INSERT INTO annex1_milestones VALUES(43,40,1,'M1',1,'Milestone','[\"WP1\"]','1 - ORG','proof',7,1,'m quote','p1sha','e3','PROPOSED','x')")
con.execute("INSERT INTO annex1_reporting_periods VALUES(44,40,1,'RP1',1,1,15,'Periodic report','60 days after end of reporting period',2,'rp quote','p2sha','e4','PROPOSED','x')")
con.commit()
con.close()

graph.ensure_schema(tmp)
g = graph.build_graph(tmp, 1)
assert g["structural_node_count"] == 4

prov.ensure_schema(tmp)
r = prov.build_provenance_review(tmp, 1, g["id"])
assert r["node_item_count"] == 4
assert r["node_complete_count"] == 4
# 2 WP deadlines + 1 deliverable + 1 milestone + 3 RP deadlines = 7
assert r["deadline_item_count"] == 7
assert r["deadline_complete_count"] == 7
assert r["orphan_edge_count"] == 0
assert r["status"] == "PASS"

items = prov.list_provenance_items(tmp, r["id"])
core = [x for x in items if x["graph_node_key"] in {"WP:WP1","DEL:D1.1","MS:M1","RP:RP1"}]
assert core
assert all(x["document_filename"] == "ga.pdf" for x in core)
assert all(x["document_sha256"] == "docsha" for x in core)
assert all(x["provenance_status"] in {"COMPLETE","COMPLETE_DERIVED"} for x in items)

print("PASS_MVP_V0_4_1_PROVENANCE_REVIEW")