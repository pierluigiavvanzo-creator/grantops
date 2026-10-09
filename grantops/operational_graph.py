from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
import hashlib
import json
import re

from .db import connect, now, audit

GRAPH_VERSION = "opgraph-v1.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS operational_graph_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    annex1_run_id INTEGER REFERENCES annex1_runs(id) ON DELETE SET NULL,
    graph_version TEXT NOT NULL,
    status TEXT NOT NULL,
    project_start_date TEXT,
    project_end_date TEXT,
    structural_node_count INTEGER NOT NULL DEFAULT 0,
    verified_obligation_count INTEGER NOT NULL DEFAULT 0,
    evidence_requirement_count INTEGER NOT NULL DEFAULT 0,
    evidence_item_count INTEGER NOT NULL DEFAULT 0,
    edge_count INTEGER NOT NULL DEFAULT 0,
    deadline_count INTEGER NOT NULL DEFAULT 0,
    resolved_deadline_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_operational_graph_runs_project
ON operational_graph_runs(project_id, created_at);

CREATE TABLE IF NOT EXISTS operational_graph_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES operational_graph_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    node_key TEXT NOT NULL,
    node_type TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_id INTEGER,
    title TEXT NOT NULL,
    owner TEXT,
    verification_status TEXT NOT NULL,
    source_page INTEGER,
    source_section TEXT,
    source_quote TEXT,
    source_text_sha256 TEXT,
    source_entity_sha256 TEXT,
    metadata_json TEXT NOT NULL,
    node_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, node_key)
);

CREATE INDEX IF NOT EXISTS idx_operational_graph_nodes_run
ON operational_graph_nodes(run_id, node_type, node_key);

CREATE TABLE IF NOT EXISTS operational_graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES operational_graph_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_node_key TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    to_node_key TEXT NOT NULL,
    basis TEXT NOT NULL,
    edge_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, from_node_key, relation_type, to_node_key)
);

CREATE INDEX IF NOT EXISTS idx_operational_graph_edges_run
ON operational_graph_edges(run_id, relation_type);

CREATE TABLE IF NOT EXISTS operational_graph_deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES operational_graph_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    node_key TEXT NOT NULL,
    deadline_kind TEXT NOT NULL,
    relative_rule TEXT,
    trigger_key TEXT,
    trigger_date TEXT,
    resolved_date TEXT,
    resolution_status TEXT NOT NULL,
    basis TEXT NOT NULL,
    deadline_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, node_key, deadline_kind, relative_rule)
);

CREATE INDEX IF NOT EXISTS idx_operational_graph_deadlines_run
ON operational_graph_deadlines(run_id, resolution_status, resolved_date);
"""

def ensure_schema(db_path):
    with connect(db_path) as con:
        con.executescript(SCHEMA)

def _sha(payload) -> str:
    if not isinstance(payload, str):
        payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _norm(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()

def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)

def _parse_iso_date(value):
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])

def _add_months(d: date, months: int) -> date:
    index = (d.month - 1) + months
    year = d.year + index // 12
    month = index % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)

def project_month_start(project_start: date, month_number: int) -> date:
    if month_number < 1:
        raise ValueError("MONTH_NUMBER_MUST_BE_POSITIVE")
    return _add_months(project_start, month_number - 1)

def project_month_end(project_start: date, month_number: int) -> date:
    if month_number < 1:
        raise ValueError("MONTH_NUMBER_MUST_BE_POSITIVE")
    return _add_months(project_start, month_number) - timedelta(days=1)

def _table_exists(con, table_name):
    return bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone())

def _find_evidence_table(con):
    required = {"id", "obligation_id", "label", "evidence_type", "status"}
    for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        name = row["name"] if hasattr(row, "keys") else row[0]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            continue
        cols = {
            r["name"] if hasattr(r, "keys") else r[1]
            for r in con.execute(f'PRAGMA table_info("{name}")').fetchall()
        }
        if required.issubset(cols):
            return name, cols
    return None, set()

def _latest_annex1_run(con, project_id):
    if not _table_exists(con, "annex1_runs"):
        return None
    row = con.execute(
        "SELECT * FROM annex1_runs WHERE project_id=? ORDER BY id DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    return dict(row) if row else None

def _insert_node(con, run_id, project_id, node):
    payload = {
        "node_key": node["node_key"],
        "node_type": node["node_type"],
        "source_kind": node["source_kind"],
        "source_id": node.get("source_id"),
        "title": node["title"],
        "owner": node.get("owner"),
        "verification_status": node["verification_status"],
        "source_page": node.get("source_page"),
        "source_section": node.get("source_section"),
        "source_quote": node.get("source_quote"),
        "source_text_sha256": node.get("source_text_sha256"),
        "source_entity_sha256": node.get("source_entity_sha256"),
        "metadata": node.get("metadata", {}),
    }
    con.execute(
        """INSERT INTO operational_graph_nodes(
           run_id,project_id,node_key,node_type,source_kind,source_id,title,owner,
           verification_status,source_page,source_section,source_quote,
           source_text_sha256,source_entity_sha256,metadata_json,node_sha256,created_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id, project_id, node["node_key"], node["node_type"], node["source_kind"],
            node.get("source_id"), node["title"], node.get("owner"),
            node["verification_status"], node.get("source_page"), node.get("source_section"),
            node.get("source_quote"), node.get("source_text_sha256"),
            node.get("source_entity_sha256"), _json(node.get("metadata", {})),
            _sha(payload), now(),
        ),
    )

