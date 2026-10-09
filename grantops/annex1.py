from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re

from .db import connect, now, audit

PARSER_VERSION = "annex1-v1.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS annex1_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    extraction_id INTEGER NOT NULL REFERENCES ga_extractions(id) ON DELETE CASCADE,
    parser_version TEXT NOT NULL,
    status TEXT NOT NULL,
    source_page_from INTEGER,
    source_page_to INTEGER,
    work_package_count INTEGER NOT NULL DEFAULT 0,
    deliverable_count INTEGER NOT NULL DEFAULT 0,
    milestone_count INTEGER NOT NULL DEFAULT 0,
    reporting_period_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_annex1_runs_project
ON annex1_runs(project_id, extraction_id, created_at);

CREATE TABLE IF NOT EXISTS annex1_work_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES annex1_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    wp_code TEXT NOT NULL,
    name TEXT NOT NULL,
    lead_beneficiary TEXT,
    start_month INTEGER,
    end_month INTEGER,
    source_page INTEGER NOT NULL,
    source_quote TEXT NOT NULL,
    source_text_sha256 TEXT NOT NULL,
    entity_sha256 TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'PROPOSED',
    created_at TEXT NOT NULL,
    UNIQUE(run_id, wp_code)
);

CREATE TABLE IF NOT EXISTS annex1_deliverables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES annex1_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    deliverable_code TEXT NOT NULL,
    name TEXT NOT NULL,
    work_package_code TEXT,
    lead_beneficiary TEXT,
    due_month INTEGER,
    deliverable_type TEXT,
    dissemination_level TEXT,
    source_page INTEGER NOT NULL,
    source_quote TEXT NOT NULL,
    source_text_sha256 TEXT NOT NULL,
    entity_sha256 TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'PROPOSED',
    created_at TEXT NOT NULL,
    UNIQUE(run_id, deliverable_code)
);

CREATE TABLE IF NOT EXISTS annex1_milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES annex1_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    milestone_code TEXT NOT NULL,
    milestone_number INTEGER NOT NULL,
    name TEXT NOT NULL,
    work_package_codes_json TEXT NOT NULL,
    lead_beneficiary TEXT,
    means_of_verification TEXT,
    due_month INTEGER,
    source_page INTEGER NOT NULL,
    source_quote TEXT NOT NULL,
    source_text_sha256 TEXT NOT NULL,
    entity_sha256 TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'PROPOSED',
    created_at TEXT NOT NULL,
    UNIQUE(run_id, milestone_code)
);

CREATE TABLE IF NOT EXISTS annex1_reporting_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES annex1_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    rp_code TEXT NOT NULL,
    rp_number INTEGER NOT NULL,
    month_from INTEGER NOT NULL,
    month_to INTEGER NOT NULL,
    report_type TEXT,
    report_deadline_rule TEXT,
    source_page INTEGER NOT NULL,
    source_quote TEXT NOT NULL,
    source_text_sha256 TEXT NOT NULL,
    entity_sha256 TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'PROPOSED',
    created_at TEXT NOT NULL,
    UNIQUE(run_id, rp_code)
);

