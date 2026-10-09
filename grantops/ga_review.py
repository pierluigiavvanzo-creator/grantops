from __future__ import annotations

from pathlib import Path
from datetime import date
import hashlib
import json
import re

from .db import connect, now, audit

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PAGES = 250
MAX_CHARS_PER_PAGE = 200_000
MAX_TOTAL_CHARS = 8_000_000
MIN_TOTAL_TEXT_CHARS = 200
REQUIRED_PYPDF_VERSION = "6.19.0"
CONTEXT_ANALYSIS_VERSION = "context-v1.1"


CANDIDATE_TYPES = {
    "OBLIGATION",
    "DELIVERABLE",
    "MILESTONE",
    "REPORTING_PERIOD",
    "EVIDENCE_REQUIREMENT",
}

REVIEW_STATES = {
    "PENDING",
    "APPROVED",
    "REJECTED",
    "NEEDS_CLARIFICATION",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS ga_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES grant_documents(id) ON DELETE CASCADE,
    document_sha256 TEXT NOT NULL,
    backend TEXT NOT NULL,
    backend_version TEXT NOT NULL,
    extraction_mode TEXT NOT NULL,
    page_count INTEGER NOT NULL,
    total_text_chars INTEGER NOT NULL,
    empty_page_count INTEGER NOT NULL,
    ocr_used INTEGER NOT NULL DEFAULT 0,
    network_requests INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(document_id, document_sha256, status)
);

CREATE TABLE IF NOT EXISTS ga_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    extraction_id INTEGER NOT NULL REFERENCES ga_extractions(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    text_sha256 TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    text TEXT NOT NULL,
    UNIQUE(extraction_id, page_number)
);