def _insert_edge(con, run_id, project_id, from_key, relation, to_key, basis):
    payload = {"from": from_key, "relation": relation, "to": to_key, "basis": basis}
    con.execute(
        """INSERT OR IGNORE INTO operational_graph_edges(
           run_id,project_id,from_node_key,relation_type,to_node_key,basis,edge_sha256,created_at
           ) VALUES(?,?,?,?,?,?,?,?)""",
        (run_id, project_id, from_key, relation, to_key, basis, _sha(payload), now()),
    )

def _insert_deadline(
    con, run_id, project_id, node_key, kind, relative_rule, resolved_date,
    status, basis, trigger_key=None, trigger_date=None
):
    payload = {
        "node_key": node_key, "kind": kind, "relative_rule": relative_rule,
        "trigger_key": trigger_key, "trigger_date": trigger_date,
        "resolved_date": resolved_date, "status": status, "basis": basis,
    }
    con.execute(
        """INSERT OR IGNORE INTO operational_graph_deadlines(
           run_id,project_id,node_key,deadline_kind,relative_rule,trigger_key,
           trigger_date,resolved_date,resolution_status,basis,deadline_sha256,created_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id, project_id, node_key, kind, relative_rule, trigger_key,
            trigger_date, resolved_date, status, basis, _sha(payload), now(),
        ),
    )

def _party_key(raw):
    return "PARTY:" + _sha(_norm(raw))[:16]

def _safe_page(value):
    if value is None:
        return None
    m = re.search(r"\d+", str(value))
    return int(m.group(0)) if m else None

def _load_structural(con, annex1_run_id):
    return {
        "wps": [dict(r) for r in con.execute(
            "SELECT * FROM annex1_work_packages WHERE run_id=? ORDER BY wp_code", (annex1_run_id,)
        )],
        "deliverables": [dict(r) for r in con.execute(
            "SELECT * FROM annex1_deliverables WHERE run_id=? ORDER BY deliverable_code", (annex1_run_id,)
        )],
        "milestones": [dict(r) for r in con.execute(
            "SELECT * FROM annex1_milestones WHERE run_id=? ORDER BY milestone_number", (annex1_run_id,)
        )],
        "reporting": [dict(r) for r in con.execute(
            "SELECT * FROM annex1_reporting_periods WHERE run_id=? ORDER BY rp_number", (annex1_run_id,)
        )],
    }

def _verified_operational_records(con, project_id):
    if not _table_exists(con, "obligations"):
        return []
    return [dict(r) for r in con.execute(
        """SELECT * FROM obligations
           WHERE project_id=? AND verification_status='HUMAN_VERIFIED'
           AND record_type IN ('OBLIGATION','EVIDENCE_REQUIREMENT')
           ORDER BY id""",
        (project_id,),
    ).fetchall()]

def _promoted_trigger_map(con, project_id):
    if not (_table_exists(con, "ga_candidates") and _table_exists(con, "ga_candidate_context")):
        return {}
    rows = con.execute(
        """SELECT c.promoted_record_id, ctx.trigger_text
           FROM ga_candidates c
           JOIN ga_candidate_context ctx ON ctx.candidate_id=c.id
           WHERE c.project_id=? AND c.promoted_record_id IS NOT NULL""",
        (project_id,),
    ).fetchall()
    return {
        r["promoted_record_id"]: r["trigger_text"]
        for r in rows
        if r["promoted_record_id"] is not None and r["trigger_text"]
    }

def _pending_evidence_candidate_count(con, project_id):
    if not _table_exists(con, "ga_candidates"):
        return 0
    row = con.execute(
        """SELECT COUNT(*) AS n FROM ga_candidates
           WHERE project_id=? AND record_type='EVIDENCE_REQUIREMENT'
           AND review_status!='APPROVED'""",
        (project_id,),
    ).fetchone()
    return int(row["n"]) if row else 0

def build_graph(db_path, project_id: int):
    ensure_schema(db_path)
    with connect(db_path) as con:
        project_row = con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project_row:
            raise ValueError("PROJECT_NOT_FOUND")
        project = dict(project_row)

        annex_run = _latest_annex1_run(con, project_id)
        if not annex_run:
            raise ValueError("ANNEX1_RUN_REQUIRED")

        structural = _load_structural(con, annex_run["id"])
        verified_records = _verified_operational_records(con, project_id)
        trigger_map = _promoted_trigger_map(con, project_id)
        structural_count = sum(len(v) for v in structural.values())
        evidence_req_count = sum(r["record_type"] == "EVIDENCE_REQUIREMENT" for r in verified_records)
        verified_obligation_count = sum(r["record_type"] == "OBLIGATION" for r in verified_records)

        cur = con.execute(
            """INSERT INTO operational_graph_runs(
               project_id,annex1_run_id,graph_version,status,project_start_date,project_end_date,
               structural_node_count,verified_obligation_count,evidence_requirement_count,
               evidence_item_count,edge_count,deadline_count,resolved_deadline_count,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                project_id, annex_run["id"], GRAPH_VERSION, "PROPOSED",
                project.get("start_date"), project.get("end_date"),
                structural_count, verified_obligation_count, evidence_req_count,
                0, 0, 0, 0, now(),
            ),
        )
        run_id = cur.lastrowid
        project_key = f"PROJECT:{project_id}"
        _insert_node(con, run_id, project_id, {
            "node_key": project_key,
            "node_type": "PROJECT",
            "source_kind": "PROJECT_METADATA",
            "source_id": project_id,
            "title": f'{project.get("code") or "Project"} — {project.get("title") or ""}'.strip(" —"),
            "owner": project.get("coordinator"),
            "verification_status": "PROJECT_METADATA",
            "metadata": {
                "code": project.get("code"),
                "programme": project.get("programme"),
                "start_date": project.get("start_date"),
                "end_date": project.get("end_date"),
                "coordinator": project.get("coordinator"),
            },
        })

        project_start = _parse_iso_date(project.get("start_date"))
        node_keys = {project_key}
        parties = {}

        def add_party(raw):
            raw = _norm(raw)
            if not raw:
                return None
            key = _party_key(raw)
            if key not in parties:
                parties[key] = raw
                _insert_node(con, run_id, project_id, {
                    "node_key": key,
                    "node_type": "RESPONSIBLE_PARTY",
                    "source_kind": "ANNEX1_EXPLICIT_LEAD",
                    "source_id": None,
                    "title": raw,
                    "owner": None,
                    "verification_status": "SOURCE_EXPLICIT",
                    "metadata": {"raw_lead_beneficiary": raw},
                })
                node_keys.add(key)
                _insert_edge(
                    con, run_id, project_id, project_key, "HAS_RESPONSIBLE_PARTY", key,
                    "Distinct explicit Lead Beneficiary value in Annex 1",
                )
            return key

        for x in structural["wps"]:
            key = f'WP:{x["wp_code"]}'
            node_keys.add(key)
            _insert_node(con, run_id, project_id, {
                "node_key": key,
                "node_type": "WORK_PACKAGE",
                "source_kind": "ANNEX1_STRUCTURAL_ENTITY",
                "source_id": x["id"],
                "title": f'{x["wp_code"]} — {x["name"]}',
                "owner": x.get("lead_beneficiary"),
                "verification_status": x.get("review_status") or "PROPOSED",
                "source_page": x.get("source_page"),
                "source_quote": x.get("source_quote"),
                "source_text_sha256": x.get("source_text_sha256"),
                "source_entity_sha256": x.get("entity_sha256"),
                "metadata": {
                    "wp_code": x["wp_code"], "name": x["name"],
                    "lead_beneficiary": x.get("lead_beneficiary"),
                    "start_month": x.get("start_month"), "end_month": x.get("end_month"),
                },
            })
            _insert_edge(con, run_id, project_id, project_key, "CONTAINS", key, "Annex 1 Work Package")
            party = add_party(x.get("lead_beneficiary"))
            if party:
                _insert_edge(con, run_id, project_id, key, "LEAD_BENEFICIARY", party, "Annex 1 Lead Beneficiary")

            for kind, month_no, basis in [
                ("WP_START", x.get("start_month"), "Project start + Work Package start month"),
                ("WP_END", x.get("end_month"), "Project month end for Work Package end month"),
            ]:
                if month_no:
                    if project_start:
                        resolved = project_month_start(project_start, int(month_no)) if kind == "WP_START" else project_month_end(project_start, int(month_no))
                        _insert_deadline(
                            con, run_id, project_id, key, kind, f"M{month_no}",
                            resolved.isoformat(), "RESOLVED", basis,
                            trigger_key=project_key, trigger_date=project_start.isoformat(),
                        )
                    else:
                        _insert_deadline(
                            con, run_id, project_id, key, kind, f"M{month_no}",
                            None, "MISSING_PROJECT_START_DATE", basis, trigger_key=project_key,
                        )

        for x in structural["deliverables"]:
            key = f'DEL:{x["deliverable_code"]}'
            node_keys.add(key)
            _insert_node(con, run_id, project_id, {
                "node_key": key,
                "node_type": "DELIVERABLE",
                "source_kind": "ANNEX1_STRUCTURAL_ENTITY",
                "source_id": x["id"],
                "title": f'{x["deliverable_code"]} — {x["name"]}',
                "owner": x.get("lead_beneficiary"),
                "verification_status": x.get("review_status") or "PROPOSED",
                "source_page": x.get("source_page"),
                "source_quote": x.get("source_quote"),
                "source_text_sha256": x.get("source_text_sha256"),
                "source_entity_sha256": x.get("entity_sha256"),
                "metadata": {
                    "deliverable_code": x["deliverable_code"], "name": x["name"],
                    "work_package_code": x.get("work_package_code"),
                    "lead_beneficiary": x.get("lead_beneficiary"),
                    "due_month": x.get("due_month"),
                    "deliverable_type": x.get("deliverable_type"),
                    "dissemination_level": x.get("dissemination_level"),
                },
            })
            wp_key = f'WP:{x["work_package_code"]}' if x.get("work_package_code") else None
            if wp_key and wp_key in node_keys:
                _insert_edge(con, run_id, project_id, wp_key, "HAS_DELIVERABLE", key, "Annex 1 Work Package No")
            party = add_party(x.get("lead_beneficiary"))
            if party:
                _insert_edge(con, run_id, project_id, key, "LEAD_BENEFICIARY", party, "Annex 1 Lead Beneficiary")

            due_month = x.get("due_month")
            if due_month:
                if project_start:
                    resolved = project_month_end(project_start, int(due_month))
                    _insert_deadline(
                        con, run_id, project_id, key, "DELIVERABLE_DUE", f"M{due_month}",
                        resolved.isoformat(), "RESOLVED",
                        "Project month end derived from explicit Annex 1 due month",
                        trigger_key=project_key, trigger_date=project_start.isoformat(),
                    )
                else:
                    _insert_deadline(
                        con, run_id, project_id, key, "DELIVERABLE_DUE", f"M{due_month}",
                        None, "MISSING_PROJECT_START_DATE",
                        "Explicit Annex 1 due month; project start unavailable",
                        trigger_key=project_key,
                    )

        for x in structural["milestones"]:
            key = f'MS:{x["milestone_code"]}'
            node_keys.add(key)
            wp_codes = json.loads(x.get("work_package_codes_json") or "[]")
            _insert_node(con, run_id, project_id, {
                "node_key": key,
                "node_type": "MILESTONE",
                "source_kind": "ANNEX1_STRUCTURAL_ENTITY",
                "source_id": x["id"],
                "title": f'{x["milestone_code"]} — {x["name"]}',
                "owner": x.get("lead_beneficiary"),
                "verification_status": x.get("review_status") or "PROPOSED",
                "source_page": x.get("source_page"),
                "source_quote": x.get("source_quote"),
                "source_text_sha256": x.get("source_text_sha256"),
                "source_entity_sha256": x.get("entity_sha256"),
                "metadata": {
                    "milestone_code": x["milestone_code"], "name": x["name"],
                    "work_package_codes": wp_codes,
                    "lead_beneficiary": x.get("lead_beneficiary"),
                    "means_of_verification": x.get("means_of_verification"),
                    "due_month": x.get("due_month"),
                },
            })
            _insert_edge(con, run_id, project_id, project_key, "CONTAINS", key, "Annex 1 Milestone")
            for wp in wp_codes:
                wp_key = f"WP:{wp}"
                if wp_key in node_keys:
                    _insert_edge(con, run_id, project_id, key, "RELATES_TO", wp_key, "Annex 1 Work Package No")
            party = add_party(x.get("lead_beneficiary"))
            if party:
                _insert_edge(con, run_id, project_id, key, "LEAD_BENEFICIARY", party, "Annex 1 Lead Beneficiary")
            due_month = x.get("due_month")
            if due_month:
                if project_start:
                    resolved = project_month_end(project_start, int(due_month))
                    _insert_deadline(
                        con, run_id, project_id, key, "MILESTONE_DUE", f"M{due_month}",
                        resolved.isoformat(), "RESOLVED",
                        "Project month end derived from explicit Annex 1 milestone due month",
                        trigger_key=project_key, trigger_date=project_start.isoformat(),
                    )
                else:
                    _insert_deadline(
                        con, run_id, project_id, key, "MILESTONE_DUE", f"M{due_month}",
                        None, "MISSING_PROJECT_START_DATE",
                        "Explicit Annex 1 milestone due month; project start unavailable",
                        trigger_key=project_key,
                    )

        rp_ranges = []
        for x in structural["reporting"]:
            key = f'RP:{x["rp_code"]}'
            node_keys.add(key)
            _insert_node(con, run_id, project_id, {
                "node_key": key,
                "node_type": "REPORTING_PERIOD",
                "source_kind": "GRANT_DATA_SHEET_STRUCTURAL_ENTITY",
                "source_id": x["id"],
                "title": f'{x["rp_code"]} — M{x["month_from"]} to M{x["month_to"]}',
                "owner": None,
                "verification_status": x.get("review_status") or "PROPOSED",
                "source_page": x.get("source_page"),
                "source_quote": x.get("source_quote"),
                "source_text_sha256": x.get("source_text_sha256"),
                "source_entity_sha256": x.get("entity_sha256"),
                "metadata": {
                    "rp_code": x["rp_code"], "month_from": x["month_from"],
                    "month_to": x["month_to"], "report_type": x.get("report_type"),
                    "report_deadline_rule": x.get("report_deadline_rule"),
                },
            })
            _insert_edge(con, run_id, project_id, project_key, "CONTAINS", key, "Grant Agreement Data Sheet reporting period")
            rp_ranges.append((int(x["month_from"]), int(x["month_to"]), key))

            for kind, month_no, basis in [
                ("REPORTING_PERIOD_START", x["month_from"], "Project month start for reporting period"),
                ("REPORTING_PERIOD_END", x["month_to"], "Project month end for reporting period"),
            ]:
                if project_start:
                    resolved = project_month_start(project_start, int(month_no)) if kind == "REPORTING_PERIOD_START" else project_month_end(project_start, int(month_no))
                    _insert_deadline(
                        con, run_id, project_id, key, kind, f"M{month_no}",
                        resolved.isoformat(), "RESOLVED", basis,
                        trigger_key=project_key, trigger_date=project_start.isoformat(),
                    )
                else:
                    _insert_deadline(
                        con, run_id, project_id, key, kind, f"M{month_no}",
                        None, "MISSING_PROJECT_START_DATE", basis, trigger_key=project_key,
                    )

            # Prefer the normalized field. If missing, recover only from this
            # reporting-period entity's own authoritative source quote.
            #
            # PDF table extraction can interleave the adjacent payment column,
            # e.g.:
            # "60 days after end Interim payment 90 days from of reporting period"
            #
            # The tolerant regex allows a bounded amount of intervening text
            # between "end" and "of reporting period". It still requires both
            # anchors and never supplies a default number of days.
            def _report_deadline_days(text):
                if not text:
                    return None
                strict = re.search(
                    r"\b(\d+)\s+days?\s+after\s+end\s+of\s+reporting\s+period\b",
                    text,
                    re.I,
                )
                if strict:
                    return int(strict.group(1))
                wrapped = re.search(
                    r"\b(\d+)\s+days?\s+after\s+end\b.{0,120}?\bof\s+reporting\s+period\b",
                    text,
                    re.I | re.S,
                )
                return int(wrapped.group(1)) if wrapped else None

            rule = x.get("report_deadline_rule")
            rule_source = "NORMALIZED_FIELD"
            days = _report_deadline_days(rule)

            if days is None:
                days = _report_deadline_days(x.get("source_quote") or "")
                if days is not None:
                    rule = f"{days} days after end of reporting period"
                    rule_source = "SOURCE_QUOTE_TABLE_WRAP_REPAIR"

            if days is not None:
                if project_start:
                    period_end = project_month_end(project_start, int(x["month_to"]))
                    report_due = period_end + timedelta(days=days)
                    _insert_deadline(
                        con, run_id, project_id, key, "REPORT_DUE", rule,
                        report_due.isoformat(), "RESOLVED",
                        f"Explicit reporting deadline rule from {rule_source} applied to resolved reporting-period end",
                        trigger_key=f"{key}:REPORTING_PERIOD_END",
                        trigger_date=period_end.isoformat(),
                    )
                else:
                    _insert_deadline(
                        con, run_id, project_id, key, "REPORT_DUE", rule,
                        None, "MISSING_PROJECT_START_DATE",
                        f"Explicit reporting deadline rule from {rule_source}; reporting-period end unresolved",
                        trigger_key=f"{key}:REPORTING_PERIOD_END",
                    )

        for x in structural["deliverables"]:
            due = x.get("due_month")
            if due:
                for lo, hi, rp_key in rp_ranges:
                    if lo <= int(due) <= hi:
                        _insert_edge(
                            con, run_id, project_id, f'DEL:{x["deliverable_code"]}',
                            "DUE_IN", rp_key,
                            f'Explicit due month M{due} falls inside reporting period M{lo}-M{hi}',
                        )
                        break

        for x in structural["milestones"]:
            due = x.get("due_month")
            if due:
                for lo, hi, rp_key in rp_ranges:
                    if lo <= int(due) <= hi:
                        _insert_edge(
                            con, run_id, project_id, f'MS:{x["milestone_code"]}',
                            "DUE_IN", rp_key,
                            f'Explicit due month M{due} falls inside reporting period M{lo}-M{hi}',
                        )
                        break

        obligation_nodes = {}
        evidence_nodes = {}
        for r in verified_records:
            prefix = "EVIDREQ" if r["record_type"] == "EVIDENCE_REQUIREMENT" else "OBL"
            key = f"{prefix}:{r['id']}"
            node_keys.add(key)
            _insert_node(con, run_id, project_id, {
                "node_key": key,
                "node_type": r["record_type"],
                "source_kind": "HUMAN_VERIFIED_OPERATIONAL_RECORD",
                "source_id": r["id"],
                "title": r["title"],
                "owner": r.get("owner"),
                "verification_status": r["verification_status"],
                "source_page": _safe_page(r.get("source_page")),
                "source_section": r.get("source_section"),
                "source_quote": r.get("source_quote"),
                "source_text_sha256": r.get("source_text_sha256"),
                "metadata": {
                    "status": r.get("status"), "due_date": r.get("due_date"),
                    "description": r.get("description"),
                },
            })
            _insert_edge(
                con, run_id, project_id, project_key, "CONTAINS", key,
                "Human-verified operational record only",
            )
            if r["record_type"] == "EVIDENCE_REQUIREMENT":
                evidence_nodes[r["id"]] = (key, r)
            else:
                obligation_nodes[r["id"]] = (key, r)

            due_date = r.get("due_date")
            if due_date:
                try:
                    resolved = _parse_iso_date(due_date)
                except Exception:
                    resolved = None
                _insert_deadline(
                    con, run_id, project_id, key, "ABSOLUTE_OPERATIONAL_DUE",
                    None, resolved.isoformat() if resolved else None,
                    "RESOLVED" if resolved else "INVALID_STORED_DATE",
                    "Human-verified operational record due_date",
                )
            elif r["id"] in trigger_map:
                trig = trigger_map[r["id"]]
                _insert_deadline(
                    con, run_id, project_id, key, "EVENT_RELATIVE",
                    trig, None, "AWAITING_TRIGGER",
                    "Human-verified obligation has relative trigger but trigger date is not known",
                    trigger_key="EXTERNAL_EVENT",
                )

        for _, (evid_key, evid) in evidence_nodes.items():
            for _, (obl_key, obl) in obligation_nodes.items():
                same_page = _safe_page(evid.get("source_page")) == _safe_page(obl.get("source_page"))
                same_hash = (
                    evid.get("source_text_sha256")
                    and evid.get("source_text_sha256") == obl.get("source_text_sha256")
                )
                if same_page and same_hash:
                    _insert_edge(
                        con, run_id, project_id, evid_key, "EVIDENCE_FOR", obl_key,
                        "Human-verified evidence requirement shares authoritative source page and source-text hash",
                    )

        evidence_table, evidence_cols = _find_evidence_table(con)
        evidence_item_count = 0
        if evidence_table:
            extra_cols = [c for c in ["location", "notes"] if c in evidence_cols]
            select_cols = ["id", "obligation_id", "label", "evidence_type", "status"] + extra_cols
            query = f"""
                SELECT {", ".join("e." + c for c in select_cols)}
                FROM "{evidence_table}" e
                JOIN obligations o ON o.id=e.obligation_id
                WHERE o.project_id=?
                ORDER BY e.id
            """
            for row in con.execute(query, (project_id,)).fetchall():
                item = dict(row)
                target = obligation_nodes.get(item["obligation_id"]) or evidence_nodes.get(item["obligation_id"])
                if not target:
                    continue
                target_key, _ = target
                key = f'EVIDENCE:{item["id"]}'
                _insert_node(con, run_id, project_id, {
                    "node_key": key,
                    "node_type": "EVIDENCE_ITEM",
                    "source_kind": "EVIDENCE_REGISTER",
                    "source_id": item["id"],
                    "title": item["label"],
                    "owner": None,
                    "verification_status": item["status"],
                    "metadata": {
                        "evidence_type": item["evidence_type"], "status": item["status"],
                        "location": item.get("location"), "notes": item.get("notes"),
                        "obligation_id": item["obligation_id"],
                    },
                })
                _insert_edge(
                    con, run_id, project_id, target_key, "SUPPORTED_BY", key,
                    "Existing evidence register item linked to human-verified operational record",
                )
                evidence_item_count += 1

        edge_count = con.execute(
            "SELECT COUNT(*) AS n FROM operational_graph_edges WHERE run_id=?", (run_id,)
        ).fetchone()["n"]
        deadline_row = con.execute(
            """SELECT COUNT(*) AS n,
                      SUM(CASE WHEN resolution_status='RESOLVED' THEN 1 ELSE 0 END) AS resolved
               FROM operational_graph_deadlines WHERE run_id=?""",
            (run_id,),
        ).fetchone()
        deadline_count = int(deadline_row["n"] or 0)
        resolved_count = int(deadline_row["resolved"] or 0)

        con.execute(
            """UPDATE operational_graph_runs
               SET evidence_item_count=?,edge_count=?,deadline_count=?,resolved_deadline_count=?
               WHERE id=?""",
            (evidence_item_count, edge_count, deadline_count, resolved_count, run_id),
        )

        audit(
            con, project_id, "OPERATIONAL_GRAPH_BUILT",
            _json({
                "graph_version": GRAPH_VERSION,
                "annex1_run_id": annex_run["id"],
                "structural_nodes": structural_count,
                "verified_obligations": verified_obligation_count,
                "verified_evidence_requirements": evidence_req_count,
                "evidence_items": evidence_item_count,
                "edges": edge_count,
                "deadlines": deadline_count,
                "resolved_deadlines": resolved_count,
                "pending_evidence_candidates_excluded": _pending_evidence_candidate_count(con, project_id),
            }),
            "OPERATIONAL_GRAPH_RUN", run_id,
        )
        return graph_summary_in_connection(con, run_id)

