from datetime import date
from pathlib import Path
import sqlite3
import tempfile

from grantops.operational_graph import (
    ensure_schema, build_graph, list_nodes, list_edges, list_deadlines,
    evidence_safety_summary, project_month_start, project_month_end,
)
import grantops.operational_graph as operational_graph_module

# Test-fixture only: the temporary SQLite DB intentionally contains only the
# graph dependencies under test. Production/local GrantOps keeps the real
# append-only audit_log and the engine continues to call it normally.
operational_graph_module.audit = lambda *args, **kwargs: None

assert project_month_start(date(2024,5,1), 1).isoformat() == "2024-05-01"
assert project_month_end(date(2024,5,1), 6).isoformat() == "2024-10-31"
assert project_month_end(date(2024,5,1), 40).isoformat() == "2027-08-31"

tmp = Path(tempfile.mkdtemp()) / "graph_test.db"
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
CREATE TABLE evidence_items(
 id INTEGER PRIMARY KEY, obligation_id INTEGER, label TEXT, evidence_type TEXT,
 location TEXT, status TEXT, notes TEXT
);
""")
con.execute("INSERT INTO projects VALUES(1,'TEST','Test project','Coordinator','HE','2024-05-01','2025-07-31','ACTIVE',NULL,NULL)")
con.execute("INSERT INTO annex1_runs VALUES(1,1,1,'annex1-v1.0','PROPOSED',50,100,1,1,1,1,'x')")
con.execute("INSERT INTO annex1_work_packages VALUES(1,1,1,'WP1','Core work','1 - ORG',1,15,60,'wp quote','sha-wp','entity-wp','PROPOSED','x')")
con.execute("INSERT INTO annex1_deliverables VALUES(1,1,1,'D1.1','Report','WP1','1 - ORG',6,'R','PU',70,'del quote','sha-del','entity-del','PROPOSED','x')")
con.execute("INSERT INTO annex1_milestones VALUES(1,1,1,'M1',1,'Milestone','[\"WP1\"]','1 - ORG','Proof',7,80,'ms quote','sha-ms','entity-ms','PROPOSED','x')")
con.execute("INSERT INTO annex1_reporting_periods VALUES(1,1,1,'RP1',1,1,15,'Periodic report','60 days after end of reporting period',10,'rp quote','sha-rp','entity-rp','PROPOSED','x')")
con.execute("INSERT INTO obligations VALUES(1,1,'OBLIGATION','Keep records','desc',NULL,NULL,'OPEN','HUMAN_VERIFIED','52','Article 20','must keep records','same-sha','x')")
con.execute("INSERT INTO obligations VALUES(2,1,'EVIDENCE_REQUIREMENT','Original documents','desc',NULL,NULL,'OPEN','HUMAN_VERIFIED','52','Article 20','must keep original documents','same-sha','x')")
con.execute("INSERT INTO obligations VALUES(3,1,'OBLIGATION','UNVERIFIED MUST STAY OUT','desc',NULL,NULL,'OPEN','UNVERIFIED','53','Article 21','text','sha3','x')")
con.execute("INSERT INTO ga_candidates VALUES(1,1,'EVIDENCE_REQUIREMENT','PENDING',NULL)")
con.execute("INSERT INTO evidence_items VALUES(1,1,'Signed proof','DOCUMENT','repo/path','READY','ok')")
con.commit()
con.close()

ensure_schema(tmp)
result = build_graph(tmp, 1)
assert result["structural_node_count"] == 4
nodes = list_nodes(tmp, result["id"])
edges = list_edges(tmp, result["id"])
deadlines = list_deadlines(tmp, result["id"])
assert "UNVERIFIED MUST STAY OUT" not in {n["title"] for n in nodes}
assert {"PROJECT","WORK_PACKAGE","DELIVERABLE","MILESTONE","REPORTING_PERIOD","OBLIGATION","EVIDENCE_REQUIREMENT","EVIDENCE_ITEM","RESPONSIBLE_PARTY"} <= {n["node_type"] for n in nodes}

edge_keys = {(e["from_node_key"], e["relation_type"], e["to_node_key"]) for e in edges}
assert ("WP:WP1", "HAS_DELIVERABLE", "DEL:D1.1") in edge_keys
assert ("MS:M1", "RELATES_TO", "WP:WP1") in edge_keys
assert ("DEL:D1.1", "DUE_IN", "RP:RP1") in edge_keys
assert ("MS:M1", "DUE_IN", "RP:RP1") in edge_keys
assert any(e["relation_type"] == "EVIDENCE_FOR" for e in edges)
assert any(e["relation_type"] == "SUPPORTED_BY" for e in edges)

by_kind = {(d["node_key"], d["deadline_kind"]): d for d in deadlines}
assert by_kind[("DEL:D1.1","DELIVERABLE_DUE")]["resolved_date"] == "2024-10-31"
assert by_kind[("MS:M1","MILESTONE_DUE")]["resolved_date"] == "2024-11-30"
assert by_kind[("RP:RP1","REPORTING_PERIOD_END")]["resolved_date"] == "2025-07-31"
assert by_kind[("RP:RP1","REPORT_DUE")]["resolved_date"] == "2025-09-29"

safety = evidence_safety_summary(tmp, 1, result["id"])
assert safety["verified_evidence_requirements"] == 1
assert safety["pending_unverified_evidence_candidates_excluded"] == 1
assert safety["non_verified_evidence_nodes_in_graph"] == 0

print("PASS_MVP_V0_4_OPERATIONAL_GRAPH")