CREATE TABLE IF NOT EXISTS ga_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    extraction_id INTEGER NOT NULL REFERENCES ga_extractions(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES grant_documents(id) ON DELETE CASCADE,
    record_type TEXT NOT NULL,
    source_page INTEGER NOT NULL,
    source_quote TEXT NOT NULL,
    source_text_sha256 TEXT NOT NULL,
    candidate_subject TEXT NOT NULL,
    candidate_action TEXT NOT NULL,
    candidate_trigger_or_due TEXT,
    rule_id TEXT NOT NULL,
    candidate_sha256 TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'PENDING',
    reviewer TEXT,
    reviewed_at TEXT,
    review_notes TEXT,
    promoted_record_id INTEGER REFERENCES obligations(id),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ga_candidates_project
ON ga_candidates(project_id, review_status, record_type);

CREATE INDEX IF NOT EXISTS idx_ga_pages_extraction
ON ga_pages(extraction_id, page_number);

CREATE TABLE IF NOT EXISTS ga_document_profiles (
    document_id INTEGER PRIMARY KEY REFERENCES grant_documents(id) ON DELETE CASCADE,
    analysis_version TEXT NOT NULL,
    document_kind TEXT NOT NULL,
    detection_basis TEXT NOT NULL,
    analyzed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ga_candidate_context (
    candidate_id INTEGER PRIMARY KEY REFERENCES ga_candidates(id) ON DELETE CASCADE,
    analysis_version TEXT NOT NULL,
    document_kind TEXT NOT NULL,
    source_article TEXT,
    source_heading TEXT,
    context_before TEXT,
    context_quote TEXT NOT NULL,
    context_after TEXT,
    applicability TEXT NOT NULL,
    trigger_text TEXT,
    context_status TEXT NOT NULL,
    promotable INTEGER NOT NULL DEFAULT 0,
    blocking_reasons_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    duplicate_of_candidate_id INTEGER REFERENCES ga_candidates(id),
    relation_type TEXT,
    analyzed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ga_candidate_context_status
ON ga_candidate_context(context_status, promotable);
"""

RULES = [
    {
        "rule_id": "R-OBL-001",
        "record_type": "OBLIGATION",
        "pattern": re.compile(
            r"\b(?P<subject>the coordinator|the beneficiary|the beneficiaries|the consortium|coordinator|beneficiary|beneficiaries|consortium)\b"
            r"(?P<middle>.{0,120}?)\b(?:must|shall|is required to|are required to)\b"
            r"(?P<action>.{3,260}?)(?:(?<=\.)|$)",
            re.I,
        ),
    },
    {
        "rule_id": "R-DEL-001",
        "record_type": "DELIVERABLE",
        "pattern": re.compile(
            r"\b(?P<id>D\d+(?:\.\d+)*)\b\s*[-:–—]\s*(?P<title>.{3,160}?)"
            r"(?:\s+\b(?:due\s*)?(?:month\s*|M)\s*(?P<due>\d+)\b|$)",
            re.I,
        ),
    },
    {
        "rule_id": "R-MIL-001",
        "record_type": "MILESTONE",
        "pattern": re.compile(
            r"\b(?P<id>MS\d+(?:\.\d+)*)\b\s*[-:–—]\s*(?P<title>.{3,160}?)"
            r"(?:\s+\b(?:due\s*)?(?:month\s*|M)\s*(?P<due>\d+)\b|$)",
            re.I,
        ),
    },
    {
        "rule_id": "R-REP-001",
        "record_type": "REPORTING_PERIOD",
        "pattern": re.compile(
            r"\breporting period\s*(?P<num>\d+)\b.{0,80}?"
            r"\b(?:month|M)\s*(?P<start>\d+)\s*(?:to|-|–|—)\s*(?:month|M)?\s*(?P<end>\d+)",
            re.I,
        ),
    },
    {
        "rule_id": "R-EVI-001",
        "record_type": "EVIDENCE_REQUIREMENT",
        "pattern": re.compile(
            r"\b(?:must|shall)\s+(?:keep|retain|maintain)\b"
            r"(?P<action>.{3,240}?)(?:(?<=\.)|$)",
            re.I,
        ),
    },
]

def ensure_schema(db_path):
    with connect(db_path) as con:
        con.executescript(SCHEMA)


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalized_lines(text: str):
    lines = []
    for raw in (text or "").replace("\r", "\n").split("\n"):
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if line:
            lines.append(line)
    return lines


def _flat_page(text: str) -> str:
    return _normalize_ws(text)


def _strong_sentence_spans(text: str):
    """Conservative sentence spans that do not split common abbreviations such as e.g."""
    text = _normalize_ws(text)
    if not text:
        return []
    # Sentence boundary only when punctuation is followed by a likely new sentence.
    boundary = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“'\[])" )
    spans = []
    start = 0
    for m in boundary.finditer(text):
        end = m.start()
        spans.append((start, end, text[start:end].strip()))
        start = m.end()
    spans.append((start, len(text), text[start:].strip()))
    return [s for s in spans if s[2]]


def _find_candidate_span(flat: str, quote: str):
    q = _normalize_ws(quote)
    if not q:
        return None
    pos = flat.lower().find(q.lower())
    if pos >= 0:
        return (pos, pos + len(q))
    # Layout extraction can split Article 25 as "2 5" etc. Fall back to a token-flexible search.
    tokens = [re.escape(t) for t in q.split() if t]
    if not tokens:
        return None
    pattern = re.compile(r"\s+".join(tokens), re.I)
    m = pattern.search(flat)
    return (m.start(), m.end()) if m else None


def _nearest_heading(page_text: str, quote: str):
    """
    Return only real structural headings preceding the candidate.

    v0.2.3a deliberately ignores body references such as
    "under Articles 11, 12, 13..." because those are citations, not the
    candidate's containing Article.
    """
    lines = _normalized_lines(page_text)
    if not lines:
        return (None, None)

    q = _normalize_ws(quote).lower()
    needle = " ".join(q.split()[:5])
    anchor = len(lines) - 1
    for i, line in enumerate(lines):
        if needle and needle in _normalize_ws(line).lower():
            anchor = i
            break

    article = None
    heading = None

    # Structural headings must BEGIN the line. Search only backwards.
    for i in range(anchor, max(-1, anchor - 45), -1):
        line = lines[i]

        am = re.match(r"^ARTICLE\s+(\d+[A-Z]?)\b(?:\s*[-–—:]\s*(.*))?$", line, re.I)
        if am:
            article = f"Article {am.group(1)}"
            heading = line
            # Some PDFs put ARTICLE 9 on one line and the title on the next.
            if not am.group(2) and i + 1 < len(lines):
                nxt = lines[i + 1]
                alpha = [ch for ch in nxt if ch.isalpha()]
                upper = [ch for ch in alpha if ch.isupper()]
                if alpha and len(nxt) <= 180 and len(upper) / len(alpha) >= 0.70:
                    heading = f"{line} — {nxt}"
            break

        # Preserve a real Section/Annex heading when no Article heading exists.
        if heading is None and re.match(r"^(SECTION|ANNEX|CHAPTER|TITLE)\b", line, re.I):
            heading = line

    return (article, heading)

def _trim_clause_at_structural_boundary(current: str, quote: str) -> str:
    """
    Keep recovered text inside the candidate's own clause.

    This prevents context leakage into the following OPTION, Article,
    Section or numbered sub-section while still allowing recovery from
    abbreviations such as "e.g.".
    """
    current = _normalize_ws(current)
    q = _normalize_ws(quote)
    if not current:
        return current

    qpos = current.lower().find(q.lower()) if q else -1
    search_from = (qpos + max(len(q), 1)) if qpos >= 0 else min(len(current), max(len(q), 1))

    boundary_patterns = [
        r"\s+\[(?:OPTION|END OPTION)\b",
        r"\s+(?=ARTICLE\s+\d+[A-Z]?\b)",
        r"\s+(?=SECTION\s+\d+\b)",
        r"\s+(?=ANNEX\s+\d+\b)",
        r"\s+(?=\d{1,2}\.\d+(?:\.\d+)?\s+[A-Z][A-Za-z])",
    ]

    cuts = []
    tail = current[search_from:]
    for pat in boundary_patterns:
        m = re.search(pat, tail, re.I)
        if m:
            cuts.append(search_from + m.start())

    if cuts:
        current = current[:min(cuts)].strip()

    return current


def _context_window(page_text: str, quote: str):
    flat = _flat_page(page_text)
    span = _find_candidate_span(flat, quote)
    if not span:
        q = _normalize_ws(quote)
        return {"before": "", "current": q, "after": "", "found": False}

    qstart, qend = span
    sentences = _strong_sentence_spans(flat)
    idx = None
    for i, (start, end, sentence) in enumerate(sentences):
        if start <= qstart < end or start < qend <= end or (qstart <= start and qend >= end):
            idx = i
            break

    if idx is None:
        current = flat[qstart:qend].strip()
        return {
            "before": flat[max(0, qstart - 350):qstart].strip(),
            "current": current,
            "after": flat[qend:qend + 500].strip(),
            "found": True,
        }

    current = _trim_clause_at_structural_boundary(sentences[idx][2], quote)
    before = sentences[idx - 1][2] if idx > 0 else ""
    after = sentences[idx + 1][2] if idx + 1 < len(sentences) else ""

    # If trimming removed the following structural block, do not re-inject it as
    # semantic trigger material. It remains visible only as neighboring context.
    return {"before": before, "current": current, "after": after, "found": True}

def _document_kind(filename: str, page_texts):
    name = (filename or "").lower()
    sample = _normalize_ws(" ".join((p.get("text") or "") for p in page_texts[:5])).lower()
    if "general-mga" in name or "general model grant agreement" in sample or "general mga" in sample:
        return ("MODEL_MGA", "filename/text identifies a General Model Grant Agreement")
    return ("UNKNOWN", "no deterministic project-specific signature established")


def _extract_trigger(text: str):
    normalized = _normalize_ws(text)
    patterns = [
        r"\bwithin\s+\d+\s+days?\b.{0,140}?(?=[.;]|$)",
        r"\bin case of\b.{0,150}?(?=[.;]|$)",
        r"\bif\b.{0,150}?(?=[.;]|$)",
        r"\bwhen\b.{0,150}?(?=[.;]|$)",
        r"\bwhere applicable\b.{0,120}?(?=[.;]|$)",
    ]
    for p in patterns:
        m = re.search(p, normalized, re.I)
        if m:
            return m.group(0).strip()
    return None


def _parent_trigger(before: str):
    """
    Accept a previous sentence as a parent trigger only when it is explicitly
    conditional and structurally introduces the current clause.
    """
    b = _normalize_ws(before)
    if not b:
        return None
    if not re.match(r"^(if|when|where applicable|in case of)\b", b, re.I):
        return None
    return _extract_trigger(b) or b


def _applicability(clause: str, subject: str, source_heading: str = "", parent_trigger: str | None = None):
    # Deliberately excludes context_after to prevent semantic leakage.
    t = _normalize_ws(" ".join([source_heading or "", clause or ""])).lower()
    s = _normalize_ws(subject).lower()

    if "call conditions" in t:
        return "IF_CALL_CONDITION"
    if any(x in t for x in ["eurohpc", "chips ju", "eic market place", "joint undertaking", "specific rules for"]):
        return "IF_PROGRAMME_OPTION"
    if "beneficiary concerned" in t or "beneficiary concerned" in s:
        return "IF_PARTICIPANT_TYPE"
    if parent_trigger or re.search(r"\b(in case of|if|when|where applicable|within\s+\d+\s+days?)\b", t, re.I):
        return "IF_EVENT"
    return "ALWAYS"


def _analyze_completeness(candidate, window, document_kind, source_heading=None):
    quote = _normalize_ws(candidate.get("source_quote"))
    action = _normalize_ws(candidate.get("candidate_action"))
    current = _normalize_ws(window.get("current")) or quote
    before = _normalize_ws(window.get("before"))
    blocking = []
    warnings = []

    if re.search(r"\([a-z]\.$", quote, re.I) or re.search(r"\b(?:e|i)\.$", quote, re.I):
        if len(current) > len(quote) + 8:
            warnings.append("SOURCE_QUOTE_TRUNCATION_RECOVERED")
        else:
            blocking.append("TRUNCATED_SOURCE_QUOTE")

    if quote.endswith(":") or action.endswith(":") or current.endswith(":"):
        blocking.append("PARENT_OR_LIST_CONTINUATION_REQUIRED")

    if re.search(r"\b(them|those|it|this|these|such)\b", action[:80], re.I):
        blocking.append("UNRESOLVED_REFERENCE")

    if len(action) < 12:
        blocking.append("LOW_SIGNAL_ACTION")

    if re.match(r"^(?:also\s+)?take place\b", action, re.I) and "beneficiar" in _normalize_ws(candidate.get("candidate_subject")).lower():
        blocking.append("MALFORMED_SUBJECT_ACTION_BOUNDARY")

    if not window.get("found"):
        blocking.append("SOURCE_CONTEXT_NOT_LOCATED")

    # Trigger is clause-bound. Previous text is accepted only if it is itself
    # an explicit conditional parent. context_after is never used.
    trigger = _extract_trigger(current)
    parent_trigger = None if trigger else _parent_trigger(before)
    if not trigger:
        trigger = parent_trigger

    applicability = _applicability(
        current,
        candidate.get("candidate_subject") or "",
        source_heading=source_heading or "",
        parent_trigger=parent_trigger,
    )
    if applicability != "ALWAYS" and not trigger and applicability not in {"IF_PROGRAMME_OPTION", "IF_CALL_CONDITION"}:
        warnings.append("CONDITIONAL_CONTEXT_DETECTED_WITHOUT_EXPLICIT_TRIGGER")

    if document_kind == "MODEL_MGA":
        blocking.append("MODEL_TEMPLATE_NOT_PROJECT_SPECIFIC")

    blocking = list(dict.fromkeys(blocking))
    warnings = list(dict.fromkeys(warnings))

    if "MALFORMED_SUBJECT_ACTION_BOUNDARY" in blocking:
        status = "BLOCKED_MALFORMED"
    elif "PARENT_OR_LIST_CONTINUATION_REQUIRED" in blocking:
        status = "PARENT_CONTROL"
    elif document_kind == "MODEL_MGA":
        status = "TEMPLATE_ONLY"
    elif blocking:
        status = "CONTEXT_REQUIRED"
    else:
        status = "READY"

    return {
        "blocking": blocking,
        "warnings": warnings,
        "status": status,
        "promotable": 1 if status == "READY" else 0,
        "applicability": applicability,
        "trigger_text": trigger,
        "context_quote": current,
    }

def _refresh_context_for_extraction_in_connection(con, extraction_id):
    ext = con.execute("SELECT * FROM ga_extractions WHERE id=?", (extraction_id,)).fetchone()
    if not ext:
        raise ValueError("EXTRACTION_NOT_FOUND")
    ext = dict(ext)
    doc = con.execute("SELECT * FROM grant_documents WHERE id=?", (ext["document_id"],)).fetchone()
    if not doc:
        raise ValueError("GRANT_DOCUMENT_NOT_FOUND")
    doc = dict(doc)
    pages = [dict(r) for r in con.execute("SELECT * FROM ga_pages WHERE extraction_id=? ORDER BY page_number", (extraction_id,))]
    document_kind, basis = _document_kind(doc.get("filename"), pages)
    con.execute(
        """INSERT INTO ga_document_profiles(document_id,analysis_version,document_kind,detection_basis,analyzed_at)
           VALUES(?,?,?,?,?)
           ON CONFLICT(document_id) DO UPDATE SET
             analysis_version=excluded.analysis_version,
             document_kind=excluded.document_kind,
             detection_basis=excluded.detection_basis,
             analyzed_at=excluded.analyzed_at""",
        (doc["id"], CONTEXT_ANALYSIS_VERSION, document_kind, basis, now()),
    )

    page_map = {p["page_number"]: p for p in pages}
    candidates = [dict(r) for r in con.execute("SELECT * FROM ga_candidates WHERE extraction_id=? ORDER BY id", (extraction_id,))]
    analyses = {}
    for candidate in candidates:
        page = page_map.get(candidate["source_page"])
        if not page:
            window = {"before": "", "current": _normalize_ws(candidate["source_quote"]), "after": "", "found": False}
            article = heading = None
        else:
            window = _context_window(page["text"], candidate["source_quote"])
            article, heading = _nearest_heading(page["text"], candidate["source_quote"])
        complete = _analyze_completeness(candidate, window, document_kind, source_heading=heading)
        analyses[candidate["id"]] = {
            "candidate": candidate,
            "window": window,
            "article": article,
            "heading": heading,
            **complete,
            "duplicate_of": None,
            "relation_type": None,
        }

    # Cross-type overlap on the same page/source hash: keep obligation as parent and mark evidence facet for merge.
    for cid, a in analyses.items():
        c = a["candidate"]
        if c["record_type"] != "EVIDENCE_REQUIREMENT":
            continue
        q = _normalize_ws(c["source_quote"]).lower()
        for oid, other in analyses.items():
            oc = other["candidate"]
            if oc["record_type"] != "OBLIGATION" or oc["source_page"] != c["source_page"] or oc["source_text_sha256"] != c["source_text_sha256"]:
                continue
            oq = _normalize_ws(oc["source_quote"]).lower()
            if q and oq and (q in oq or oq in q or _normalize_ws(c["candidate_action"]).lower() in oq):
                a["duplicate_of"] = oid
                a["relation_type"] = "EVIDENCE_FACET_OF"
                a["status"] = "MERGE_REQUIRED"
                a["promotable"] = 0
                a["blocking"] = list(dict.fromkeys(a["blocking"] + ["CROSS_TYPE_DUPLICATE_REQUIRES_MERGE"]))
                break

    for cid, a in analyses.items():
        con.execute(
            """INSERT INTO ga_candidate_context(
               candidate_id,analysis_version,document_kind,source_article,source_heading,
               context_before,context_quote,context_after,applicability,trigger_text,
               context_status,promotable,blocking_reasons_json,warnings_json,
               duplicate_of_candidate_id,relation_type,analyzed_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(candidate_id) DO UPDATE SET
                 analysis_version=excluded.analysis_version,
                 document_kind=excluded.document_kind,
                 source_article=excluded.source_article,
                 source_heading=excluded.source_heading,
                 context_before=excluded.context_before,
                 context_quote=excluded.context_quote,
                 context_after=excluded.context_after,
                 applicability=excluded.applicability,
                 trigger_text=excluded.trigger_text,
                 context_status=excluded.context_status,
                 promotable=excluded.promotable,
                 blocking_reasons_json=excluded.blocking_reasons_json,
                 warnings_json=excluded.warnings_json,
                 duplicate_of_candidate_id=excluded.duplicate_of_candidate_id,
                 relation_type=excluded.relation_type,
                 analyzed_at=excluded.analyzed_at""",
            (
                cid, CONTEXT_ANALYSIS_VERSION, document_kind, a["article"], a["heading"],
                a["window"].get("before"), a["context_quote"], a["window"].get("after"),
                a["applicability"], a["trigger_text"], a["status"], a["promotable"],
                json.dumps(a["blocking"], ensure_ascii=False),
                json.dumps(a["warnings"], ensure_ascii=False),
                a["duplicate_of"], a["relation_type"], now(),
            ),
        )
    return len(analyses)


def refresh_context_for_extraction(db_path, extraction_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        return _refresh_context_for_extraction_in_connection(con, extraction_id)


def refresh_context_for_project(db_path, project_id):
    ensure_schema(db_path)
    total = 0
    with connect(db_path) as con:
        ids = [r["id"] for r in con.execute("SELECT id FROM ga_extractions WHERE project_id=?", (project_id,))]
        for extraction_id in ids:
            total += _refresh_context_for_extraction_in_connection(con, extraction_id)
    return total


def document_profile_for_document(db_path, document_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        row = con.execute("SELECT * FROM ga_document_profiles WHERE document_id=?", (document_id,)).fetchone()
        return dict(row) if row else None

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _candidate_hash(candidate: dict) -> str:
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
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_text(canonical)

def _split_sentences(text: str):
    chunks = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]

def _build_candidate(rule, match, page, context):
    groups = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in match.groupdict().items()
    }
    record_type = rule["record_type"]

    if record_type == "OBLIGATION":
        subject = groups.get("subject") or "Grant obligation"
        action = groups.get("action") or ""
        due = None
    elif record_type == "DELIVERABLE":
        subject = groups.get("id") or "Deliverable"
        action = groups.get("title") or ""
        due = f"M{groups['due']}" if groups.get("due") else None
    elif record_type == "MILESTONE":
        subject = groups.get("id") or "Milestone"
        action = groups.get("title") or ""
        due = f"M{groups['due']}" if groups.get("due") else None
    elif record_type == "REPORTING_PERIOD":
        subject = f"Reporting Period {groups.get('num') or ''}".strip()
        action = "Reporting period identified in authoritative text"
        due = f"M{groups.get('start')}-M{groups.get('end')}"
    else:
        subject = "Evidence retention"
        action = groups.get("action") or ""
        due = None

    candidate = {
        "extraction_id": context["extraction_id"],
        "project_id": context["project_id"],
        "document_id": context["document_id"],
        "record_type": record_type,
        "source_page": page["page_number"],
        "source_quote": match.group(0).strip(),
        "source_text_sha256": page["text_sha256"],
        "candidate_subject": subject,
        "candidate_action": action,
        "candidate_trigger_or_due": due,
        "rule_id": rule["rule_id"],
    }
    candidate["candidate_sha256"] = _candidate_hash(candidate)
    return candidate

def detect_candidates(page_rows, extraction_id, project_id, document_id):
    candidates = []
    seen = set()
    context = {
        "extraction_id": extraction_id,
        "project_id": project_id,
        "document_id": document_id,
    }

    for page in page_rows:
        if _sha256_text(page["text"]) != page["text_sha256"]:
            raise ValueError(f"PAGE_TEXT_SHA_MISMATCH page={page['page_number']}")

        for sentence in _split_sentences(page["text"]):
            for rule in RULES:
                for match in rule["pattern"].finditer(sentence):
                    signature = (
                        rule["rule_id"],
                        page["page_number"],
                        match.group(0).strip().lower(),
                    )
                    if signature in seen:
                        continue
                    seen.add(signature)
                    candidates.append(_build_candidate(rule, match, page, context))
    return candidates

def _existing_extraction(con, document_id, document_sha256):
    row = con.execute(
        """SELECT * FROM ga_extractions
           WHERE document_id=? AND document_sha256=? AND status='PASS_TEXT_EXTRACTED'
           ORDER BY id DESC LIMIT 1""",
        (document_id, document_sha256),
    ).fetchone()
    return dict(row) if row else None

def store_extraction_result(
    db_path,
    project_id,
    document_id,
    document_sha256,
    page_texts,
    backend,
    backend_version,
    extraction_mode,
    ocr_used=False,
    network_requests=0,
):
    ensure_schema(db_path)

    normalized = []
    total_chars = 0
    empty_pages = 0

    for page_number, text in enumerate(page_texts, start=1):
        text = text or ""
        if len(text) > MAX_CHARS_PER_PAGE:
            raise ValueError(f"PAGE_TEXT_EXCEEDS_CHAR_LIMIT page={page_number}")
        total_chars += len(text)
        if total_chars > MAX_TOTAL_CHARS:
            raise ValueError("TOTAL_TEXT_EXCEEDS_CHAR_LIMIT")
        if not text.strip():
            empty_pages += 1
        normalized.append(
            {
                "page_number": page_number,
                "text": text,
                "text_sha256": _sha256_text(text),
                "char_count": len(text),
            }
        )

    if not normalized:
        raise ValueError("PDF_HAS_ZERO_PAGES")
    if len(normalized) > MAX_PAGES:
        raise ValueError("PDF_EXCEEDS_PAGE_LIMIT")
    if total_chars < MIN_TOTAL_TEXT_CHARS:
        raise ValueError("INSUFFICIENT_MACHINE_READABLE_TEXT_OCR_NOT_ENABLED")

    with connect(db_path) as con:
        existing = _existing_extraction(con, document_id, document_sha256)
        if existing:
            refresh_context_for_extraction(db_path, existing["id"])
            return extraction_summary(db_path, existing["id"])

        cur = con.execute(
            """INSERT INTO ga_extractions(
               project_id,document_id,document_sha256,backend,backend_version,
               extraction_mode,page_count,total_text_chars,empty_page_count,
               ocr_used,network_requests,status,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                project_id,
                document_id,
                document_sha256,
                backend,
                backend_version,
                extraction_mode,
                len(normalized),
                total_chars,
                empty_pages,
                1 if ocr_used else 0,
                network_requests,
                "PASS_TEXT_EXTRACTED",
                now(),
            ),
        )
        extraction_id = cur.lastrowid

        for page in normalized:
            con.execute(
                """INSERT INTO ga_pages(
                   extraction_id,page_number,text_sha256,char_count,text
                   ) VALUES(?,?,?,?,?)""",
                (
                    extraction_id,
                    page["page_number"],
                    page["text_sha256"],
                    page["char_count"],
                    page["text"],
                ),
            )

        candidates = detect_candidates(
            normalized,
            extraction_id=extraction_id,
            project_id=project_id,
            document_id=document_id,
        )

        for candidate in candidates:
            con.execute(
                """INSERT INTO ga_candidates(
                   extraction_id,project_id,document_id,record_type,source_page,
                   source_quote,source_text_sha256,candidate_subject,candidate_action,
                   candidate_trigger_or_due,rule_id,candidate_sha256,review_status,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    candidate["extraction_id"],
                    candidate["project_id"],
                    candidate["document_id"],
                    candidate["record_type"],
                    candidate["source_page"],
                    candidate["source_quote"],
                    candidate["source_text_sha256"],
                    candidate["candidate_subject"],
                    candidate["candidate_action"],
                    candidate.get("candidate_trigger_or_due"),
                    candidate["rule_id"],
                    candidate["candidate_sha256"],
                    "PENDING",
                    now(),
                ),
            )

        con.execute(
            "UPDATE grant_documents SET status='EXTRACTED_REVIEW_PENDING' WHERE id=?",
            (document_id,),
        )
        audit(
            con,
            project_id,
            "GA_TEXT_EXTRACTED",
            f"document_id={document_id}; pages={len(normalized)}; candidates={len(candidates)}",
            "GRANT_DOCUMENT",
            document_id,
        )
        _refresh_context_for_extraction_in_connection(con, extraction_id)

    return extraction_summary(db_path, extraction_id)

def extract_pdf_and_detect(db_path, document_id):
    ensure_schema(db_path)

    with connect(db_path) as con:
        row = con.execute(
            """SELECT gd.*, p.code project_code
               FROM grant_documents gd
               JOIN projects p ON p.id=gd.project_id
               WHERE gd.id=?""",
            (document_id,),
        ).fetchone()
        if not row:
            raise ValueError("GRANT_DOCUMENT_NOT_FOUND")
        document = dict(row)

    pdf_path = Path(document["stored_path"])
    if not pdf_path.exists() or not pdf_path.is_file():
        raise ValueError("STAGED_PDF_NOT_FOUND")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("STAGED_FILE_NOT_PDF")

    data = pdf_path.read_bytes()
    if not data:
        raise ValueError("EMPTY_PDF")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF_EXCEEDS_25_MIB_LIMIT")

    actual_sha = _sha256_bytes(data)
    if actual_sha.lower() != document["sha256"].lower():
        raise ValueError("DOCUMENT_SHA256_MISMATCH")

    with connect(db_path) as con:
        existing = _existing_extraction(con, document_id, actual_sha)
        if existing:
            refresh_context_for_extraction(db_path, existing["id"])
            return extraction_summary(db_path, existing["id"])

    try:
        import pypdf
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError(
            "PYPDF_NOT_AVAILABLE — run INSTALL_GRANTOPS_MVP_V0_2.ps1"
        ) from exc

    if getattr(pypdf, "__version__", None) != REQUIRED_PYPDF_VERSION:
        raise RuntimeError(
            f"PYPDF_VERSION_MISMATCH — required {REQUIRED_PYPDF_VERSION}, "
            f"observed {getattr(pypdf, '__version__', 'unknown')}"
        )

    try:
        reader = PdfReader(str(pdf_path), strict=True)
    except Exception as exc:
        raise ValueError(f"PDF_READER_FAILED: {type(exc).__name__}: {exc}") from exc

    if reader.is_encrypted:
        raise ValueError("ENCRYPTED_PDF_NOT_SUPPORTED")
    if len(reader.pages) > MAX_PAGES:
        raise ValueError("PDF_EXCEEDS_250_PAGE_LIMIT")

    page_texts = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except Exception as exc:
            raise ValueError(
                f"PAGE_TEXT_EXTRACTION_FAILED page={index}: {type(exc).__name__}: {exc}"
            ) from exc
        page_texts.append(text)

    return store_extraction_result(
        db_path=db_path,
        project_id=document["project_id"],
        document_id=document_id,
        document_sha256=actual_sha,
        page_texts=page_texts,
        backend="pypdf",
        backend_version=pypdf.__version__,
        extraction_mode="layout",
        ocr_used=False,
        network_requests=0,
    )

def extraction_for_document(db_path, document_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        row = con.execute(
            """SELECT * FROM ga_extractions
               WHERE document_id=? AND status='PASS_TEXT_EXTRACTED'
               ORDER BY id DESC LIMIT 1""",
            (document_id,),
        ).fetchone()
        return dict(row) if row else None

def extraction_summary(db_path, extraction_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        ext = con.execute(
            "SELECT * FROM ga_extractions WHERE id=?",
            (extraction_id,),
        ).fetchone()
        if not ext:
            raise ValueError("EXTRACTION_NOT_FOUND")
        counts = {
            row["record_type"]: row["n"]
            for row in con.execute(
                """SELECT record_type, COUNT(*) n
                   FROM ga_candidates WHERE extraction_id=?
                   GROUP BY record_type""",
                (extraction_id,),
            )
        }
        review = {
            row["review_status"]: row["n"]
            for row in con.execute(
                """SELECT review_status, COUNT(*) n
                   FROM ga_candidates WHERE extraction_id=?
                   GROUP BY review_status""",
                (extraction_id,),
            )
        }
        out = dict(ext)
        context_counts = {
            row["context_status"]: row["n"]
            for row in con.execute(
                """SELECT gcc.context_status, COUNT(*) n
                   FROM ga_candidate_context gcc
                   JOIN ga_candidates c ON c.id=gcc.candidate_id
                   WHERE c.extraction_id=?
                   GROUP BY gcc.context_status""",
                (extraction_id,),
            )
        }
        profile = con.execute(
            """SELECT p.* FROM ga_document_profiles p
               JOIN ga_extractions e ON e.document_id=p.document_id
               WHERE e.id=?""",
            (extraction_id,),
        ).fetchone()
        out["candidate_counts_by_type"] = counts
        out["review_counts"] = review
        out["context_counts"] = context_counts
        out["document_kind"] = dict(profile)["document_kind"] if profile else "UNKNOWN"
        out["candidate_count"] = sum(counts.values())
        out["promotable_count"] = con.execute(
            """SELECT COUNT(*) n FROM ga_candidate_context gcc
               JOIN ga_candidates c ON c.id=gcc.candidate_id
               WHERE c.extraction_id=? AND gcc.promotable=1""",
            (extraction_id,),
        ).fetchone()["n"]
        return out

def _candidate_select_sql(where_sql):
    return f"""SELECT c.*,
              gcc.analysis_version AS context_analysis_version,
              gcc.document_kind,
              gcc.source_article,
              gcc.source_heading,
              gcc.context_before,
              gcc.context_quote,
              gcc.context_after,
              gcc.applicability,
              gcc.trigger_text,
              gcc.context_status,
              gcc.promotable,
              gcc.blocking_reasons_json,
              gcc.warnings_json,
              gcc.duplicate_of_candidate_id,
              gcc.relation_type
              FROM ga_candidates c
              LEFT JOIN ga_candidate_context gcc ON gcc.candidate_id=c.id
              WHERE {where_sql}"""


def list_candidates(db_path, project_id, extraction_id=None, review_status=None, record_type=None):
    ensure_schema(db_path)
    refresh_context_for_project(db_path, project_id)
    clauses = ["c.project_id=?"]
    params = [project_id]
    if extraction_id is not None:
        clauses.append("c.extraction_id=?")
        params.append(extraction_id)
    if review_status and review_status != "ALL":
        clauses.append("c.review_status=?")
        params.append(review_status)
    if record_type and record_type != "ALL":
        clauses.append("c.record_type=?")
        params.append(record_type)

    sql = _candidate_select_sql(" AND ".join(clauses)) + " ORDER BY c.source_page, c.id"
    with connect(db_path) as con:
        return [dict(row) for row in con.execute(sql, params)]


def get_candidate(db_path, candidate_id):
    ensure_schema(db_path)
    with connect(db_path) as con:
        row = con.execute(_candidate_select_sql("c.id=?"), (candidate_id,)).fetchone()
        return dict(row) if row else None


def page_text(db_path, extraction_id, page_number):
    ensure_schema(db_path)
    with connect(db_path) as con:
        row = con.execute(
            """SELECT * FROM ga_pages
               WHERE extraction_id=? AND page_number=?""",
            (extraction_id, page_number),
        ).fetchone()
        return dict(row) if row else None

def _title_for_candidate(candidate):
    subject = candidate["candidate_subject"].strip()
    action = candidate["candidate_action"].strip()

    if candidate["record_type"] in {"DELIVERABLE", "MILESTONE"}:
        return f"{subject} — {action}".strip(" —")[:220]
    if candidate["record_type"] == "REPORTING_PERIOD":
        trigger = candidate.get("candidate_trigger_or_due")
        return f"{subject} — {trigger}" if trigger else subject
    if candidate["record_type"] == "EVIDENCE_REQUIREMENT":
        return f"Evidence retention — {action}"[:220]
    return action[:220] if action else subject[:220]

def _description_for_candidate(candidate):
    parts = [
        "Promoted from Grant Agreement review queue.",
        f"Candidate subject: {candidate['candidate_subject']}.",
    ]
    trigger = candidate.get("trigger_text") or candidate.get("candidate_trigger_or_due")
    if trigger:
        parts.append(
            f"Source expresses applicability/trigger as {trigger}; "
            "GrantOps has not converted it into an absolute date."
        )
    if candidate.get("applicability"):
        parts.append(f"Applicability: {candidate['applicability']}.")
    parts.append(f"Detection rule: {candidate['rule_id']}.")
    return " ".join(parts)

def review_candidate(
    db_path,
    candidate_id,
    decision,
    reviewer,
    source_page_verified,
    source_quote_verified,
    source_text_sha256_verified,
    notes="",
):
    ensure_schema(db_path)
    decision = decision.strip().upper()
    reviewer = reviewer.strip()

    if decision not in {"APPROVE", "REJECT", "NEEDS_CLARIFICATION"}:
        raise ValueError("INVALID_REVIEW_DECISION")
    if not reviewer:
        raise ValueError("REVIEWER_REQUIRED")

    with connect(db_path) as con:
        row = con.execute(
            _candidate_select_sql("c.id=?"),
            (candidate_id,),
        ).fetchone()
        if not row:
            raise ValueError("CANDIDATE_NOT_FOUND")
        candidate = dict(row)

        if candidate["review_status"] in {"APPROVED", "REJECTED"}:
            raise ValueError("CANDIDATE_ALREADY_FINALIZED")

        expected_hash = _candidate_hash(candidate)
        if expected_hash != candidate["candidate_sha256"]:
            raise ValueError("CANDIDATE_INTEGRITY_MISMATCH")

        page = con.execute(
            """SELECT * FROM ga_pages
               WHERE extraction_id=? AND page_number=?""",
            (candidate["extraction_id"], candidate["source_page"]),
        ).fetchone()
        if not page:
            raise ValueError("SOURCE_PAGE_NOT_FOUND")

        page = dict(page)
        actual_page_sha = _sha256_text(page["text"])
        if actual_page_sha != page["text_sha256"]:
            raise ValueError("SOURCE_PAGE_HASH_MISMATCH")
        if candidate["source_text_sha256"] != page["text_sha256"]:
            raise ValueError("CANDIDATE_SOURCE_HASH_MISMATCH")
        if candidate["source_quote"] not in page["text"]:
            raise ValueError("SOURCE_QUOTE_NOT_FOUND_ON_PAGE")

        if decision == "APPROVE":
            if candidate.get("promotable") != 1:
                status = candidate.get("context_status") or "CONTEXT_NOT_ANALYZED"
                raise ValueError(f"CANDIDATE_NOT_PROMOTABLE_{status}")
            if candidate.get("duplicate_of_candidate_id"):
                raise ValueError("CANDIDATE_REQUIRES_MERGE")
            if not (
                source_page_verified
                and source_quote_verified
                and source_text_sha256_verified
            ):
                raise ValueError("APPROVAL_REQUIRES_FULL_SOURCE_VERIFICATION")

            title = _title_for_candidate(candidate)
            description = _description_for_candidate(candidate)

            existing_promoted_id = candidate.get("promoted_record_id")

            if existing_promoted_id is not None:
                existing_record_row = con.execute(
                    """SELECT * FROM obligations
                       WHERE id=? AND project_id=?""",
                    (existing_promoted_id, candidate["project_id"]),
                ).fetchone()
                if not existing_record_row:
                    raise ValueError("PROMOTED_RECORD_NOT_FOUND")

                existing_record = dict(existing_record_row)
                restore_status = existing_record["status"]

                # A v0.4.2 reopen deliberately blocks and unverifies the
                # operational record. On re-approval, restore the exact
                # pre-reopen status from the immutable human change event.
                change_table = con.execute(
                    """SELECT 1 FROM sqlite_master
                       WHERE type='table' AND name='human_change_events'"""
                ).fetchone()
                reopen_event = None
                if change_table:
                    reopen_event = con.execute(
                        """SELECT * FROM human_change_events
                           WHERE project_id=?
                             AND entity_type='GA_CANDIDATE'
                             AND entity_id=?
                             AND action='CANDIDATE_REOPEN'
                           ORDER BY id DESC LIMIT 1""",
                        (candidate["project_id"], candidate_id),
                    ).fetchone()

                before_reapprove = {
                    "candidate": {
                        "review_status": candidate["review_status"],
                        "reviewer": candidate.get("reviewer"),
                        "reviewed_at": candidate.get("reviewed_at"),
                        "review_notes": candidate.get("review_notes"),
                        "promoted_record_id": existing_promoted_id,
                    },
                    "record": {
                        "id": existing_record["id"],
                        "status": existing_record["status"],
                        "verification_status": existing_record["verification_status"],
                    },
                }

                if reopen_event:
                    try:
                        reopen_before = json.loads(reopen_event["before_json"])
                        prior = reopen_before.get("record") or {}
                        if prior.get("status"):
                            restore_status = prior["status"]
                    except Exception:
                        pass

                con.execute(
                    """UPDATE obligations
                       SET verification_status='HUMAN_VERIFIED',
                           status=?
                       WHERE id=?""",
                    (restore_status, existing_promoted_id),
                )
                promoted_id = existing_promoted_id

                con.execute(
                    """UPDATE ga_candidates
                       SET review_status='APPROVED',reviewer=?,reviewed_at=?,
                           review_notes=?
                       WHERE id=?""",
                    (reviewer, now(), notes or None, candidate_id),
                )

                after_record = dict(con.execute(
                    "SELECT * FROM obligations WHERE id=?",
                    (promoted_id,),
                ).fetchone())
                after_candidate = dict(con.execute(
                    "SELECT * FROM ga_candidates WHERE id=?",
                    (candidate_id,),
                ).fetchone())

                if change_table:
                    con.execute(
                        """INSERT INTO human_change_events(
                           project_id,entity_type,entity_id,action,actor,reason,
                           before_json,after_json,source_integrity_json,
                           requires_graph_rebuild,created_at
                           ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            candidate["project_id"],
                            "GA_CANDIDATE",
                            candidate_id,
                            "CANDIDATE_REAPPROVED",
                            reviewer,
                            notes or "Re-approved after human review.",
                            json.dumps(before_reapprove, sort_keys=True, ensure_ascii=False),
                            json.dumps({
                                "candidate": {
                                    "review_status": after_candidate["review_status"],
                                    "reviewer": after_candidate["reviewer"],
                                    "reviewed_at": after_candidate["reviewed_at"],
                                    "review_notes": after_candidate["review_notes"],
                                    "promoted_record_id": after_candidate["promoted_record_id"],
                                },
                                "record": {
                                    "id": after_record["id"],
                                    "status": after_record["status"],
                                    "verification_status": after_record["verification_status"],
                                },
                            }, sort_keys=True, ensure_ascii=False),
                            json.dumps({
                                "candidate_integrity_verified": True,
                                "source_page_verified": True,
                                "source_quote_verified": True,
                                "source_text_sha256_verified": True,
                                "reused_promoted_record": True,
                            }, sort_keys=True, ensure_ascii=False),
                            1,
                            now(),
                        ),
                    )

                audit(
                    con,
                    candidate["project_id"],
                    "GA_CANDIDATE_REAPPROVED_REVERIFIED",
                    f"candidate_id={candidate_id}; reused_record_id={promoted_id}; reviewer={reviewer}",
                    "OBLIGATION",
                    promoted_id,
                )
                return {
                    "status": "APPROVED",
                    "promoted_record_id": promoted_id,
                    "reviewer": reviewer,
                    "reused_promoted_record": True,
                }

            cur = con.execute(
                """INSERT INTO obligations(
                   project_id,record_type,title,description,due_date,owner,status,
                   verification_status,source_page,source_section,source_quote,
                   source_text_sha256,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    candidate["project_id"],
                    candidate["record_type"],
                    title,
                    description,
                    None,
                    None,
                    "OPEN",
                    "HUMAN_VERIFIED",
                    str(candidate["source_page"]),
                    " · ".join(x for x in [
                        "Grant Agreement",
                        candidate.get("source_article"),
                        candidate.get("source_heading"),
                        candidate["rule_id"],
                    ] if x),
                    candidate.get("context_quote") or candidate["source_quote"],
                    candidate["source_text_sha256"],
                    now(),
                ),
            )
            promoted_id = cur.lastrowid
            con.execute(
                """UPDATE ga_candidates
                   SET review_status='APPROVED',reviewer=?,reviewed_at=?,
                       review_notes=?,promoted_record_id=?
                   WHERE id=?""",
                (reviewer, now(), notes or None, promoted_id, candidate_id),
            )
            audit(
                con,
                candidate["project_id"],
                "GA_CANDIDATE_APPROVED_AND_PROMOTED",
                f"candidate_id={candidate_id}; record_id={promoted_id}; reviewer={reviewer}",
                "OBLIGATION",
                promoted_id,
            )
            return {
                "status": "APPROVED",
                "promoted_record_id": promoted_id,
                "reviewer": reviewer,
                "reused_promoted_record": False,
            }

        new_status = "REJECTED" if decision == "REJECT" else "NEEDS_CLARIFICATION"
        con.execute(
            """UPDATE ga_candidates
               SET review_status=?,reviewer=?,reviewed_at=?,review_notes=?
               WHERE id=?""",
            (new_status, reviewer, now(), notes or None, candidate_id),
        )
        audit(
            con,
            candidate["project_id"],
            f"GA_CANDIDATE_{new_status}",
            f"candidate_id={candidate_id}; reviewer={reviewer}",
            "GA_CANDIDATE",
            candidate_id,
        )
        return {
            "status": new_status,
            "promoted_record_id": None,
            "reviewer": reviewer,
        }
