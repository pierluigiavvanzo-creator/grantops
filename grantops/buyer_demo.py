from __future__ import annotations

from datetime import date
import json
import sqlite3


STRUCTURAL_TYPES = (
    "WORK_PACKAGE",
    "DELIVERABLE",
    "MILESTONE",
    "REPORTING_PERIOD",
)

BUYER_DEADLINE_KINDS = (
    "DELIVERABLE_DUE",
    "MILESTONE_DUE",
    "REPORT_DUE",
    "REPORTING_PERIOD_END",
)


def _connect(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def _table_exists(con, name):
    return bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone())


def _scalar(con, sql, params=(), default=0):
    row = con.execute(sql, params).fetchone()
    if not row:
        return default
    value = row[0]
    return default if value is None else value


def buyer_demo_snapshot(db_path, project_id: int):
    with _connect(db_path) as con:
        project = con.execute(
            "SELECT * FROM projects WHERE id=?",
            (project_id,),
        ).fetchone()
        if not project:
            raise ValueError("PROJECT_NOT_FOUND")
        project = dict(project)

        latest_graph = None
        if _table_exists(con, "operational_graph_runs"):
            row = con.execute(
                """SELECT * FROM operational_graph_runs
                   WHERE project_id=? ORDER BY id DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
            latest_graph = dict(row) if row else None

        latest_prov = None
        if latest_graph and _table_exists(con, "provenance_review_runs"):
            row = con.execute(
                """SELECT * FROM provenance_review_runs
                   WHERE project_id=? AND graph_run_id=?
                   ORDER BY id DESC LIMIT 1""",
                (project_id, latest_graph["id"]),
            ).fetchone()
            latest_prov = dict(row) if row else None

        type_counts = {t: 0 for t in STRUCTURAL_TYPES}
        structural_nodes = []
        deadlines = []
        edges = []
        verified_obligations = 0
        verified_evidence_requirements = 0
        unverified_evidence_nodes = 0

        if latest_graph:
            rows = con.execute(
                """SELECT * FROM operational_graph_nodes
                   WHERE run_id=? ORDER BY node_type,node_key""",
                (latest_graph["id"],),
            ).fetchall()
            nodes = [dict(r) for r in rows]
            structural_nodes = [n for n in nodes if n["node_type"] in STRUCTURAL_TYPES]

            for n in structural_nodes:
                type_counts[n["node_type"]] += 1

            verified_obligations = sum(
                n["node_type"] == "OBLIGATION"
                and n["verification_status"] == "HUMAN_VERIFIED"
                for n in nodes
            )
            verified_evidence_requirements = sum(
                n["node_type"] == "EVIDENCE_REQUIREMENT"
                and n["verification_status"] == "HUMAN_VERIFIED"
                for n in nodes
            )
            unverified_evidence_nodes = sum(
                n["node_type"] == "EVIDENCE_REQUIREMENT"
                and n["verification_status"] != "HUMAN_VERIFIED"
                for n in nodes
            )

            deadlines = [dict(r) for r in con.execute(
                """SELECT d.*, n.title AS node_title, n.node_type,
                          n.owner AS node_owner, n.source_page
                   FROM operational_graph_deadlines d
                   JOIN operational_graph_nodes n
                     ON n.run_id=d.run_id AND n.node_key=d.node_key
                   WHERE d.run_id=?
                   ORDER BY CASE WHEN d.resolved_date IS NULL THEN 1 ELSE 0 END,
                            d.resolved_date,d.node_key""",
                (latest_graph["id"],),
            ).fetchall()]

            edges = [dict(r) for r in con.execute(
                """SELECT * FROM operational_graph_edges
                   WHERE run_id=? ORDER BY relation_type,from_node_key,to_node_key""",
                (latest_graph["id"],),
            ).fetchall()]

        structural_total = sum(type_counts.values())
        resolved_structural = sum(
            d["node_type"] in STRUCTURAL_TYPES and d["resolution_status"] == "RESOLVED"
            for d in deadlines
        )

        provenance_node_complete = 0
        provenance_node_total = 0
        provenance_deadline_complete = 0
        provenance_deadline_total = 0
        orphan_edges = None
        source_document_count = 0

        provenance_items = []
        if latest_prov:
            provenance_node_complete = int(latest_prov["node_complete_count"] or 0)
            provenance_node_total = int(latest_prov["node_item_count"] or 0)
            provenance_deadline_complete = int(latest_prov["deadline_complete_count"] or 0)
            provenance_deadline_total = int(latest_prov["deadline_item_count"] or 0)
            orphan_edges = int(latest_prov["orphan_edge_count"] or 0)

            provenance_items = [dict(r) for r in con.execute(
                """SELECT * FROM provenance_review_items
                   WHERE run_id=?
                   ORDER BY CASE item_type WHEN 'GRAPH_NODE' THEN 0 ELSE 1 END,
                            graph_node_key,graph_deadline_id""",
                (latest_prov["id"],),
            ).fetchall()]
            source_document_count = len({
                x["document_id"] for x in provenance_items
                if x["document_id"] is not None
            })

        latest_change_ts = None
        if _table_exists(con, "human_change_events"):
            row = con.execute(
                """SELECT MAX(created_at) AS ts
                   FROM human_change_events
                   WHERE project_id=? AND requires_graph_rebuild=1""",
                (project_id,),
            ).fetchone()
            latest_change_ts = row["ts"] if row else None

        graph_stale = bool(
            latest_change_ts
            and latest_graph
            and latest_change_ts > latest_graph["created_at"]
        )
        provenance_stale = bool(
            latest_change_ts
            and latest_prov
            and latest_change_ts > latest_prov["created_at"]
        )

        complete_provenance = bool(
            latest_prov
            and provenance_node_total > 0
            and provenance_node_complete == provenance_node_total
            and provenance_deadline_total > 0
            and provenance_deadline_complete == provenance_deadline_total
            and orphan_edges == 0
        )

        demo_ready = bool(
            latest_graph
            and structural_total > 0
            and resolved_structural > 0
            and complete_provenance
            and not graph_stale
            and not provenance_stale
            and unverified_evidence_nodes == 0
        )

        today = date.today().isoformat()
        buyer_deadlines = [
            d for d in deadlines
            if d["deadline_kind"] in BUYER_DEADLINE_KINDS
            and d["resolution_status"] == "RESOLVED"
        ]
        upcoming = [d for d in buyer_deadlines if d["resolved_date"] >= today]
        past = [d for d in buyer_deadlines if d["resolved_date"] < today]

        # Buyer demo should show upcoming first; if a historical project has no
        # future deadline left, show the most recent resolved dates as evidence.
        schedule_preview = upcoming[:10]
        if not schedule_preview:
            schedule_preview = list(reversed(past[-10:]))

        source_by_node = {}
        for item in provenance_items:
            if item["item_type"] != "GRAPH_NODE":
                continue
            if item["graph_node_key"] not in source_by_node:
                source_by_node[item["graph_node_key"]] = item

        showcase_types = {"DELIVERABLE", "MILESTONE", "REPORTING_PERIOD", "WORK_PACKAGE"}
        showcase = []
        for node in structural_nodes:
            if node["node_type"] not in showcase_types:
                continue
            source = source_by_node.get(node["node_key"])
            if not source:
                continue
            meta = json.loads(node["metadata_json"] or "{}")
            node_deadlines = [
                d for d in deadlines
                if d["node_key"] == node["node_key"]
                and d["deadline_kind"] in BUYER_DEADLINE_KINDS
                and d["resolution_status"] == "RESOLVED"
            ]
            showcase.append({
                "node_key": node["node_key"],
                "node_type": node["node_type"],
                "title": node["title"],
                "owner": node["owner"],
                "verification_status": node["verification_status"],
                "relative_due": (
                    f'M{meta.get("due_month")}'
                    if meta.get("due_month") is not None
                    else (
                        f'M{meta.get("month_from")}–M{meta.get("month_to")}'
                        if meta.get("month_from") is not None else None
                    )
                ),
                "resolved_dates": [d["resolved_date"] for d in node_deadlines],
                "document_filename": source["document_filename"],
                "document_sha256": source["document_sha256"],
                "page_number": source["page_number"],
                "page_text_sha256": source["page_text_sha256"],
                "source_quote": source["source_quote"],
                "provenance_status": source["provenance_status"],
            })

        relation_counts = {}
        for e in edges:
            relation_counts[e["relation_type"]] = relation_counts.get(e["relation_type"], 0) + 1

        return {
            "project": project,
            "demo_ready": demo_ready,
            "graph_stale": graph_stale,
            "provenance_stale": provenance_stale,
            "graph_run_id": latest_graph["id"] if latest_graph else None,
            "provenance_run_id": latest_prov["id"] if latest_prov else None,
            "structure": {
                "work_packages": type_counts["WORK_PACKAGE"],
                "deliverables": type_counts["DELIVERABLE"],
                "milestones": type_counts["MILESTONE"],
                "reporting_periods": type_counts["REPORTING_PERIOD"],
                "total": structural_total,
            },
            "deadlines": {
                "resolved_structural": resolved_structural,
                "buyer_schedule_count": len(buyer_deadlines),
                "preview": schedule_preview,
            },
            "provenance": {
                "node_complete": provenance_node_complete,
                "node_total": provenance_node_total,
                "deadline_complete": provenance_deadline_complete,
                "deadline_total": provenance_deadline_total,
                "core_complete": provenance_node_complete + provenance_deadline_complete,
                "core_total": provenance_node_total + provenance_deadline_total,
                "source_documents": source_document_count,
                "orphan_relations": orphan_edges,
                "complete": complete_provenance,
            },
            "human_control": {
                "verified_obligations": verified_obligations,
                "verified_evidence_requirements": verified_evidence_requirements,
                "unverified_evidence_nodes": unverified_evidence_nodes,
                "corrections_supported": _table_exists(con, "human_change_events"),
            },
            "relations": relation_counts,
            "showcase": showcase,
        }