CREATE INDEX IF NOT EXISTS idx_annex1_wp_run ON annex1_work_packages(run_id, wp_code);
CREATE INDEX IF NOT EXISTS idx_annex1_del_run ON annex1_deliverables(run_id, deliverable_code);
CREATE INDEX IF NOT EXISTS idx_annex1_ms_run ON annex1_milestones(run_id, milestone_code);
CREATE INDEX IF NOT EXISTS idx_annex1_rp_run ON annex1_reporting_periods(run_id, rp_code);
"""

def ensure_schema(db_path):
    with connect(db_path) as con:
        con.executescript(SCHEMA)

def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()

def _lines(value: str):
    out = []
    for raw in (value or "").replace("\r", "\n").split("\n"):
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if line:
            out.append(line)
    return out

def _entity_hash(kind: str, *parts) -> str:
    payload = "|".join([kind] + [str(p or "") for p in parts])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _canon_deliverable_id(value: str):
    if not value:
        return None
    x = value.upper().replace(" ", "")
    # pypdf often renders digit 1 as lower-case/upper-case L in these tables.
    x = re.sub(r"(?<=D)[LI](?=[.\dLI])", "1", x)
    x = re.sub(r"(?<=\.)[LI](?=\d|$)", "1", x)
    m = re.search(r"D(\d+)\.(\d+)", x)
    return f"D{m.group(1)}.{m.group(2)}" if m else None

def _annex1_bounds(pages):
    """Locate the structural Annex 1 section conservatively.

    Prefer the actual LIST OF WORK PACKAGES section instead of early body
    references such as "Annex 1 Description of the action" in the agreement
    composition or legal clauses.
    """
    start = None
    end = None

    # First pass: strongest structural anchor.
    for p in pages:
        t = _norm(p["text"]).upper()
        if "LIST OF WORK PACKAGES" in t:
            start = p["page_number"]
            break

    # Fallback only if the structural anchor is unavailable. Ignore early legal
    # references by requiring the latter part of the document.
    if start is None:
        for p in pages:
            t = _norm(p["text"]).upper()
            if p["page_number"] >= 50 and "ANNEX 1" in t and "DESCRIPTION OF THE ACTION" in t:
                start = p["page_number"]
                break

    if start is None:
        return None, None

    for p in pages:
        if p["page_number"] <= start:
            continue
        t = _norm(p["text"]).upper()
        # Annex 2 marks the end of the project-description structure.
        if re.search(r"\bANNEX\s+2\b", t) and "ESTIMATED BUDGET" in t:
            end = p["page_number"] - 1
            break

    if end is None:
        end = max(p["page_number"] for p in pages)
    return start, end

def _parse_wp_page(page):
    flat = _norm(page["text"])
    # Detail block is much safer than the summary table: it carries explicit labels.
    pat = re.compile(
        r"Work Package Number\s+(WP\d+)\s+"
        r"Lead Beneficiary\s+(.+?)\s+"
        r"Work Package Name\s+(.+?)\s+"
        r"Start Month\s+(\d+)\s+End Month\s+(\d+)",
        re.I,
    )
    rows = []
    for m in pat.finditer(flat):
        wp = m.group(1).upper()
        lead = _norm(m.group(2))
        name = _norm(m.group(3))
        start_month = int(m.group(4))
        end_month = int(m.group(5))
        quote = m.group(0)
        rows.append({
            "wp_code": wp,
            "name": name,
            "lead_beneficiary": lead,
            "start_month": start_month,
            "end_month": end_month,
            "source_page": page["page_number"],
            "source_quote": quote,
            "source_text_sha256": page["text_sha256"],
            "entity_sha256": _entity_hash("WP", wp, name, lead, start_month, end_month, page["text_sha256"]),
        })
    return rows

def _parse_deliverable_page(page):
    flat = _norm(page["text"])
    # Normalize common D1.1 OCR/text-extraction artefacts without changing source quote.
    matchable = re.sub(r"\bD\s*[lI]\s*\.\s*[lI]\b", "D1.1", flat, flags=re.I)

    pat = re.compile(
        r"Deliverable Number\s+(D[\dIl]+\s*\.\s*[\dIl]+)\s+"
        r"Lead Beneficiary\s+(.+?)\s+"
        r"Deliverable Name\s+(.+?)\s+"
        r"Type\s+(.+?)\s+"
        r"Dissemination Level\s+(.+?)\s+"
        r"Due Date\s*\(month\)\s+(\d+)\s+"
        r"Work Package No\s+(WP\d+)",
        re.I,
    )

    rows = []
    for m in pat.finditer(matchable):
        did = _canon_deliverable_id(m.group(1))
        if not did:
            continue
        lead = _norm(m.group(2))
        name = _norm(m.group(3))
        dtype = _norm(m.group(4))
        dissemination = _norm(m.group(5))
        due = int(m.group(6))
        wp = m.group(7).upper()
        quote = m.group(0)
        rows.append({
            "deliverable_code": did,
            "name": name,
            "work_package_code": wp,
            "lead_beneficiary": lead,
            "due_month": due,
            "deliverable_type": dtype,
            "dissemination_level": dissemination,
            "source_page": page["page_number"],
            "source_quote": quote,
            "source_text_sha256": page["text_sha256"],
            "entity_sha256": _entity_hash("DEL", did, name, wp, lead, due, page["text_sha256"]),
        })
    return rows

def _parse_milestone_page(page):
    ls = _lines(page["text"])
    upper = [x.upper() for x in ls]
    if not any("LIST OF MILESTONES" in x for x in upper):
        return []

    start = next(i for i, x in enumerate(upper) if "LIST OF MILESTONES" in x)
    end = len(ls)
    for i in range(start + 1, len(ls)):
        if "LIST OF CRITICAL RISKS" in upper[i]:
            end = i
            break

    section = ls[start:end]
    # Rows start "1 Name...", "2 Name...". Lead-beneficiary lines such as
    # "1 - UPCE ..." are deliberately excluded by the negative lookahead.
    starts = []
    for i, line in enumerate(section):
        m = re.match(r"^(\d{1,3})\s+(?!-)([A-Za-z].*)$", line)
        if m:
            num = int(m.group(1))
            if 1 <= num <= 99:
                starts.append((i, num))

    rows = []
    # Keep only a natural increasing milestone sequence to avoid table/header noise.
    filtered = []
    expected = 1
    for idx, num in starts:
        if num == expected:
            filtered.append((idx, num))
            expected += 1
    for n, (idx, num) in enumerate(filtered):
        stop = filtered[n + 1][0] if n + 1 < len(filtered) else len(section)
        group_lines = section[idx:stop]
        group = _norm(" ".join(group_lines))
        m0 = re.match(r"^(\d{1,3})\s+(.+)$", group)
        if not m0:
            continue
        body = m0.group(2)

        wp_match = re.search(r"\bWP\d+\b", body, re.I)
        if not wp_match:
            continue
        name = _norm(body[:wp_match.start()])
        wp_codes = []
        for wp in re.findall(r"\bWP\d+\b", body, re.I):
            wp = wp.upper()
            if wp not in wp_codes:
                wp_codes.append(wp)

        lead_match = re.search(r"\b(\d+\s*-\s*[A-Z][A-Z0-9_-]+)\b", body)
        lead = _norm(lead_match.group(1)) if lead_match else None

        # Due month is the final standalone integer in the grouped row.
        nums = [int(x) for x in re.findall(r"(?<![A-Za-z.])\b(\d{1,3})\b(?!\s*-)", body)]
        due = nums[-1] if nums else None

        means = None
        if lead_match:
            tail = body[lead_match.end():]
            if due is not None:
                tail = re.sub(rf"\b{due}\s*$", "", tail).strip()
            means = _norm(tail) or None

        code = f"M{num}"
        rows.append({
            "milestone_code": code,
            "milestone_number": num,
            "name": name,
            "work_package_codes": wp_codes,
            "lead_beneficiary": lead,
            "means_of_verification": means,
            "due_month": due,
            "source_page": page["page_number"],
            "source_quote": group,
            "source_text_sha256": page["text_sha256"],
            "entity_sha256": _entity_hash("MS", code, name, json.dumps(wp_codes), lead, due, page["text_sha256"]),
        })
    return rows

def _parse_reporting_period_page(page):
    flat = _norm(page["text"])
    if "Reporting periods" not in flat or "RP No" not in flat:
        return []

    pat = re.compile(
        r"\b(\d+)\s+(\d+)\s+(\d+)\s+Periodic report\s+"
        r"(.+?)(?=(?:\b\d+\s+\d+\s+\d+\s+Periodic report\b)|Prefinancing payments|Reporting and payment modalities|$)",
        re.I,
    )
    rows = []
    for m in pat.finditer(flat):
        num = int(m.group(1))
        month_from = int(m.group(2))
        month_to = int(m.group(3))
        tail = _norm(m.group(4))
        deadline_match = re.search(
            r"(\d+)\s+days?\s+after\s+end\s+of\s+reporting\s+period",
            tail,
            re.I,
        )
        if not deadline_match:
            # pypdf can interleave an adjacent payment column inside the phrase:
            # "60 days after end Interim payment 90 days from of reporting period".
            # Keep the window bounded and require both semantic anchors.
            deadline_match = re.search(
                r"(\d+)\s+days?\s+after\s+end\b.{0,120}?\bof\s+reporting\s+period",
                tail,
                re.I | re.S,
            )
        deadline = (
            f"{deadline_match.group(1)} days after end of reporting period"
            if deadline_match else None
        )
        code = f"RP{num}"
        quote = m.group(0)
        rows.append({
            "rp_code": code,
            "rp_number": num,
            "month_from": month_from,
            "month_to": month_to,
            "report_type": "Periodic report",
            "report_deadline_rule": deadline,
            "source_page": page["page_number"],
            "source_quote": quote,
            "source_text_sha256": page["text_sha256"],
            "entity_sha256": _entity_hash("RP", code, month_from, month_to, deadline, page["text_sha256"]),
        })
    return rows

def _dedupe(rows, key):
    out = []
    seen = set()
    for row in rows:
        value = row[key]
        if value in seen:
            continue
        seen.add(value)
        out.append(row)
    return out

def parse_extraction(db_path, extraction_id: int):
    ensure_schema(db_path)
    with connect(db_path) as con:
        ext = con.execute(
            "SELECT * FROM ga_extractions WHERE id=?",
            (extraction_id,),
        ).fetchone()
        if not ext:
            raise ValueError("EXTRACTION_NOT_FOUND")

        pages = [
            dict(r) for r in con.execute(
                "SELECT page_number, text_sha256, text FROM ga_pages WHERE extraction_id=? ORDER BY page_number",
                (extraction_id,),
            )
        ]
        if not pages:
            raise ValueError("EXTRACTION_HAS_NO_PAGES")

        start_page, end_page = _annex1_bounds(pages)
        if start_page is None:
            raise ValueError("ANNEX1_NOT_DETECTED")

        scoped = [p for p in pages if start_page <= p["page_number"] <= end_page]

        wps = []
        dels = []
        milestones = []
        reporting = []

        # Work packages/deliverables/milestones are Annex 1 structures.
        for p in scoped:
            wps.extend(_parse_wp_page(p))
            dels.extend(_parse_deliverable_page(p))
            milestones.extend(_parse_milestone_page(p))

        # Reporting periods live in the Data Sheet, not Annex 1. Parse all pages.
        for p in pages:
            reporting.extend(_parse_reporting_period_page(p))

        wps = _dedupe(wps, "wp_code")
        dels = _dedupe(dels, "deliverable_code")
        milestones = _dedupe(milestones, "milestone_code")
        reporting = _dedupe(reporting, "rp_code")

        created = now()
        cur = con.execute(
            """
            INSERT INTO annex1_runs(
                project_id, extraction_id, parser_version, status,
                source_page_from, source_page_to,
                work_package_count, deliverable_count, milestone_count, reporting_period_count,
                created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ext["project_id"], extraction_id, PARSER_VERSION, "PROPOSED",
                start_page, end_page,
                len(wps), len(dels), len(milestones), len(reporting),
                created,
            ),
        )
        run_id = cur.lastrowid

        for x in wps:
            con.execute(
                """
                INSERT INTO annex1_work_packages(
                    run_id, project_id, wp_code, name, lead_beneficiary,
                    start_month, end_month, source_page, source_quote,
                    source_text_sha256, entity_sha256, review_status, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id, ext["project_id"], x["wp_code"], x["name"], x["lead_beneficiary"],
                    x["start_month"], x["end_month"], x["source_page"], x["source_quote"],
                    x["source_text_sha256"], x["entity_sha256"], "PROPOSED", created,
                ),
            )

        for x in dels:
            con.execute(
                """
                INSERT INTO annex1_deliverables(
                    run_id, project_id, deliverable_code, name, work_package_code,
                    lead_beneficiary, due_month, deliverable_type, dissemination_level,
                    source_page, source_quote, source_text_sha256, entity_sha256,
                    review_status, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id, ext["project_id"], x["deliverable_code"], x["name"], x["work_package_code"],
                    x["lead_beneficiary"], x["due_month"], x["deliverable_type"], x["dissemination_level"],
                    x["source_page"], x["source_quote"], x["source_text_sha256"], x["entity_sha256"],
                    "PROPOSED", created,
                ),
            )

        for x in milestones:
            con.execute(
                """
                INSERT INTO annex1_milestones(
                    run_id, project_id, milestone_code, milestone_number, name,
                    work_package_codes_json, lead_beneficiary, means_of_verification,
                    due_month, source_page, source_quote, source_text_sha256,
                    entity_sha256, review_status, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id, ext["project_id"], x["milestone_code"], x["milestone_number"], x["name"],
                    json.dumps(x["work_package_codes"]), x["lead_beneficiary"], x["means_of_verification"],
                    x["due_month"], x["source_page"], x["source_quote"], x["source_text_sha256"],
                    x["entity_sha256"], "PROPOSED", created,
                ),
            )

        for x in reporting:
            con.execute(
                """
                INSERT INTO annex1_reporting_periods(
                    run_id, project_id, rp_code, rp_number, month_from, month_to,
                    report_type, report_deadline_rule, source_page, source_quote,
                    source_text_sha256, entity_sha256, review_status, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id, ext["project_id"], x["rp_code"], x["rp_number"], x["month_from"], x["month_to"],
                    x["report_type"], x["report_deadline_rule"], x["source_page"], x["source_quote"],
                    x["source_text_sha256"], x["entity_sha256"], "PROPOSED", created,
                ),
            )

        audit(
            con,
            ext["project_id"],
            "ANNEX1_STRUCTURE_PARSED",
            json.dumps({
                "parser_version": PARSER_VERSION,
                "extraction_id": extraction_id,
                "work_packages": len(wps),
                "deliverables": len(dels),
                "milestones": len(milestones),
                "reporting_periods": len(reporting),
            }),
            "ANNEX1_RUN",
            run_id,
        )

        return run_summary_in_connection(con, run_id)

def latest_run_for_extraction(db_path, extraction_id: int):
    ensure_schema(db_path)
    with connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM annex1_runs WHERE extraction_id=? ORDER BY id DESC LIMIT 1",
            (extraction_id,),
        ).fetchone()
        return dict(row) if row else None

def run_summary_in_connection(con, run_id):
    run = con.execute("SELECT * FROM annex1_runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        return None
    return dict(run)

def run_summary(db_path, run_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        return run_summary_in_connection(con, run_id)

def list_work_packages(db_path, run_id):
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM annex1_work_packages WHERE run_id=? ORDER BY CAST(SUBSTR(wp_code,3) AS INTEGER)",
            (run_id,),
        )]

def list_deliverables(db_path, run_id):
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM annex1_deliverables WHERE run_id=? ORDER BY deliverable_code",
            (run_id,),
        )]

def list_milestones(db_path, run_id):
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM annex1_milestones WHERE run_id=? ORDER BY milestone_number",
            (run_id,),
        )]

def list_reporting_periods(db_path, run_id):
    with connect(db_path) as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM annex1_reporting_periods WHERE run_id=? ORDER BY rp_number",
            (run_id,),
        )]