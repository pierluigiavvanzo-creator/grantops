from __future__ import annotations

from datetime import date
import hashlib
import json

from .db import connect, now, audit

CORRECTIONS_VERSION = "human-corrections-v1.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS human_change_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    before_json TEXT NOT NULL,
    after_json TEXT NOT NULL,
    source_integrity_json TEXT NOT NULL,
    requires_graph_rebuild INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_human_change_events_project
ON human_change_events(project_id, created_at, entity_type, entity_id);
"""

EDITABLE_RECORD_FIELDS = {
    "title",
    "description",
    "due_date",
    "owner",
    "status",
}

ALLOWED_RECORD_STATUS = {
    "OPEN",
    "IN_PROGRESS",
    "DONE",
    "BLOCKED",
}

def ensure_schema(db_path):
    with connect(db_path) as con:
        con.executescript(SCHEMA)

def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)

def _sha_text(value):
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()

def _candidate_hash(candidate):
    fields = {
        "extraction_id": candidate["extraction_id"],
        "project_id": candidate["project_id"],
        "document_id": candidate["document_id"],
        "record_type": candidate["record_type"],
        "source_page": candidate["source_page"],
        "source_quote": candidate["source_quote"],
        "source_text_sha256": candidate["source_text_sha256"],
        "candidate_subject": candidate["candidate_subject"],
        "candidate_action": candidate["candidate_action"],
        "candidate_trigger_or_due": candidate.get("candidate_trigger_or_due"),
        "rule_id": candidate["rule_id"],
    }
    return _sha_text(json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False))

def _table_exists(con, name):
    return bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone())

def _record_snapshot(row):
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "record_type": row["record_type"],
        "title": row["title"],
        "description": row["description"],
        "due_date": row["due_date"],
        "owner": row["owner"],
        "status": row["status"],
        "verification_status": row["verification_status"],
        "source_page": row["source_page"],
        "source_section": row["source_section"],
        "source_quote": row["source_quote"],
        "source_text_sha256": row["source_text_sha256"],
    }

def _candidate_snapshot(row):
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "record_type": row["record_type"],
        "review_status": row["review_status"],
        "reviewer": row["reviewer"],
        "reviewed_at": row["reviewed_at"],
        "review_notes": row["review_notes"],
        "promoted_record_id": row["promoted_record_id"],
        "candidate_sha256": row["candidate_sha256"],
        "source_page": row["source_page"],
        "source_text_sha256": row["source_text_sha256"],
    }

def _source_integrity_for_record(con, record):
    result = {
        "status": "UNLINKED",
        "candidate_id": None,
        "candidate_hash_ok": None,
        "page_hash_ok": None,
        "candidate_page_hash_link_ok": None,
    }

    if not _table_exists(con, "ga_candidates"):
        return result

    candidate = con.execute(
        """SELECT * FROM ga_candidates
           WHERE promoted_record_id=? AND project_id=?
           ORDER BY id DESC LIMIT 1""",
        (record["id"], record["project_id"]),
    ).fetchone()
    if not candidate:
        return result

    candidate = dict(candidate)
    result["candidate_id"] = candidate["id"]
    result["candidate_hash_ok"] = _candidate_hash(candidate) == candidate["candidate_sha256"]

    page = con.execute(
        """SELECT * FROM ga_pages
           WHERE extraction_id=? AND page_number=?""",
        (candidate["extraction_id"], candidate["source_page"]),
    ).fetchone()

    if page:
        page = dict(page)
        actual_page_hash = _sha_text(page["text"])
        result["page_hash_ok"] = actual_page_hash == page["text_sha256"]
        result["candidate_page_hash_link_ok"] = (
            candidate["source_text_sha256"] == page["text_sha256"]
        )
    else:
        result["page_hash_ok"] = False
        result["candidate_page_hash_link_ok"] = False

    if all([
        result["candidate_hash_ok"],
        result["page_hash_ok"],
        result["candidate_page_hash_link_ok"],
    ]):
        result["status"] = "PASS"
    else:
        result["status"] = "FAIL"

    return result

def list_operational_records(db_path, project_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            """SELECT * FROM obligations
               WHERE project_id=?
               ORDER BY record_type,title,id""",
            (project_id,),
        ).fetchall()]

def get_operational_record(db_path, record_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM obligations WHERE id=?",
            (record_id,),
        ).fetchone()
        return dict(row) if row else None

def list_finalized_candidates(db_path, project_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            """SELECT c.*,
                      o.title AS promoted_title,
                      o.status AS promoted_status,
                      o.verification_status AS promoted_verification_status
               FROM ga_candidates c
               LEFT JOIN obligations o ON o.id=c.promoted_record_id
               WHERE c.project_id=?
                 AND c.review_status IN ('APPROVED','REJECTED')
               ORDER BY c.source_page,c.id""",
            (project_id,),
        ).fetchall()]

def edit_operational_record(
    db_path,
    record_id,
    actor,
    reason,
    changes,
    confirm_source_immutable=False,
):
    ensure_schema(db_path)
    actor = (actor or "").strip()
    reason = (reason or "").strip()

    if not actor:
        raise ValueError("ACTOR_REQUIRED")
    if not reason:
        raise ValueError("CORRECTION_REASON_REQUIRED")
    if not confirm_source_immutable:
        raise ValueError("SOURCE_IMMUTABILITY_CONFIRMATION_REQUIRED")

    unknown = set(changes or {}) - EDITABLE_RECORD_FIELDS
    if unknown:
        raise ValueError("IMMUTABLE_OR_UNKNOWN_FIELDS: " + ",".join(sorted(unknown)))

    with connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM obligations WHERE id=?",
            (record_id,),
        ).fetchone()
        if not row:
            raise ValueError("OPERATIONAL_RECORD_NOT_FOUND")
        record = dict(row)
        before = _record_snapshot(record)

        source_integrity = _source_integrity_for_record(con, record)
        if source_integrity["status"] == "FAIL":
            raise ValueError("SOURCE_INTEGRITY_CHECK_FAILED")

        next_values = {
            field: record[field]
            for field in EDITABLE_RECORD_FIELDS
        }

        for field, value in (changes or {}).items():
            if isinstance(value, str):
                value = value.strip()
            if field in {"owner", "due_date"} and value == "":
                value = None
            next_values[field] = value

        if not next_values["title"]:
            raise ValueError("TITLE_REQUIRED")
        if next_values["status"] not in ALLOWED_RECORD_STATUS:
            raise ValueError("INVALID_RECORD_STATUS")
        if next_values["due_date"]:
            try:
                date.fromisoformat(str(next_values["due_date"]))
            except Exception as exc:
                raise ValueError("DUE_DATE_MUST_BE_ISO_YYYY_MM_DD") from exc

        changed_fields = [
            field for field in EDITABLE_RECORD_FIELDS
            if next_values[field] != record[field]
        ]
        if not changed_fields:
            raise ValueError("NO_CHANGES")

        con.execute(
            """UPDATE obligations
               SET title=?,description=?,due_date=?,owner=?,status=?
               WHERE id=?""",
            (
                next_values["title"],
                next_values["description"],
                next_values["due_date"],
                next_values["owner"],
                next_values["status"],
                record_id,
            ),
        )
        updated = dict(con.execute(
            "SELECT * FROM obligations WHERE id=?",
            (record_id,),
        ).fetchone())
        after = _record_snapshot(updated)

        # Source identity is deliberately immutable.
        for field in [
            "source_page",
            "source_section",
            "source_quote",
            "source_text_sha256",
            "verification_status",
        ]:
            if before[field] != after[field]:
                raise RuntimeError("IMMUTABLE_SOURCE_OR_VERIFICATION_FIELD_CHANGED")

        cur = con.execute(
            """INSERT INTO human_change_events(
               project_id,entity_type,entity_id,action,actor,reason,
               before_json,after_json,source_integrity_json,
               requires_graph_rebuild,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record["project_id"],
                "OBLIGATION",
                record_id,
                "RECORD_EDIT",
                actor,
                reason,
                _json(before),
                _json(after),
                _json({
                    **source_integrity,
                    "changed_fields": sorted(changed_fields),
                    "immutable_source_preserved": True,
                }),
                1,
                now(),
            ),
        )
        event_id = cur.lastrowid

        audit(
            con,
            record["project_id"],
            "HUMAN_OPERATIONAL_RECORD_EDITED",
            _json({
                "record_id": record_id,
                "actor": actor,
                "reason": reason,
                "changed_fields": sorted(changed_fields),
                "change_event_id": event_id,
            }),
            "OBLIGATION",
            record_id,
        )
        return {
            "event_id": event_id,
            "record_id": record_id,
            "changed_fields": sorted(changed_fields),
            "requires_graph_rebuild": True,
        }

