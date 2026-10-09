from pathlib import Path
import sqlite3
import tempfile

from grantops.buyer_demo import buyer_demo_snapshot

tmp = Path(tempfile.mkdtemp()) / "demo.db"
con = sqlite3.connect(tmp)
con.executescript("""
CREATE TABLE projects(
 id INTEGER PRIMARY KEY, code TEXT, title TEXT, coordinator TEXT, programme TEXT,
 start_date TEXT, end_date TEXT, status TEXT, source_url TEXT, notes TEXT
);
CREATE TABLE operational_graph_runs(
 id INTEGER PRIMARY KEY, project_id INTEGER, annex1_run_id INTEGER, graph_version TEXT,
 status TEXT, project_start_date TEXT, project_end_date TEXT,
 structural_node_count INTEGER, verified_obligation_count INTEGER,
 evidence_requirement_count INTEGER, evidence_item_count INTEGER,
 edge_count INTEGER, deadline_count INTEGER, resolved_deadline_count INTEGER,
 created_at TEXT
);
CREATE TABLE operational_graph_nodes(
 id INTEGER PRIMARY KEY, run_id INTEGER, project_id INTEGER, node_key TEXT,
 node_type TEXT, source_kind TEXT, source_id INTEGER, title TEXT, owner TEXT,
 verification_status TEXT, source_page INTEGER, source_section TEXT,
 source_quote TEXT, source_text_sha256 TEXT, source_entity_sha256 TEXT,
 metadata_json TEXT, node_sha256 TEXT, created_at TEXT
);
CREATE TABLE operational_graph_edges(
 id INTEGER PRIMARY KEY, run_id INTEGER, project_id INTEGER, from_node_key TEXT,
 relation_type TEXT, to_node_key TEXT, basis TEXT, edge_sha256 TEXT, created_at TEXT
);
CREATE TABLE operational_graph_deadlines(
 id INTEGER PRIMARY KEY, run_id INTEGER, project_id INTEGER, node_key TEXT,
 deadline_kind TEXT, relative_rule TEXT, trigger_key TEXT, trigger_date TEXT,
 resolved_date TEXT, resolution_status TEXT, basis TEXT, deadline_sha256 TEXT,
 created_at TEXT
);
CREATE TABLE provenance_review_runs(
 id INTEGER PRIMARY KEY, project_id INTEGER, graph_run_id INTEGER,
 provenance_version TEXT, status TEXT, node_item_count INTEGER,
 node_complete_count INTEGER, deadline_item_count INTEGER,
 deadline_complete_count INTEGER, edge_count INTEGER, orphan_edge_count INTEGER,
 created_at TEXT
);
CREATE TABLE provenance_review_items(
 id INTEGER PRIMARY KEY, run_id INTEGER, project_id INTEGER, item_key TEXT,
 item_type TEXT, graph_node_key TEXT, graph_deadline_id INTEGER,
 source_strategy TEXT, document_id INTEGER, document_filename TEXT,
 document_sha256 TEXT, extraction_id INTEGER, page_number INTEGER,
 page_text_sha256 TEXT, source_quote TEXT, provenance_status TEXT,
 chain_json TEXT, warnings_json TEXT, provenance_sha256 TEXT, created_at TEXT
);
CREATE TABLE human_change_events(
 id INTEGER PRIMARY KEY, project_id INTEGER, entity_type TEXT, entity_id INTEGER,
 action TEXT, actor TEXT, reason TEXT, before_json TEXT, after_json TEXT,
 source_integrity_json TEXT, requires_graph_rebuild INTEGER, created_at TEXT
);
""")

con.execute("INSERT INTO projects VALUES(1,'T','Test project','Coord','HE','2024-05-01','2027-08-31','ACTIVE',NULL,NULL)")
con.execute("INSERT INTO operational_graph_runs VALUES(1,1,1,'opgraph-v1.0','PROPOSED','2024-05-01','2027-08-31',4,1,0,0,4,7,7,'2026-01-02T00:00:00+00:00')")