def latest_graph_run(db_path, project_id: int):
    ensure_schema(db_path)
    with connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM operational_graph_runs WHERE project_id=? ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        return dict(row) if row else None

def graph_summary_in_connection(con, run_id):
    run = con.execute("SELECT * FROM operational_graph_runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        return None
    run = dict(run)
    run["node_type_counts"] = {
        r["node_type"]: r["n"] for r in con.execute(
            "SELECT node_type, COUNT(*) AS n FROM operational_graph_nodes WHERE run_id=? GROUP BY node_type",
            (run_id,),
        )
    }
    run["edge_type_counts"] = {
        r["relation_type"]: r["n"] for r in con.execute(
            "SELECT relation_type, COUNT(*) AS n FROM operational_graph_edges WHERE run_id=? GROUP BY relation_type",
            (run_id,),
        )
    }
    run["deadline_status_counts"] = {
        r["resolution_status"]: r["n"] for r in con.execute(
            "SELECT resolution_status, COUNT(*) AS n FROM operational_graph_deadlines WHERE run_id=? GROUP BY resolution_status",
            (run_id,),
        )
    }
    run["node_count"] = sum(run["node_type_counts"].values())
    return run

def graph_summary(db_path, run_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        return graph_summary_in_connection(con, run_id)

def list_nodes(db_path, run_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            """SELECT * FROM operational_graph_nodes
               WHERE run_id=?
               ORDER BY CASE node_type
                   WHEN 'PROJECT' THEN 0
                   WHEN 'WORK_PACKAGE' THEN 1
                   WHEN 'DELIVERABLE' THEN 2
                   WHEN 'MILESTONE' THEN 3
                   WHEN 'REPORTING_PERIOD' THEN 4
                   WHEN 'OBLIGATION' THEN 5
                   WHEN 'EVIDENCE_REQUIREMENT' THEN 6
                   WHEN 'EVIDENCE_ITEM' THEN 7
                   ELSE 8 END, node_key""",
            (run_id,),
        )]

def list_edges(db_path, run_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            """SELECT e.*,
                      fn.title AS from_title, fn.node_type AS from_type,
                      tn.title AS to_title, tn.node_type AS to_type
               FROM operational_graph_edges e
               LEFT JOIN operational_graph_nodes fn
                 ON fn.run_id=e.run_id AND fn.node_key=e.from_node_key
               LEFT JOIN operational_graph_nodes tn
                 ON tn.run_id=e.run_id AND tn.node_key=e.to_node_key
               WHERE e.run_id=?
               ORDER BY e.relation_type,e.from_node_key,e.to_node_key""",
            (run_id,),
        )]

