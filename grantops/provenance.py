from __future__ import annotations

import hashlib
import json
import re

from .db import connect, now, audit

PROVENANCE_VERSION = "provenance-v1.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS provenance_review_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    graph_run_id INTEGER NOT NULL REFERENCES operational_graph_runs(id) ON DELETE CASCADE,
    provenance_version TEXT NOT NULL,
    status TEXT NOT NULL,
    node_item_count INTEGER NOT NULL DEFAULT 0,
    node_complete_count INTEGER NOT NULL DEFAULT 0,
    deadline_item_count INTEGER NOT NULL DEFAULT 0,
    deadline_complete_count INTEGER NOT NULL DEFAULT 0,
    edge_count INTEGER NOT NULL DEFAULT 0,
    orphan_edge_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_provenance_review_runs_project
ON provenance_review_runs(project_id, graph_run_id, created_at);

CREATE TABLE IF NOT EXISTS provenance_review_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES provenance_review_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    item_key TEXT NOT NULL,
    item_type TEXT NOT NULL,
    graph_node_key TEXT,
    graph_deadline_id INTEGER,
    source_strategy TEXT NOT NULL,
    document_id INTEGER,
    document_filename TEXT,
    document_sha256 TEXT,
    extraction_id INTEGER,
    page_number INTEGER,
    page_text_sha256 TEXT,
    source_quote TEXT,
    provenance_status TEXT NOT NULL,
    chain_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    provenance_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, item_key)
);

