from pathlib import Path
import tempfile
import hashlib
import json

from grantops.db import init_db, connect
from grantops.repo import add_project, records
from grantops.ga_review import (
    ensure_schema, store_extraction_result, list_candidates,
    extraction_summary, review_candidate, refresh_context_for_project,
)

def make_doc(con, pid, path, filename):
    data = b"%PDF-1.4 synthetic-context-fixture"
    path.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    cur = con.execute(
        """INSERT INTO grant_documents(project_id,filename,stored_path,sha256,byte_count,status,created_at)
           VALUES(?,?,?,?,?,?,datetime('now'))""",
        (pid, filename, str(path), sha, len(data), "STAGED_NOT_PARSED"),
    )
    return cur.lastrowid, sha

def run():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        db = td / "test.db"
        init_db(db); ensure_schema(db)
        pid = add_project(db, "CTX-001", "Context Test", "Example University", "Horizon Europe")
        with connect(db) as con:
            did, sha = make_doc(con, pid, td / "project-ga.pdf", "project-grant-agreement.pdf")

        pages = [
            """ARTICLE 21 — REPORTING\nThe beneficiaries must report on the progress of the action (e.g. deliverables, milestones, outputs and outcomes).\nThe coordinator must submit them as part of the periodic report.""",
            """ARTICLE 20 — RECORDS\nBeneficiaries must keep the original documents.""",
            """ARTICLE 32 — TERMINATION\nThe coordinator must — within 60 days from when termination takes effect — submit:\n\n- a final periodic report;\n- the required financial statements.""",
            """ANNEX 5 — SPECIAL CONDITIONS\nThe beneficiaries must ensure that the activities under the action do not:\n\n- breach ethical principles;\n- focus exclusively on military applications.""",
        ]
        summary = store_extraction_result(db, pid, did, sha, pages, "synthetic", "1", "fixture")
        assert summary["candidate_count"] >= 6
        assert summary["document_kind"] == "UNKNOWN"

        cs = list_candidates(db, pid)
        report = next(c for c in cs if "report" in (c["candidate_action"] or "").lower())
        assert report["context_status"] == "READY", report
        assert "deliverables" in report["context_quote"].lower()
        assert report["promotable"] == 1
        assert "SOURCE_QUOTE_TRUNCATION_RECOVERED" in json.loads(report["warnings_json"])

        pronoun = next(c for c in cs if (c["candidate_action"] or "").lower().startswith("submit them"))
        assert pronoun["context_status"] == "CONTEXT_REQUIRED"
        assert "UNRESOLVED_REFERENCE" in json.loads(pronoun["blocking_reasons_json"])

        obligation_keep = next(c for c in cs if c["record_type"] == "OBLIGATION" and "original documents" in c["source_quote"].lower())
        evidence_keep = next(c for c in cs if c["record_type"] == "EVIDENCE_REQUIREMENT")
        assert obligation_keep["promotable"] == 1
        assert evidence_keep["context_status"] == "MERGE_REQUIRED"
        assert evidence_keep["duplicate_of_candidate_id"] == obligation_keep["id"]

        termination = next(c for c in cs if "60 days" in (c["source_quote"] or ""))
        assert termination["applicability"] == "IF_EVENT"
        assert termination["trigger_text"] and "60 days" in termination["trigger_text"]
        assert termination["context_status"] == "PARENT_CONTROL"

        parent = next(c for c in cs if "do not:" in (c["source_quote"] or ""))
        assert parent["context_status"] == "PARENT_CONTROL"

        before = len(records(db, pid))
        result = review_candidate(db, report["id"], "APPROVE", "Reviewer", True, True, True, "")
        assert result["status"] == "APPROVED"
        after = len(records(db, pid))
        assert after == before + 1

        try:
            review_candidate(db, pronoun["id"], "APPROVE", "Reviewer", True, True, True, "")
            raise AssertionError("context-required candidate should not promote")
        except ValueError as exc:
            assert "NOT_PROMOTABLE" in str(exc)

        # Model MGA source must be template-only and never promotable.
        pid2 = add_project(db, "CTX-002", "Model Test", "Example University", "Horizon Europe")
        with connect(db) as con:
            did2, sha2 = make_doc(con, pid2, td / "general-mga_horizon-euratom_en.pdf", "general-mga_horizon-euratom_en.pdf")
        store_extraction_result(db, pid2, did2, sha2, ["ARTICLE 20 — RECORDS\nBeneficiaries must keep the original documents. " + ("General Model Grant Agreement context. " * 8)], "synthetic", "1", "fixture")
        model_c = list_candidates(db, pid2)[0]
        assert model_c["document_kind"] == "MODEL_MGA"
        assert model_c["context_status"] == "TEMPLATE_ONLY"
        assert model_c["promotable"] == 0

    print("PASS_MVP_V0_2_3_CONTEXT_AWARE_EXTRACTION")

if __name__ == "__main__":
    run()