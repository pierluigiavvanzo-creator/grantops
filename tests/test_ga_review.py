from pathlib import Path
import tempfile
import hashlib

from grantops.db import init_db, connect
from grantops.repo import add_project, records
from grantops.ga_review import (
    ensure_schema,
    store_extraction_result,
    extraction_summary,
    list_candidates,
    get_candidate,
    review_candidate,
)

def run():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        db = td / "test.db"
        init_db(db)
        ensure_schema(db)

        pid = add_project(
            db,
            "TEST-HE-001",
            "Synthetic Grant Agreement Review Test",
            "Example University",
            "Horizon Europe — synthetic test",
        )

        fake_pdf = td / "ga.pdf"
        pdf_bytes = b"%PDF-1.4 synthetic fixture"
        fake_pdf.write_bytes(pdf_bytes)
        pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()

        with connect(db) as con:
            cur = con.execute(
                """INSERT INTO grant_documents(
                   project_id,filename,stored_path,sha256,byte_count,status,created_at
                   ) VALUES(?,?,?,?,?,?,datetime('now'))""",
                (
                    pid,
                    "ga.pdf",
                    str(fake_pdf),
                    pdf_sha,
                    len(pdf_bytes),
                    "STAGED_NOT_PARSED",
                ),
            )
            document_id = cur.lastrowid

        pages = [
            (
                "The coordinator shall submit the technical report by the agreed reporting deadline. "
                "The beneficiaries must keep supporting records for five years. "
                + ("Administrative context. " * 8)
            ),
            (
                "D3.2 - Sustainability assessment due M18. "
                "MS2 - Consortium validation milestone due M20. "
                "Reporting period 1 covers M1 to M18."
                + (" Reporting context." * 8)
            ),
        ]

        summary = store_extraction_result(
            db,
            pid,
            document_id,
            pdf_sha,
            pages,
            "synthetic-test",
            "1",
            "fixture",
        )

        assert summary["status"] == "PASS_TEXT_EXTRACTED"
        assert summary["candidate_count"] >= 4
        assert summary["review_counts"]["PENDING"] == summary["candidate_count"]

        candidates = list_candidates(db, pid, review_status="PENDING")
        assert candidates

        target = next(c for c in candidates if c["record_type"] == "OBLIGATION")
        before = len(records(db, pid))

        result = review_candidate(
            db,
            target["id"],
            "APPROVE",
            "Test Reviewer",
            True,
            True,
            True,
            "Synthetic approval.",
        )
        assert result["status"] == "APPROVED"
        assert result["promoted_record_id"] is not None

        after_records = records(db, pid)
        assert len(after_records) == before + 1
        promoted = next(r for r in after_records if r["id"] == result["promoted_record_id"])
        assert promoted["verification_status"] == "HUMAN_VERIFIED"
        assert promoted["source_quote"]
        assert promoted["source_text_sha256"]
        assert promoted["due_date"] is None

        try:
            review_candidate(
                db,
                target["id"],
                "APPROVE",
                "Test Reviewer",
                True,
                True,
                True,
                "",
            )
            raise AssertionError("Double approval should be blocked")
        except ValueError as exc:
            assert "ALREADY_FINALIZED" in str(exc)

        candidate2 = next(
            c for c in list_candidates(db, pid, review_status="PENDING")
            if c["id"] != target["id"]
        )
        result2 = review_candidate(
            db,
            candidate2["id"],
            "NEEDS_CLARIFICATION",
            "Test Reviewer",
            False,
            False,
            False,
            "Need to inspect context.",
        )
        assert result2["status"] == "NEEDS_CLARIFICATION"

    print("PASS_MVP_V0_2_GA_REVIEW_PIPELINE")

if __name__ == "__main__":
    run()