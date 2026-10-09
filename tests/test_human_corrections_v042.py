from pathlib import Path
import sqlite3
import tempfile

import grantops.ga_review as ga
import grantops.corrections as corr

ga.audit = lambda *args, **kwargs: None
corr.audit = lambda *args, **kwargs: None

tmp = Path(tempfile.mkdtemp()) / "v042.db"
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
CREATE TABLE obligations(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 project_id INTEGER NOT NULL,
 record_type TEXT NOT NULL,
 title TEXT NOT NULL,
 description TEXT,
 due_date TEXT,
 owner TEXT,
 status TEXT NOT NULL,
 verification_status TEXT NOT NULL,
 source_page TEXT,
 source_section TEXT,
 source_quote TEXT,
 source_text_sha256 TEXT,
 created_at TEXT NOT NULL
);
""")
con.execute("INSERT INTO projects VALUES(1,'T','Test','Coord','HE','2024-01-01','2025-01-01','ACTIVE',NULL,NULL)")
con.execute("INSERT INTO grant_documents VALUES(10,1,'ga.pdf','ga.pdf','docsha',1000,'EXTRACTED_REVIEW_PENDING','x')")
con.commit()
con.close()

ga.ensure_schema(tmp)
corr.ensure_schema(tmp)

page_text = "The beneficiary must keep original records."
page_hash = ga._sha256_text(page_text)

candidate = {
    "extraction_id": 20,
    "project_id": 1,
    "document_id": 10,
    "record_type": "OBLIGATION",
    "source_page": 5,
    "source_quote": "The beneficiary must keep original records.",
    "source_text_sha256": page_hash,
    "candidate_subject": "The beneficiary",
    "candidate_action": "keep original records.",
    "candidate_trigger_or_due": None,
    "rule_id": "R-OBL-001",
}
candidate_hash = ga._candidate_hash(candidate)

con = sqlite3.connect(tmp)
con.execute(
    """INSERT INTO ga_extractions(
       id,project_id,document_id,document_sha256,backend,backend_version,
       extraction_mode,page_count,total_text_chars,empty_page_count,
       ocr_used,network_requests,status,created_at
       ) VALUES(20,1,10,'docsha','pypdf','6.19.0','layout',1,50,0,0,0,'PASS_TEXT_EXTRACTED','x')"""
)
con.execute(
    "INSERT INTO ga_pages(id,extraction_id,page_number,text_sha256,char_count,text) VALUES(30,20,5,?,?,?)",
    (page_hash, len(page_text), page_text),
)
con.execute(
    """INSERT INTO obligations(
       id,project_id,record_type,title,description,due_date,owner,status,
       verification_status,source_page,source_section,source_quote,
       source_text_sha256,created_at
       ) VALUES(100,1,'OBLIGATION','Keep records','Original description',NULL,'Alice',
                'IN_PROGRESS','HUMAN_VERIFIED','5','Grant Agreement · Article 20',
                ?,?,'x')""",
    (page_text, page_hash),
)
con.execute(
    """INSERT INTO ga_candidates(
       id,extraction_id,project_id,document_id,record_type,source_page,
       source_quote,source_text_sha256,candidate_subject,candidate_action,
       candidate_trigger_or_due,rule_id,candidate_sha256,review_status,
       reviewer,reviewed_at,review_notes,promoted_record_id,created_at
       ) VALUES(200,20,1,10,'OBLIGATION',5,?,?,?,?,?,?,?,'APPROVED',
                'Reviewer A','x','initial approval',100,'x')""",
    (
        candidate["source_quote"],
        page_hash,
        candidate["candidate_subject"],
        candidate["candidate_action"],
        None,
        candidate["rule_id"],
        candidate_hash,
    ),
)
con.execute(
    """INSERT INTO ga_candidate_context(
       candidate_id,analysis_version,document_kind,source_article,source_heading,
       context_before,context_quote,context_after,applicability,trigger_text,
       context_status,promotable,blocking_reasons_json,warnings_json,
       duplicate_of_candidate_id,relation_type,analyzed_at
       ) VALUES(200,'context-v1.1','PROJECT_GRANT_AGREEMENT','Article 20','ARTICLE 20',
                NULL,?,NULL,'ALWAYS',NULL,'READY',1,'[]','[]',NULL,NULL,'x')""",
    (page_text,),
)
con.commit()
con.close()

# Edit operational fields while preserving source identity.
before = corr.get_operational_record(tmp, 100)
edit = corr.edit_operational_record(
    tmp,
    100,
    "Editor One",
    "Correct owner and due date after human verification.",
    {
        "title": "Keep original records",
        "description": "Corrected operational description",
        "owner": "Bob",
        "due_date": "2025-03-31",
        "status": "IN_PROGRESS",
    },
    confirm_source_immutable=True,
)
after_edit = corr.get_operational_record(tmp, 100)
assert edit["record_id"] == 100
assert after_edit["owner"] == "Bob"
assert after_edit["due_date"] == "2025-03-31"
assert after_edit["source_quote"] == before["source_quote"]
assert after_edit["source_text_sha256"] == before["source_text_sha256"]
assert after_edit["verification_status"] == "HUMAN_VERIFIED"

# Immutable fields cannot be changed through correction API.
try:
    corr.edit_operational_record(
        tmp, 100, "Editor One", "bad", {"source_quote": "changed"},
        confirm_source_immutable=True,
    )
    raise AssertionError("immutable source field should have failed")
except ValueError as exc:
    assert "IMMUTABLE_OR_UNKNOWN_FIELDS" in str(exc)

# Reopen approved candidate: preserve record ID, unverify + block.
reopened = corr.reopen_candidate(
    tmp,
    200,
    "Reviewer B",
    "Source interpretation needs another review.",
    confirm_effect=True,
)
assert reopened["promoted_record_id"] == 100

con = sqlite3.connect(tmp)
con.row_factory = sqlite3.Row
c = dict(con.execute("SELECT * FROM ga_candidates WHERE id=200").fetchone())
o = dict(con.execute("SELECT * FROM obligations WHERE id=100").fetchone())
con.close()
assert c["review_status"] == "NEEDS_CLARIFICATION"
assert c["promoted_record_id"] == 100
assert o["verification_status"] == "UNVERIFIED"
assert o["status"] == "BLOCKED"

# Re-approval must reuse record #100 and restore pre-reopen status IN_PROGRESS.
result = ga.review_candidate(
    tmp,
    200,
    "APPROVE",
    "Reviewer C",
    True,
    True,
    True,
    "Rechecked against source.",
)
assert result["promoted_record_id"] == 100
assert result["reused_promoted_record"] is True

con = sqlite3.connect(tmp)
con.row_factory = sqlite3.Row
count = con.execute("SELECT COUNT(*) AS n FROM obligations").fetchone()["n"]
c = dict(con.execute("SELECT * FROM ga_candidates WHERE id=200").fetchone())
o = dict(con.execute("SELECT * FROM obligations WHERE id=100").fetchone())
con.close()

assert count == 1
assert c["review_status"] == "APPROVED"
assert c["promoted_record_id"] == 100
assert o["verification_status"] == "HUMAN_VERIFIED"
assert o["status"] == "IN_PROGRESS"
# Human edit survives reapproval.
assert o["owner"] == "Bob"
assert o["due_date"] == "2025-03-31"

events = corr.list_change_events(tmp, 1)
actions = [e["action"] for e in events]
assert "RECORD_EDIT" in actions
assert "CANDIDATE_REOPEN" in actions
assert "CANDIDATE_REAPPROVED" in actions

print("PASS_MVP_V0_4_2_HUMAN_CORRECTIONS")