CREATE INDEX IF NOT EXISTS idx_provenance_review_items_run
ON provenance_review_items(run_id, item_type, provenance_status);
"""

SOURCE_BEARING_NODE_TYPES = {
    "WORK_PACKAGE",
    "DELIVERABLE",
    "MILESTONE",
    "REPORTING_PERIOD",
    "OBLIGATION",
    "EVIDENCE_REQUIREMENT",
    "EVIDENCE_ITEM",
}

STRUCTURAL_NODE_TYPES = {
    "WORK_PACKAGE",
    "DELIVERABLE",
    "MILESTONE",
    "REPORTING_PERIOD",
}

def ensure_schema(db_path):
    with connect(db_path) as con:
        con.executescript(SCHEMA)

def _sha(payload):
    if not isinstance(payload, str):
        payload = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)

def _table_exists(con, name):
    return bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone())

def _columns(con, name):
    if not _table_exists(con, name):
        return set()
    return {r["name"] for r in con.execute(f'PRAGMA table_info("{name}")').fetchall()}

def _document_row(con, document_id):
    if document_id is None or not _table_exists(con, "grant_documents"):
        return None
    row = con.execute(
        "SELECT * FROM grant_documents WHERE id=?",
        (document_id,),
    ).fetchone()
    return dict(row) if row else None

def _filename(doc):
    if not doc:
        return None
    return doc.get("filename") or doc.get("name") or f'document-{doc.get("id")}'

def _doc_sha(doc):
    if not doc:
        return None
    return doc.get("sha256") or doc.get("document_sha256")

def _page_row(con, extraction_id, page_number):
    if not extraction_id or page_number is None:
        return None
    row = con.execute(
        """SELECT * FROM ga_pages
           WHERE extraction_id=? AND page_number=?""",
        (extraction_id, page_number),
    ).fetchone()
    return dict(row) if row else None

def _base_chain(project_id, document, extraction, page, node):
    chain = [
        {
            "layer": "PROJECT",
            "ref": f"project:{project_id}",
        }
    ]
    if document:
        chain.append({
            "layer": "DOCUMENT",
            "ref": f'document:{document.get("id")}',
            "filename": _filename(document),
            "sha256": _doc_sha(document),
        })
    if extraction:
        chain.append({
            "layer": "EXTRACTION",
            "ref": f'extraction:{extraction.get("id")}',
            "document_sha256": extraction.get("document_sha256"),
            "backend": extraction.get("backend"),
            "backend_version": extraction.get("backend_version"),
        })
    if page:
        chain.append({
            "layer": "PAGE",
            "ref": f'page:{page.get("page_number")}',
            "text_sha256": page.get("text_sha256"),
        })
    if node:
        chain.append({
            "layer": "GRAPH_NODE",
            "ref": node.get("node_key"),
            "node_type": node.get("node_type"),
            "source_kind": node.get("source_kind"),
            "source_id": node.get("source_id"),
        })
    return chain

def _structural_source(con, graph_run, node):
    annex_run = con.execute(
        "SELECT * FROM annex1_runs WHERE id=?",
        (graph_run["annex1_run_id"],),
    ).fetchone()
    if not annex_run:
        return None

    annex_run = dict(annex_run)
    extraction = con.execute(
        "SELECT * FROM ga_extractions WHERE id=?",
        (annex_run["extraction_id"],),
    ).fetchone()
    if not extraction:
        return None
    extraction = dict(extraction)

    document = _document_row(con, extraction["document_id"])
    page = _page_row(con, extraction["id"], node["source_page"])

    warnings = []
    if not document:
        warnings.append("DOCUMENT_NOT_FOUND")
    if not page:
        warnings.append("PAGE_NOT_FOUND")
    elif node.get("source_text_sha256") and page.get("text_sha256") != node.get("source_text_sha256"):
        warnings.append("PAGE_HASH_MISMATCH")

    complete = (
        document is not None
        and extraction is not None
        and page is not None
        and bool(node.get("source_quote"))
        and bool(node.get("source_text_sha256"))
        and page.get("text_sha256") == node.get("source_text_sha256")
    )

    return {
        "source_strategy": "ANNEX1_RUN_CHAIN",
        "document": document,
        "extraction": extraction,
        "page": page,
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "warnings": warnings,
    }

def _candidate_source_for_record(con, project_id, obligation_id):
    if not _table_exists(con, "ga_candidates"):
        return None

    row = con.execute(
        """SELECT *
           FROM ga_candidates
           WHERE project_id=? AND promoted_record_id=?
           ORDER BY id DESC LIMIT 1""",
        (project_id, obligation_id),
    ).fetchone()
    if row:
        candidate = dict(row)
        extraction = con.execute(
            "SELECT * FROM ga_extractions WHERE id=?",
            (candidate["extraction_id"],),
        ).fetchone()
        extraction = dict(extraction) if extraction else None
        document = _document_row(con, candidate["document_id"])
        page = _page_row(con, candidate["extraction_id"], candidate["source_page"])
        warnings = []
        if not document:
            warnings.append("DOCUMENT_NOT_FOUND")
        if not extraction:
            warnings.append("EXTRACTION_NOT_FOUND")
        if not page:
            warnings.append("PAGE_NOT_FOUND")
        elif candidate.get("source_text_sha256") and page.get("text_sha256") != candidate.get("source_text_sha256"):
            warnings.append("PAGE_HASH_MISMATCH")
        return {
            "source_strategy": "PROMOTED_CANDIDATE_CHAIN",
            "document": document,
            "extraction": extraction,
            "page": page,
            "candidate": candidate,
            "status": "COMPLETE" if not warnings else "INCOMPLETE",
            "warnings": warnings,
        }

    # Conservative recovery by authoritative page hash + page number within project.
    obligation = con.execute(
        "SELECT * FROM obligations WHERE id=? AND project_id=?",
        (obligation_id, project_id),
    ).fetchone()
    if not obligation:
        return None
    obligation = dict(obligation)
    source_hash = obligation.get("source_text_sha256")
    page_match = re.search(r"\d+", str(obligation.get("source_page") or ""))
    page_number = int(page_match.group(0)) if page_match else None
    if not source_hash or page_number is None:
        return None

    matches = con.execute(
        """SELECT gp.*, ge.document_id, ge.document_sha256, ge.backend, ge.backend_version,
                  ge.status AS extraction_status
           FROM ga_pages gp
           JOIN ga_extractions ge ON ge.id=gp.extraction_id
           WHERE ge.project_id=? AND gp.page_number=? AND gp.text_sha256=?
           ORDER BY ge.id DESC""",
        (project_id, page_number, source_hash),
    ).fetchall()

    if len(matches) != 1:
        return {
            "source_strategy": "PAGE_HASH_RECOVERY",
            "document": None,
            "extraction": None,
            "page": None,
            "status": "AMBIGUOUS" if len(matches) > 1 else "INCOMPLETE",
            "warnings": ["AMBIGUOUS_PAGE_HASH_MATCH"] if len(matches) > 1 else ["NO_PAGE_HASH_MATCH"],
        }

    m = dict(matches[0])
    extraction = con.execute(
        "SELECT * FROM ga_extractions WHERE id=?",
        (m["extraction_id"],),
    ).fetchone()
    extraction = dict(extraction)
    document = _document_row(con, extraction["document_id"])
    page = _page_row(con, extraction["id"], page_number)
    return {
        "source_strategy": "PAGE_HASH_RECOVERY",
        "document": document,
        "extraction": extraction,
        "page": page,
        "status": "COMPLETE" if document and page else "INCOMPLETE",
        "warnings": [] if document and page else ["RECOVERED_CHAIN_INCOMPLETE"],
    }

def _source_for_node(con, graph_run, node):
    if node["node_type"] in STRUCTURAL_NODE_TYPES:
        return _structural_source(con, graph_run, node)

    if node["node_type"] in {"OBLIGATION", "EVIDENCE_REQUIREMENT"}:
        source = _candidate_source_for_record(
            con,
            graph_run["project_id"],
            node.get("source_id"),
        )
        if source:
            return source
        return {
            "source_strategy": "HUMAN_VERIFIED_RECORD_ONLY",
            "document": None,
            "extraction": None,
            "page": None,
            "status": "INCOMPLETE",
            "warnings": ["NO_DOCUMENT_CHAIN_FOR_VERIFIED_RECORD"],
        }

    if node["node_type"] == "EVIDENCE_ITEM":
        return {
            "source_strategy": "EVIDENCE_REGISTER_ONLY",
            "document": None,
            "extraction": None,
            "page": None,
            "status": "REGISTER_ONLY",
            "warnings": ["EVIDENCE_FILE_NOT_CRYPTOGRAPHICALLY_LINKED"],
        }

    return None

def _insert_item(
    con, run_id, project_id, item_key, item_type, graph_node_key,
    graph_deadline_id, source, source_quote, chain, status, warnings
):
    document = source.get("document") if source else None
    extraction = source.get("extraction") if source else None
    page = source.get("page") if source else None
    payload = {
        "item_key": item_key,
        "item_type": item_type,
        "graph_node_key": graph_node_key,
        "graph_deadline_id": graph_deadline_id,
        "source_strategy": source.get("source_strategy") if source else "NONE",
        "document_id": document.get("id") if document else None,
        "document_sha256": _doc_sha(document),
        "extraction_id": extraction.get("id") if extraction else None,
        "page_number": page.get("page_number") if page else None,
        "page_text_sha256": page.get("text_sha256") if page else None,
        "source_quote": source_quote,
        "status": status,
        "chain": chain,
        "warnings": warnings,
    }
    con.execute(
        """INSERT INTO provenance_review_items(
           run_id,project_id,item_key,item_type,graph_node_key,graph_deadline_id,
           source_strategy,document_id,document_filename,document_sha256,
           extraction_id,page_number,page_text_sha256,source_quote,
           provenance_status,chain_json,warnings_json,provenance_sha256,created_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id, project_id, item_key, item_type, graph_node_key, graph_deadline_id,
            source.get("source_strategy") if source else "NONE",
            document.get("id") if document else None,
            _filename(document),
            _doc_sha(document),
            extraction.get("id") if extraction else None,
            page.get("page_number") if page else None,
            page.get("text_sha256") if page else None,
            source_quote,
            status,
            _json(chain),
            _json(warnings),
            _sha(payload),
            now(),
        ),
    )