nodes = [
    (1,'WP:WP1','WORK_PACKAGE','WP1 — Work package','1 - ORG',1,'wp quote','sha1','{"start_month":1,"end_month":15}'),
    (2,'DEL:D1.1','DELIVERABLE','D1.1 — Report','1 - ORG',1,'d quote','sha1','{"due_month":6}'),
    (3,'MS:M1','MILESTONE','M1 — Milestone','1 - ORG',1,'m quote','sha1','{"due_month":7}'),
    (4,'RP:RP1','REPORTING_PERIOD','RP1 — M1 to M15',None,2,'rp quote','sha2','{"month_from":1,"month_to":15}'),
]
for nid,key,typ,title,owner,page,quote,sha,meta in nodes:
    con.execute(
        """INSERT INTO operational_graph_nodes
           VALUES(?,1,1,?,?,NULL,NULL,?,?,?, ?,NULL,?,?,NULL,?,'nodehash','x')""",
        (nid,key,typ,title,owner,'PROPOSED',page,quote,sha,meta)
    )

con.execute("INSERT INTO operational_graph_edges VALUES(1,1,1,'WP:WP1','HAS_DELIVERABLE','DEL:D1.1','basis','h','x')")
con.execute("INSERT INTO operational_graph_edges VALUES(2,1,1,'MS:M1','RELATES_TO','WP:WP1','basis','h','x')")

deadlines = [
    (1,'WP:WP1','WP_START','M1','2024-05-01'),
    (2,'WP:WP1','WP_END','M15','2025-07-31'),
    (3,'DEL:D1.1','DELIVERABLE_DUE','M6','2024-10-31'),
    (4,'MS:M1','MILESTONE_DUE','M7','2024-11-30'),
    (5,'RP:RP1','REPORTING_PERIOD_START','M1','2024-05-01'),
    (6,'RP:RP1','REPORTING_PERIOD_END','M15','2025-07-31'),
    (7,'RP:RP1','REPORT_DUE','60 days after end of reporting period','2025-09-29'),
]
for did,key,kind,rule,resolved in deadlines:
    con.execute(
        """INSERT INTO operational_graph_deadlines
           VALUES(?,1,1,?,?,?,NULL,NULL,?,'RESOLVED','basis','hash','x')""",
        (did,key,kind,rule,resolved)
    )

con.execute("INSERT INTO provenance_review_runs VALUES(1,1,1,'provenance-v1.0','PASS',4,4,7,7,2,0,'2026-01-03T00:00:00+00:00')")

for i,(nid,key,typ,title,owner,page,quote,sha,meta) in enumerate(nodes, start=1):
    con.execute(
        """INSERT INTO provenance_review_items
           VALUES(?,1,1,?,'GRAPH_NODE',?,NULL,'ANNEX1_RUN_CHAIN',10,'ga.pdf',
                  'docsha',20,?,?,?,'COMPLETE','[]','[]','ph','x')""",
        (i,f'NODE:{key}',key,page,sha,quote)
    )
for j,(did,key,kind,rule,resolved) in enumerate(deadlines, start=10):
    parent = next(n for n in nodes if n[1] == key)
    con.execute(
        """INSERT INTO provenance_review_items
           VALUES(?,1,1,?,'GRAPH_DEADLINE',?,?,'ANNEX1_RUN_CHAIN',10,'ga.pdf',
                  'docsha',20,?,?,?,'COMPLETE_DERIVED','[]','[]','ph','x')""",
        (j,f'DEADLINE:{did}',key,did,parent[5],parent[7],parent[6])
    )
con.commit()
con.close()

snapshot = buyer_demo_snapshot(tmp, 1)
assert snapshot["demo_ready"] is True
assert snapshot["structure"] == {
    "work_packages": 1,
    "deliverables": 1,
    "milestones": 1,
    "reporting_periods": 1,
    "total": 4,
}
assert snapshot["deadlines"]["resolved_structural"] == 7
assert snapshot["provenance"]["core_complete"] == 11
assert snapshot["provenance"]["core_total"] == 11
assert snapshot["provenance"]["source_documents"] == 1
assert snapshot["provenance"]["orphan_relations"] == 0
assert snapshot["showcase"]
assert all(x["document_filename"] == "ga.pdf" for x in snapshot["showcase"])

print("PASS_MVP_V0_5_BUYER_DEMO_READ_MODEL")