def reopen_candidate(
    db_path,
    candidate_id,
    actor,
    reason,
    confirm_effect=False,
):
    ensure_schema(db_path)
    actor = (actor or "").strip()
    reason = (reason or "").strip()

    if not actor:
        raise ValueError("ACTOR_REQUIRED")
    if not reason:
        raise ValueError("REOPEN_REASON_REQUIRED")
    if not confirm_effect:
        raise ValueError("REOPEN_EFFECT_CONFIRMATION_REQUIRED")

    with connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM ga_candidates WHERE id=?",
            (candidate_id,),
        ).fetchone()
        if not row:
            raise ValueError("CANDIDATE_NOT_FOUND")
        candidate = dict(row)

        if candidate["review_status"] not in {"APPROVED", "REJECTED"}:
            raise ValueError("CANDIDATE_NOT_FINALIZED")

        if _candidate_hash(candidate) != candidate["candidate_sha256"]:
            raise ValueError("CANDIDATE_INTEGRITY_MISMATCH")

        before = {
            "candidate": _candidate_snapshot(candidate),
            "record": None,
        }

        promoted = None
        if candidate.get("promoted_record_id") is not None:
            record_row = con.execute(
                """SELECT * FROM obligations
                   WHERE id=? AND project_id=?""",
                (candidate["promoted_record_id"], candidate["project_id"]),
            ).fetchone()
            if not record_row:
                raise ValueError("PROMOTED_RECORD_NOT_FOUND")
            promoted = dict(record_row)
            before["record"] = _record_snapshot(promoted)

            source_integrity = _source_integrity_for_record(con, promoted)
            if source_integrity["status"] != "PASS":
                raise ValueError("SOURCE_INTEGRITY_CHECK_FAILED")

            con.execute(
                """UPDATE obligations
                   SET verification_status='UNVERIFIED',
                       status='BLOCKED'
                   WHERE id=?""",
                (promoted["id"],),
            )
        else:
            source_integrity = {
                "status": "NOT_APPLICABLE_REJECTED_CANDIDATE",
                "candidate_id": candidate_id,
            }

        con.execute(
            """UPDATE ga_candidates
               SET review_status='NEEDS_CLARIFICATION',
                   reviewer=?,
                   reviewed_at=?,
                   review_notes=?
               WHERE id=?""",
            (actor, now(), "REOPENED: " + reason, candidate_id),
        )

        candidate_after = dict(con.execute(
            "SELECT * FROM ga_candidates WHERE id=?",
            (candidate_id,),
        ).fetchone())
        record_after = None
        if promoted:
            record_after = _record_snapshot(dict(con.execute(
                "SELECT * FROM obligations WHERE id=?",
                (promoted["id"],),
            ).fetchone()))

        after = {
            "candidate": _candidate_snapshot(candidate_after),
            "record": record_after,
        }

        cur = con.execute(
            """INSERT INTO human_change_events(
               project_id,entity_type,entity_id,action,actor,reason,
               before_json,after_json,source_integrity_json,
               requires_graph_rebuild,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                candidate["project_id"],
                "GA_CANDIDATE",
                candidate_id,
                "CANDIDATE_REOPEN",
                actor,
                reason,
                _json(before),
                _json(after),
                _json({
                    **source_integrity,
                    "approved_record_temporarily_unverified": promoted is not None,
                    "promoted_record_id": candidate.get("promoted_record_id"),
                }),
                1,
                now(),
            ),
        )
        event_id = cur.lastrowid

        audit(
            con,
            candidate["project_id"],
            "GA_CANDIDATE_REOPENED",
            _json({
                "candidate_id": candidate_id,
                "promoted_record_id": candidate.get("promoted_record_id"),
                "actor": actor,
                "reason": reason,
                "change_event_id": event_id,
            }),
            "GA_CANDIDATE",
            candidate_id,
        )

        return {
            "event_id": event_id,
            "candidate_id": candidate_id,
            "promoted_record_id": candidate.get("promoted_record_id"),
            "review_status": "NEEDS_CLARIFICATION",
            "requires_graph_rebuild": True,
        }

def list_change_events(db_path, project_id, limit=250):
    ensure_schema(db_path)
    limit = max(1, min(int(limit), 1000))
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            """SELECT * FROM human_change_events
               WHERE project_id=?
               ORDER BY id DESC LIMIT ?""",
            (project_id, limit),
        ).fetchall()]

def corrections_after_latest_graph(db_path, project_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        latest_change = con.execute(
            """SELECT MAX(created_at) AS ts
               FROM human_change_events
               WHERE project_id=? AND requires_graph_rebuild=1""",
            (project_id,),
        ).fetchone()["ts"]

        if not latest_change:
            return False

        if not _table_exists(con, "operational_graph_runs"):
            return True

        latest_graph = con.execute(
            """SELECT MAX(created_at) AS ts
               FROM operational_graph_runs
               WHERE project_id=?""",
            (project_id,),
        ).fetchone()["ts"]

        return latest_graph is None or latest_change > latest_graph