def list_deadlines(db_path, run_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            """SELECT d.*, n.title AS node_title, n.node_type
               FROM operational_graph_deadlines d
               JOIN operational_graph_nodes n
                 ON n.run_id=d.run_id AND n.node_key=d.node_key
               WHERE d.run_id=?
               ORDER BY CASE WHEN d.resolved_date IS NULL THEN 1 ELSE 0 END,
                        d.resolved_date,d.node_key,d.deadline_kind""",
            (run_id,),
        )]

def evidence_safety_summary(db_path, project_id, run_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        pending = _pending_evidence_candidate_count(con, project_id)
        graph_verified = con.execute(
            """SELECT COUNT(*) AS n FROM operational_graph_nodes
               WHERE run_id=? AND node_type='EVIDENCE_REQUIREMENT'
               AND verification_status='HUMAN_VERIFIED'""",
            (run_id,),
        ).fetchone()["n"]
        evidence_items = con.execute(
            """SELECT COUNT(*) AS n FROM operational_graph_nodes
               WHERE run_id=? AND node_type='EVIDENCE_ITEM'""",
            (run_id,),
        ).fetchone()["n"]
        unsupported = con.execute(
            """SELECT COUNT(*) AS n FROM operational_graph_nodes
               WHERE run_id=? AND node_type='EVIDENCE_REQUIREMENT'
               AND verification_status!='HUMAN_VERIFIED'""",
            (run_id,),
        ).fetchone()["n"]
        return {
            "verified_evidence_requirements": int(graph_verified or 0),
            "evidence_items": int(evidence_items or 0),
            "pending_unverified_evidence_candidates_excluded": int(pending or 0),
            "non_verified_evidence_nodes_in_graph": int(unsupported or 0),
        }