def build_provenance_review(db_path, project_id: int, graph_run_id: int | None = None):
    ensure_schema(db_path)
    with connect(db_path) as con:
        if graph_run_id is None:
            graph_row = con.execute(
                """SELECT * FROM operational_graph_runs
                   WHERE project_id=? ORDER BY id DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
        else:
            graph_row = con.execute(
                """SELECT * FROM operational_graph_runs
                   WHERE id=? AND project_id=?""",
                (graph_run_id, project_id),
            ).fetchone()

        if not graph_row:
            raise ValueError("OPERATIONAL_GRAPH_RUN_REQUIRED")
        graph_run = dict(graph_row)

        cur = con.execute(
            """INSERT INTO provenance_review_runs(
               project_id,graph_run_id,provenance_version,status,
               node_item_count,node_complete_count,deadline_item_count,
               deadline_complete_count,edge_count,orphan_edge_count,created_at
               ) VALUES(?,?,?,?,0,0,0,0,0,0,?)""",
            (project_id, graph_run["id"], PROVENANCE_VERSION, "REVIEW", now()),
        )
        run_id = cur.lastrowid

        nodes = [dict(r) for r in con.execute(
            "SELECT * FROM operational_graph_nodes WHERE run_id=? ORDER BY node_key",
            (graph_run["id"],),
        ).fetchall()]

        source_cache = {}
        node_item_count = 0
        node_complete_count = 0

        for node in nodes:
            if node["node_type"] not in SOURCE_BEARING_NODE_TYPES:
                continue
            source = _source_for_node(con, graph_run, node)
            if not source:
                continue
            source_cache[node["node_key"]] = source

            document = source.get("document")
            extraction = source.get("extraction")
            page = source.get("page")
            chain = _base_chain(project_id, document, extraction, page, node)

            status = source["status"]
            warnings = list(source.get("warnings") or [])
            source_quote = node.get("source_quote")

            if node["node_type"] in STRUCTURAL_NODE_TYPES:
                node_item_count += 1
                if status == "COMPLETE":
                    node_complete_count += 1

            _insert_item(
                con, run_id, project_id,
                f'NODE:{node["node_key"]}',
                "GRAPH_NODE",
                node["node_key"],
                None,
                source,
                source_quote,
                chain,
                status,
                warnings,
            )

        deadlines = [dict(r) for r in con.execute(
            """SELECT d.*, n.node_type, n.source_quote
               FROM operational_graph_deadlines d
               JOIN operational_graph_nodes n
                 ON n.run_id=d.run_id AND n.node_key=d.node_key
               WHERE d.run_id=? ORDER BY d.id""",
            (graph_run["id"],),
        ).fetchall()]

        deadline_item_count = 0
        deadline_complete_count = 0

        for d in deadlines:
            if d["node_type"] not in STRUCTURAL_NODE_TYPES:
                continue
            deadline_item_count += 1
            source = source_cache.get(d["node_key"])
            if source is None:
                node = next(n for n in nodes if n["node_key"] == d["node_key"])
                source = _source_for_node(con, graph_run, node)
                source_cache[d["node_key"]] = source

            document = source.get("document") if source else None
            extraction = source.get("extraction") if source else None
            page = source.get("page") if source else None
            parent_node = next(n for n in nodes if n["node_key"] == d["node_key"])
            chain = _base_chain(project_id, document, extraction, page, parent_node)
            chain.append({
                "layer": "DEADLINE",
                "ref": f'deadline:{d["id"]}',
                "deadline_kind": d["deadline_kind"],
                "relative_rule": d["relative_rule"],
                "resolved_date": d["resolved_date"],
                "resolution_status": d["resolution_status"],
                "basis": d["basis"],
            })

            warnings = list(source.get("warnings") or []) if source else ["NO_PARENT_SOURCE"]
            status = "COMPLETE_DERIVED" if source and source["status"] == "COMPLETE" else "INCOMPLETE"
            if status == "COMPLETE_DERIVED":
                deadline_complete_count += 1

            _insert_item(
                con, run_id, project_id,
                f'DEADLINE:{d["id"]}',
                "GRAPH_DEADLINE",
                d["node_key"],
                d["id"],
                source or {"source_strategy": "NONE"},
                parent_node.get("source_quote"),
                chain,
                status,
                warnings,
            )

        edge_rows = [dict(r) for r in con.execute(
            "SELECT * FROM operational_graph_edges WHERE run_id=?",
            (graph_run["id"],),
        ).fetchall()]
        node_keys = {n["node_key"] for n in nodes}
        orphan_edges = [
            e for e in edge_rows
            if e["from_node_key"] not in node_keys or e["to_node_key"] not in node_keys
        ]

        con.execute(
            """UPDATE provenance_review_runs
               SET node_item_count=?,node_complete_count=?,
                   deadline_item_count=?,deadline_complete_count=?,
                   edge_count=?,orphan_edge_count=?,
                   status=?
               WHERE id=?""",
            (
                node_item_count,
                node_complete_count,
                deadline_item_count,
                deadline_complete_count,
                len(edge_rows),
                len(orphan_edges),
                "PASS" if (
                    node_item_count == node_complete_count
                    and deadline_item_count == deadline_complete_count
                    and len(orphan_edges) == 0
                ) else "REVIEW",
                run_id,
            ),
        )

        audit(
            con,
            project_id,
            "PROVENANCE_REVIEW_BUILT",
            _json({
                "provenance_version": PROVENANCE_VERSION,
                "graph_run_id": graph_run["id"],
                "structural_node_provenance": f"{node_complete_count}/{node_item_count}",
                "structural_deadline_provenance": f"{deadline_complete_count}/{deadline_item_count}",
                "edges": len(edge_rows),
                "orphan_edges": len(orphan_edges),
            }),
            "PROVENANCE_REVIEW_RUN",
            run_id,
        )
        return review_summary_in_connection(con, run_id)

def latest_provenance_review(db_path, project_id: int):
    ensure_schema(db_path)
    with connect(db_path) as con:
        row = con.execute(
            """SELECT * FROM provenance_review_runs
               WHERE project_id=? ORDER BY id DESC LIMIT 1""",
            (project_id,),
        ).fetchone()
        return dict(row) if row else None

def review_summary_in_connection(con, run_id):
    row = con.execute(
        "SELECT * FROM provenance_review_runs WHERE id=?",
        (run_id,),
    ).fetchone()
    if not row:
        return None
    out = dict(row)
    out["status_counts"] = {
        r["provenance_status"]: r["n"]
        for r in con.execute(
            """SELECT provenance_status,COUNT(*) AS n
               FROM provenance_review_items WHERE run_id=?
               GROUP BY provenance_status""",
            (run_id,),
        ).fetchall()
    }
    out["document_count"] = con.execute(
        """SELECT COUNT(DISTINCT document_id) AS n
           FROM provenance_review_items
           WHERE run_id=? AND document_id IS NOT NULL""",
        (run_id,),
    ).fetchone()["n"]
    return out

def review_summary(db_path, run_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        return review_summary_in_connection(con, run_id)

def list_provenance_items(db_path, run_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            """SELECT * FROM provenance_review_items
               WHERE run_id=?
               ORDER BY CASE item_type WHEN 'GRAPH_NODE' THEN 0 ELSE 1 END,
                        graph_node_key,graph_deadline_id""",
            (run_id,),
        ).fetchall()]

def orphan_edge_count(db_path, graph_run_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        nodes = {
            r["node_key"] for r in con.execute(
                "SELECT node_key FROM operational_graph_nodes WHERE run_id=?",
                (graph_run_id,),
            ).fetchall()
        }
        return sum(
            1 for e in con.execute(
                "SELECT from_node_key,to_node_key FROM operational_graph_edges WHERE run_id=?",
                (graph_run_id,),
            ).fetchall()
            if e["from_node_key"] not in nodes or e["to_node_key"] not in nodes
        )