from pathlib import Path
from datetime import date, datetime
import tempfile
import html
import sqlite3
import json

import pandas as pd
import streamlit as st

from grantops.db import init_db
from grantops.seed import seed
from grantops.repo import (
    projects,
    project,
    records,
    evidence,
    documents,
    metrics,
    audit_events,
    update_record_status,
    add_record,
    add_evidence,
    add_project,
    stage_pdf,
)

from grantops.buyer_demo import buyer_demo_snapshot
from grantops.wide_action_centre import WIDE_PROJECT_CODE, wide_action_centre_snapshot, render_wide_action_centre
from grantops.riana_demo import riana_demo_available, riana_demo_snapshot

from grantops.corrections import (
    ensure_schema as ensure_corrections_schema,
    list_operational_records as correction_operational_records,
    list_finalized_candidates as correction_finalized_candidates,
    edit_operational_record,
    reopen_candidate,
    list_change_events,
    corrections_after_latest_graph,
)

from grantops.provenance import (
    ensure_schema as ensure_provenance_schema,
    build_provenance_review,
    latest_provenance_review,
    review_summary as provenance_review_summary,
    list_provenance_items,
)

from grantops.operational_graph import (
    ensure_schema as ensure_operational_graph_schema,
    build_graph as build_operational_graph,
    latest_graph_run as latest_operational_graph_run,
    graph_summary as operational_graph_summary,
    list_nodes as operational_graph_nodes,
    list_edges as operational_graph_edges,
    list_deadlines as operational_graph_deadlines,
    evidence_safety_summary as operational_graph_evidence_safety,
)

from grantops.annex1 import (
    ensure_schema as ensure_annex1_schema,
    parse_extraction as parse_annex1_extraction,
    latest_run_for_extraction as latest_annex1_run_for_extraction,
    list_work_packages as annex1_work_packages,
    list_deliverables as annex1_deliverables,
    list_milestones as annex1_milestones,
    list_reporting_periods as annex1_reporting_periods,
)

from grantops.ga_review import (
    ensure_schema as ensure_ga_review_schema,
    extract_pdf_and_detect,
    extraction_for_document,
    extraction_summary,
    list_candidates,
    get_candidate,
    page_text as ga_page_text,
    review_candidate,
    refresh_context_for_project,
    document_profile_for_document,
)

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "grantops.db"
UPLOADS = BASE / "uploads"
RIANA_FINAL = BASE / "audit_exports" / "RIANA_IDENTITY_FUSION_FINAL" / "RIANA_IDENTITY_FUSION_FINAL_CANONICAL.json"

init_db(DB)
seed(DB)
ensure_ga_review_schema(DB)
ensure_annex1_schema(DB)
ensure_operational_graph_schema(DB)
ensure_provenance_schema(DB)
ensure_corrections_schema(DB)

st.set_page_config(
    page_title="GrantOps",
    page_icon="GO",
    layout="wide",
    initial_sidebar_state="expanded",
)

STATUS_LABEL = {
    "OPEN": "Open",
    "IN_PROGRESS": "In progress",
    "DONE": "Done",
    "BLOCKED": "Blocked",
    "MISSING": "Missing",
    "READY": "Ready",
    "ACCEPTED": "Accepted",
}
TYPE_LABEL = {
    "OBLIGATION": "Obligation",
    "DELIVERABLE": "Deliverable",
    "MILESTONE": "Milestone",
    "REPORTING_PERIOD": "Reporting period",
    "EVIDENCE_REQUIREMENT": "Evidence requirement",
}
VER_LABEL = {
    "HUMAN_VERIFIED": "Human verified",
    "UNVERIFIED": "Unverified",
}

CSS = """
<style>
:root {
  --go-navy: #14213d;
  --go-ink: #1d2939;
  --go-muted: #667085;
  --go-line: #e4e7ec;
  --go-panel: #ffffff;
  --go-bg: #f7f8fa;
  --go-soft: #f2f4f7;
  --go-accent: #3157d5;
  --go-danger: #b42318;
  --go-warning: #b54708;
  --go-success: #067647;
}
html, body, [class*="css"] { font-family: Inter, "Segoe UI", Arial, sans-serif; }
[data-testid="stAppViewContainer"] { background: var(--go-bg); }
[data-testid="stHeader"] { background: rgba(247,248,250,.94); }
[data-testid="stToolbar"] { display: none !important; }

[data-testid="stSidebar"] {
  background: #f0f2f5;
  border-right: 1px solid var(--go-line);
  min-width: 282px;
  max-width: 282px;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .55rem; }
.block-container {
  max-width: 1480px;
  padding-top: 1.6rem;
  padding-bottom: 3rem;
  padding-left: 2.2rem;
  padding-right: 2.2rem;
}
h1, h2, h3 { color: var(--go-ink); letter-spacing: -.02em; }
h1 { font-size: 2.0rem !important; }
h2 { font-size: 1.35rem !important; }
h3 { font-size: 1.05rem !important; }
[data-testid="stMetric"] {
  background: white;
  border: 1px solid var(--go-line);
  border-radius: 14px;
  padding: 1rem 1.05rem;
  box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
[data-testid="stMetricLabel"] { color: var(--go-muted); }
[data-testid="stMetricValue"] { color: var(--go-ink); font-size: 1.7rem; }
[data-testid="stDataFrame"] {
  border: 1px solid var(--go-line);
  border-radius: 12px;
  overflow: hidden;
}
div[data-testid="stExpander"] {
  background: white;
  border: 1px solid var(--go-line);
  border-radius: 12px;
}
.go-brand {
  font-size: 1.38rem;
  font-weight: 750;
  color: var(--go-navy);
  margin-bottom: .1rem;
}
.go-brand-sub {
  color: var(--go-muted);
  font-size: .82rem;
  margin-bottom: 1rem;
}
.go-kicker {
  color: var(--go-accent);
  font-weight: 700;
  font-size: .72rem;
  letter-spacing: .08em;
  text-transform: uppercase;
  margin-bottom: .3rem;
}
.go-project-title {
  color: var(--go-ink);
  font-size: 1.65rem;
  line-height: 1.15;
  font-weight: 760;
  margin: 0;
}
.go-project-meta {
  color: var(--go-muted);
  font-size: .92rem;
  margin-top: .42rem;
}
.go-section {
  margin-top: .4rem;
  margin-bottom: .6rem;
  font-size: 1.12rem;
  font-weight: 720;
  color: var(--go-ink);
}
.go-panel {
  background: white;
  border: 1px solid var(--go-line);
  border-radius: 14px;
  padding: 1.05rem 1.15rem;
  box-shadow: 0 1px 2px rgba(16,24,40,.03);
}
.go-row {
  background: white;
  border: 1px solid var(--go-line);
  border-radius: 12px;
  padding: .85rem 1rem;
  margin-bottom: .6rem;
}
.go-row-title { color: var(--go-ink); font-weight: 690; font-size: .95rem; }
.go-row-meta { color: var(--go-muted); font-size: .82rem; margin-top: .2rem; }
.go-badge {
  display: inline-block;
  border: 1px solid var(--go-line);
  border-radius: 999px;
  padding: .18rem .52rem;
  margin-right: .25rem;
  font-size: .72rem;
  font-weight: 650;
  background: var(--go-soft);
  color: #344054;
}
.go-badge-danger { background: #fef3f2; color: var(--go-danger); border-color: #fecdca; }
.go-badge-warning { background: #fffaeb; color: var(--go-warning); border-color: #fedf89; }
.go-badge-success { background: #ecfdf3; color: var(--go-success); border-color: #abefc6; }
.go-badge-info { background: #eef4ff; color: #3538cd; border-color: #c7d7fe; }
.go-source {
  background: #f8fafc;
  border-left: 3px solid var(--go-accent);
  border-radius: 0 10px 10px 0;
  padding: .9rem 1rem;
  color: #344054;
  font-size: .9rem;
  line-height: 1.5;
}
.go-empty {
  color: var(--go-muted);
  border: 1px dashed #d0d5dd;
  border-radius: 12px;
  padding: 1rem;
  background: rgba(255,255,255,.55);
}
.go-health {
  font-size: .78rem;
  color: var(--go-muted);
  margin-top: .25rem;
}
.go-divider { height: 1px; background: var(--go-line); margin: 1rem 0; }
button[kind="primary"] { border-radius: 9px; }
.go-hero {
  background: linear-gradient(135deg, #14213d 0%, #263b73 100%);
  color: white;
  border-radius: 18px;
  padding: 1.55rem 1.65rem;
  margin-bottom: 1rem;
  box-shadow: 0 8px 24px rgba(20,33,61,.12);
}
.go-hero-kicker {
  font-size: .72rem;
  font-weight: 750;
  letter-spacing: .09em;
  text-transform: uppercase;
  opacity: .78;
  margin-bottom: .45rem;
}
.go-hero-title {
  font-size: 1.8rem;
  font-weight: 780;
  line-height: 1.12;
  margin-bottom: .55rem;
}
.go-hero-copy {
  max-width: 900px;
  font-size: .96rem;
  line-height: 1.55;
  opacity: .92;
}
.go-value-card {
  min-height: 142px;
  background: white;
  border: 1px solid var(--go-line);
  border-radius: 14px;
  padding: 1rem 1.05rem;
}
.go-value-title {
  font-weight: 730;
  color: var(--go-ink);
  margin-bottom: .35rem;
}
.go-value-copy {
  color: var(--go-muted);
  font-size: .84rem;
  line-height: 1.45;
}
.go-step {
  background: white;
  border: 1px solid var(--go-line);
  border-radius: 12px;
  padding: .78rem .9rem;
  min-height: 105px;
}
.go-step-num {
  color: var(--go-accent);
  font-weight: 800;
  font-size: .75rem;
  margin-bottom: .28rem;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def esc(value):
    return html.escape(str(value if value not in (None, "") else "—"))


def badge(text, tone="neutral"):
    cls = "go-badge"
    if tone != "neutral":
        cls += f" go-badge-{tone}"
    return f'<span class="{cls}">{esc(text)}</span>'


def status_tone(status):
    return {
        "BLOCKED": "danger",
        "MISSING": "danger",
        "IN_PROGRESS": "warning",
        "OPEN": "info",
        "READY": "success",
        "ACCEPTED": "success",
        "DONE": "success",
    }.get(status, "neutral")


def verification_tone(value):
    return "success" if value == "HUMAN_VERIFIED" else "warning"


def due_state(due_date, status):
    if not due_date or status == "DONE":
        return "normal"
    try:
        d = date.fromisoformat(due_date)
    except ValueError:
        return "normal"
    delta = (d - date.today()).days
    if delta < 0:
        return "overdue"
    if delta <= 30:
        return "due_soon"
    return "normal"


def fmt_date(value):
    if not value:
        return "No date"
    try:
        return date.fromisoformat(value).strftime("%d %b %Y")
    except ValueError:
        return value


def page_header(p, kicker):
    st.markdown(f'<div class="go-kicker">{esc(kicker)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="go-project-title">{esc(p["title"])}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="go-project-meta">{esc(p["code"])} &nbsp;·&nbsp; '
        f'{esc(p["coordinator"])} &nbsp;·&nbsp; {esc(p["programme"])}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)


def clean_records(rs):
    return [{
        "Type": TYPE_LABEL.get(r["record_type"], r["record_type"]),
        "Record": r["title"],
        "Due": fmt_date(r["due_date"]),
        "Owner": r["owner"] or "—",
        "Status": STATUS_LABEL.get(r["status"], r["status"]),
        "Verification": VER_LABEL.get(r["verification_status"], r["verification_status"]),
    } for r in rs]


def attention_items(rs, ev):
    items = []
    for r in rs:
        state = due_state(r["due_date"], r["status"])
        if r["status"] == "BLOCKED":
            items.append(("Blocked", r["title"], f'{r["owner"] or "No owner"} · {fmt_date(r["due_date"])}', "danger"))
        elif state == "overdue":
            items.append(("Overdue", r["title"], f'{r["owner"] or "No owner"} · due {fmt_date(r["due_date"])}', "danger"))
        elif state == "due_soon":
            items.append(("Due soon", r["title"], f'{r["owner"] or "No owner"} · due {fmt_date(r["due_date"])}', "warning"))
    missing_by_record = {}
    for e in ev:
        if e["status"] == "MISSING":
            missing_by_record[e["obligation_title"]] = missing_by_record.get(e["obligation_title"], 0) + 1
    for title, n in missing_by_record.items():
        items.append(("Evidence missing", title, f"{n} evidence item{'s' if n != 1 else ''} missing", "warning"))
    order = {"danger": 0, "warning": 1, "info": 2, "neutral": 3}
    return sorted(items, key=lambda x: order.get(x[3], 9))


def render_sidebar():
    st.sidebar.markdown('<div class="go-brand">GrantOps</div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="go-brand-sub">Post-award operations</div>', unsafe_allow_html=True)

    ps = projects(DB)
    labels = {f"{row['code']} — {row['title']}": row["id"] for row in ps}
    if riana_demo_available(RIANA_FINAL):
        labels["RIANA — validated read-only workspace"] = "__RIANA__"

    chosen = st.sidebar.selectbox("Project", list(labels), key="project_switcher")
    pid = labels[chosen]
    is_riana = pid == "__RIANA__"

    if is_riana:
        p = {
            "id": "__RIANA__",
            "code": "RIANA",
            "title": "RIANA — validated Grant Agreement identity workspace",
            "coordinator": "Read-only validated source workspace",
            "programme": "Horizon Europe",
            "status": "VALIDATED",
            "start_date": None,
            "end_date": None,
            "source_url": None,
            "notes": "Read-only Stage 4 identity/provenance workspace.",
        }
    else:
        p = project(DB, pid)

    st.sidebar.markdown(
        badge(
            p["status"],
            "success" if p["status"] in {"ACTIVE", "VALIDATED"} else "neutral",
        )
        + badge(p["programme"], "info"),
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("<div style='height:.55rem'></div>", unsafe_allow_html=True)

    if is_riana:
        page = st.sidebar.radio(
            "Workspace",
            ["Buyer demo"],
            key="riana_workspace_page",
        )
    else:
        page = st.sidebar.radio(
            "Workspace",
            [
                "Buyer demo",
                "Overview",
                "Operations",
                "Operational graph",
                "Provenance review",
                "Human corrections",
                "Evidence",
                "Grant Agreement",
                "Timeline",
                "Audit",
                "Project setup",
            ],
            key="workspace_page",
        )

    st.sidebar.markdown("<div class='go-divider'></div>", unsafe_allow_html=True)
    if is_riana:
        st.sidebar.caption("MVP v0.5b · RIANA validated read-only")
        st.sidebar.caption("Stage 4 identity/provenance artifact → dashboard")
    else:
        st.sidebar.caption("MVP v0.5 · buyer-ready demo")
        st.sidebar.caption("Grant Agreement → operational workspace")
    return pid, p, page


pid, p, page = render_sidebar()
is_riana = pid == "__RIANA__"
rs = [] if is_riana else records(DB, pid)
ev = [] if is_riana else evidence(DB, pid)



# V0.5B — RIANA VALIDATED READ-ONLY DASHBOARD
if page == "Buyer demo" and is_riana:
    demo = riana_demo_snapshot(RIANA_FINAL)

    st.markdown(
        f'<div class="go-hero">'
        f'<div class="go-hero-kicker">RIANA validation workspace · identity gate closed</div>'
        f'<div class="go-hero-title">A second real Grant Agreement, visible in GrantOps</div>'
        f'<div class="go-hero-copy">'
        f'This read-only workspace exposes the RIANA identity-fusion result directly in the dashboard. '
        f'It preserves current Part A identities, proposal-era provenance and the D6.3 identifier-reuse guard '
        f'without writing anything into the operational database.'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        badge("Stage 4 PASS", "success")
        + badge("Read only", "info")
        + badge("52/52 visual markers accounted", "success")
        + badge("DB unchanged", "info"),
        unsafe_allow_html=True,
    )

    st.info(
        "RIANA is intentionally rendered from the validated Stage 4 artifact rather than from the "
        "operational database. This makes the product progress visible now, while the DB migration remains frozen."
    )

    st.markdown("<div style='height:.65rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="go-section">What GrantOps recovered from RIANA</div>', unsafe_allow_html=True)

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Work packages", demo["counts"]["work_packages"])
    r2.metric("Deliverables", demo["counts"]["deliverables"])
    r3.metric("Milestones", demo["counts"]["milestones"])
    r4.metric("Gantt markers", demo["counts"]["visual_markers"])

    r5, r6, r7 = st.columns(3)
    r5.metric("Current marker bindings", demo["counts"]["current_marker_bindings"])
    r6.metric("Proposal-era-only marker", demo["counts"]["proposal_era_only_markers"])
    r7.metric("Current Part A only", demo["counts"]["current_part_a_not_gantt_bound"])

    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)

    current_tab, mapping_tab, provenance_tab = st.tabs(
        ["Current identities", "Gantt → identity mapping", "Versioned provenance"]
    )

    with current_tab:
        kind = st.radio(
            "Identity type",
            ["Deliverables", "Milestones"],
            horizontal=True,
            key="riana_identity_kind_v05b",
        )
        rows = demo["deliverables"] if kind == "Deliverables" else demo["milestones"]
        st.dataframe(
            pd.DataFrame([{
                "ID": row["id"],
                "Title": row["name"],
                "WP": row["work_packages"],
                "Due": f'M{row["due_month"]}' if row["due_month"] is not None else "—",
                "Lead": row["lead_beneficiary"] or "—",
                "Part A page": row["source_page"] if row["source_page"] is not None else "—",
                "Binding": row["binding"],
            } for row in rows]),
            width="stretch",
            hide_index=True,
        )
        if demo["current_only_ids"]:
            st.caption(
                "Current Part A identities not distinctly bound to a Gantt marker: "
                + ", ".join(demo["current_only_ids"])
            )

    with mapping_tab:
        st.caption(
            "Every accepted visual Gantt marker is accounted for. The historical Task 6.1 / M18 marker "
            "is kept as proposal-era provenance instead of being forced onto a current Part A identity."
        )
        st.dataframe(
            pd.DataFrame([{
                "Marker": row["marker_index"],
                "Type": row["kind"],
                "Task": row["task_code"],
                "Task title": row["task_title"],
                "Month": f'M{row["month"]}' if row["month"] is not None else "—",
                "Identity": row["identity"],
                "Status": row["identity_status"],
            } for row in demo["marker_rows"]]),
            width="stretch",
            hide_index=True,
        )

    with provenance_tab:
        reuse = demo["identifier_reuse"]
        st.markdown('<div class="go-section">Identifier reuse guard</div>', unsafe_allow_html=True)
        st.warning(
            "The bare identifier D6.3 cannot be used as a universal key. RIANA uses the same bare ID "
            "for two different document-era meanings."
        )

        left, right = st.columns(2, gap="large")
        with left:
            st.markdown(
                '<div class="go-panel">'
                '<div class="go-row-title">Proposal-era identity</div>'
                f'<div class="go-row-meta"><strong>{esc(reuse["proposal_qualified_id"])}</strong></div>'
                f'<div class="go-row-meta">{esc(reuse["proposal_label"])}</div>'
                f'<div class="go-row-meta">Task {esc(reuse["proposal_task_code"])} · M{esc(reuse["proposal_month"])}</div>'
                '<div class="go-health">Historical/provenance identity · not a current Part A identity</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        with right:
            st.markdown(
                '<div class="go-panel">'
                '<div class="go-row-title">Current Part A identity</div>'
                f'<div class="go-row-meta"><strong>{esc(reuse["current_qualified_id"])}</strong></div>'
                f'<div class="go-row-meta">{esc(reuse["current_name"])}</div>'
                f'<div class="go-row-meta">Task {esc(reuse["current_task_code"])} · M{esc(reuse["current_month"])}</div>'
                '<div class="go-health">Current canonical identity</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="go-source"><strong>Join rule:</strong> {esc(reuse["join_rule"])}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
    st.success(
        "RIANA source-to-identity gate is closed and visible in the product. "
        "No database migration was required for this dashboard integration."
    )


# V0.5 — BUYER-READY DEMO
elif page == "Buyer demo":
    demo = buyer_demo_snapshot(DB, pid)

    readiness_label = "Demo ready" if demo["demo_ready"] else "Needs refresh"
    readiness_tone = "success" if demo["demo_ready"] else "warning"

    st.markdown(
        f'<div class="go-hero">'
        f'<div class="go-hero-kicker">GrantOps buyer demo · {esc(readiness_label)}</div>'
        f'<div class="go-hero-title">From Grant Agreement to operational control</div>'
        f'<div class="go-hero-copy">'
        f'GrantOps turns the project Grant Agreement into a structured operational workspace: '
        f'work packages, deliverables, milestones, reporting periods and resolved deadlines, '
        f'with source-level traceability and a human verification boundary.'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    structure_badge = badge(
        f'{demo["structure"]["total"]} structural records',
        "info",
    )
    deadline_badge = badge(
        f'{demo["deadlines"]["resolved_structural"]} resolved structural dates',
        "info",
    )
    provenance_tone = "success" if demo["provenance"]["complete"] else "warning"
    provenance_badge = badge(
        f'{demo["provenance"]["core_complete"]}/{demo["provenance"]["core_total"]} source chains',
        provenance_tone,
    )

    st.markdown(
        badge(readiness_label, readiness_tone)
        + structure_badge
        + deadline_badge
        + provenance_badge,
        unsafe_allow_html=True,
    )

    if demo["graph_stale"] or demo["provenance_stale"]:
        st.warning(
            "A human correction is newer than the current graph/provenance snapshot. "
            "Rebuild Operational graph and Provenance review before presenting this project."
        )

    if p["code"] == WIDE_PROJECT_CODE:
        if demo["demo_ready"] and not demo["graph_stale"] and not demo["provenance_stale"]:
            wide_action_centre = wide_action_centre_snapshot(DB, pid)
            render_wide_action_centre(wide_action_centre)
        else:
            st.warning(
                "WIDE Action Centre withheld until the current buyer-demo, graph and provenance gates are ready."
            )

    st.markdown("<div style='height:.65rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="go-section">What GrantOps built from this grant</div>', unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Work packages", demo["structure"]["work_packages"])
    m2.metric("Deliverables", demo["structure"]["deliverables"])
    m3.metric("Milestones", demo["structure"]["milestones"])
    m4.metric("Reporting periods", demo["structure"]["reporting_periods"])

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    v1, v2, v3, v4 = st.columns(4)
    with v1:
        st.markdown(
            '<div class="go-value-card"><div class="go-value-title">1 · Structure</div>'
            '<div class="go-value-copy">Recover the project structure from the Grant Agreement instead of rebuilding it manually in a generic project tool.</div></div>',
            unsafe_allow_html=True,
        )
    with v2:
        st.markdown(
            '<div class="go-value-card"><div class="go-value-title">2 · Schedule</div>'
            '<div class="go-value-copy">Turn explicit project months and reporting rules into calendar dates when the project start date is known.</div></div>',
            unsafe_allow_html=True,
        )
    with v3:
        st.markdown(
            '<div class="go-value-card"><div class="go-value-title">3 · Traceability</div>'
            '<div class="go-value-copy">Open an operational item and trace it back to its source document, page, exact quote and page hash.</div></div>',
            unsafe_allow_html=True,
        )
    with v4:
        st.markdown(
            '<div class="go-value-card"><div class="go-value-title">4 · Human control</div>'
            '<div class="go-value-copy">Unverified normative records stay outside the operational graph; corrections are explicit and auditable.</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:.85rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="go-section">60-second walkthrough</div>', unsafe_allow_html=True)

    s1, s2, s3, s4, s5 = st.columns(5)
    steps = [
        ("01", "Grant Agreement", "One source document becomes the starting point."),
        ("02", "Project structure", f'{demo["structure"]["total"]} structural entities recovered.'),
        ("03", "Deadlines", f'{demo["deadlines"]["resolved_structural"]} structural dates resolved.'),
        ("04", "Source proof", f'{demo["provenance"]["core_complete"]}/{demo["provenance"]["core_total"]} core provenance chains complete.'),
        ("05", "Human control", "Corrections and review gates remain explicit."),
    ]
    for col, (num, title, copy) in zip([s1, s2, s3, s4, s5], steps):
        with col:
            st.markdown(
                f'<div class="go-step"><div class="go-step-num">{num}</div>'
                f'<div class="go-value-title">{esc(title)}</div>'
                f'<div class="go-value-copy">{esc(copy)}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:.85rem'></div>", unsafe_allow_html=True)
    schedule_tab, proof_tab, control_tab = st.tabs(
        ["Operational schedule", "Show the source", "Human-control proof"]
    )

    with schedule_tab:
        st.markdown('<div class="go-section">Grant-derived schedule</div>', unsafe_allow_html=True)
        st.caption(
            "These dates are derived from explicit project-month or reporting rules. "
            "They are not manually entered demo data."
        )
        preview = demo["deadlines"]["preview"]
        if preview:
            st.dataframe(
                pd.DataFrame([{
                    "Date": d["resolved_date"],
                    "Type": d["node_type"].replace("_", " ").title(),
                    "Commitment": d["node_title"],
                    "Owner": d["node_owner"] or "—",
                    "Rule": d["relative_rule"] or d["deadline_kind"].replace("_", " ").title(),
                    "Source page": d["source_page"] if d["source_page"] is not None else "—",
                } for d in preview]),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("No resolved buyer-facing deadlines are available in the latest graph.")

    with proof_tab:
        showcase = demo["showcase"]
        if not showcase:
            st.info("No traceable structural record is available. Rebuild graph and provenance.")
        else:
            item_index = st.selectbox(
                "Choose a project item",
                range(len(showcase)),
                format_func=lambda i: showcase[i]["title"],
                key="buyer_demo_trace_item_v05",
            )
            item = showcase[item_index]

            left, right = st.columns([1.08, .92], gap="large")
            with left:
                st.markdown('<div class="go-section">Operational interpretation</div>', unsafe_allow_html=True)
                st.markdown(
                    f'{badge(item["node_type"].replace("_", " ").title(), "info")}'
                    f'{badge(item["provenance_status"].replace("_", " ").title(), "success" if item["provenance_status"] == "COMPLETE" else "warning")}',
                    unsafe_allow_html=True,
                )
                st.write(f'**{item["title"]}**')
                st.write(f'**Owner / lead:** {item["owner"] or "—"}')
                st.write(f'**Relative timing:** {item["relative_due"] or "—"}')
                st.write(
                    f'**Resolved date:** {", ".join(item["resolved_dates"]) if item["resolved_dates"] else "—"}'
                )

            with right:
                st.markdown('<div class="go-section">Source identity</div>', unsafe_allow_html=True)
                st.write(f'**Document:** {item["document_filename"] or "—"}')
                st.write(f'**Page:** {item["page_number"] if item["page_number"] is not None else "—"}')
                with st.expander("Technical integrity"):
                    st.write(f'**Document SHA-256:** `{item["document_sha256"] or "—"}`')
                    st.write(f'**Page text SHA-256:** `{item["page_text_sha256"] or "—"}`')

            st.markdown('<div class="go-section">Exact source quote</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="go-source">{esc(item["source_quote"] or "No source quote stored.")}</div>',
                unsafe_allow_html=True,
            )

    with control_tab:
        h1, h2, h3 = st.columns(3)
        h1.metric("Human-verified obligations", demo["human_control"]["verified_obligations"])
        h2.metric(
            "Verified evidence requirements",
            demo["human_control"]["verified_evidence_requirements"],
        )
        h3.metric(
            "Unverified evidence in graph",
            demo["human_control"]["unverified_evidence_nodes"],
        )

        if demo["human_control"]["unverified_evidence_nodes"] == 0:
            st.success(
                "Human gate intact: no unverified evidence requirement is presented as an operational graph record."
            )
        else:
            st.error(
                "Demo safety gate failed: an unverified evidence requirement is present in the graph."
            )

        st.markdown(
            '<div class="go-panel">'
            '<div class="go-row-title">What this demo does not claim</div>'
            '<div class="go-health">'
            'GrantOps does not replace the EU Funding & Tenders Portal, institutional finance systems or human legal/compliance judgement. '
            'The demo shows deterministic project-structure recovery, deadline derivation, provenance and human-controlled operationalization.'
            '</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
    if demo["demo_ready"]:
        st.success(
            "Buyer-demo gate READY for this project. The remaining work before pilot outreach is presentation polish and the commercial one-page."
        )
    else:
        st.warning(
            "Buyer-demo gate is not ready. Refresh the graph/provenance state before using this project in an external demo."
        )


# B — EXECUTIVE INTELLIGENCE DASHBOARD
elif page == "Overview":
    page_header(p, "Executive intelligence")

    m = metrics(DB, pid)
    ev_total = len(ev)
    ev_ready = sum(e["status"] in {"READY", "ACCEPTED"} for e in ev)
    ev_missing = sum(e["status"] == "MISSING" for e in ev)
    evidence_pct = round((ev_ready / ev_total) * 100) if ev_total else 0
    verified_pct = round((m["verified"] / m["records"]) * 100) if m["records"] else 0
    blocked = sum(r["status"] == "BLOCKED" for r in rs)

    health = "On track"
    health_tone = "success"
    if m["overdue"] or blocked:
        health = "Attention required"
        health_tone = "danger"
    elif m["due30"] or ev_missing:
        health = "Watch"
        health_tone = "warning"

    st.markdown(
        f'{badge("Project health: " + health, health_tone)}'
        f'{badge(f"{verified_pct}% verified", "success" if verified_pct >= 80 else "warning")}'
        f'{badge(f"{evidence_pct}% evidence ready", "success" if evidence_pct >= 80 else "warning")}',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open records", sum(r["status"] != "DONE" for r in rs))
    c2.metric("Due in 30 days", m["due30"])
    c3.metric("Overdue", m["overdue"])
    c4.metric("Evidence missing", ev_missing)

    left, right = st.columns([1.18, 1], gap="large")

    with left:
        st.markdown('<div class="go-section">Attention required</div>', unsafe_allow_html=True)
        attention = attention_items(rs, ev)
        if not attention:
            st.markdown('<div class="go-empty">No urgent operational exceptions.</div>', unsafe_allow_html=True)
        else:
            for label, title, meta, tone in attention[:6]:
                st.markdown(
                    f'<div class="go-row">'
                    f'{badge(label, tone)}'
                    f'<div class="go-row-title" style="margin-top:.45rem">{esc(title)}</div>'
                    f'<div class="go-row-meta">{esc(meta)}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with right:
        st.markdown('<div class="go-section">Operational readiness</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="go-panel">'
            f'<div class="go-row-title">Verified operational records</div>'
            f'<div class="go-health">{m["verified"]} of {m["records"]} records have human-verified provenance.</div>'
            f'<div style="height:.45rem"></div>'
            f'<div class="go-row-title">Evidence readiness</div>'
            f'<div class="go-health">{ev_ready} of {ev_total} evidence items are ready or accepted.</div>'
            f'<div style="height:.45rem"></div>'
            f'<div class="go-row-title">Execution risk</div>'
            f'<div class="go-health">{m["overdue"]} overdue · {blocked} blocked · {ev_missing} missing evidence.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="go-section">Upcoming operational commitments</div>', unsafe_allow_html=True)
    upcoming = [r for r in rs if r["status"] != "DONE"]
    if upcoming:
        st.dataframe(
            pd.DataFrame(clean_records(upcoming)),
            width="stretch",
            hide_index=True,
        )
    else:
        st.markdown('<div class="go-empty">No open operational records.</div>', unsafe_allow_html=True)


# C — OPERATIONAL / EVIDENCE INVESTIGATION WORKSPACE
elif page == "Operations":
    page_header(p, "Operational control")

    f1, f2, f3 = st.columns(3)
    type_options = ["All"] + sorted({r["record_type"] for r in rs})
    status_options = ["All"] + ["OPEN", "IN_PROGRESS", "DONE", "BLOCKED"]
    ver_options = ["All", "HUMAN_VERIFIED", "UNVERIFIED"]
    type_filter = f1.selectbox("Record type", type_options, format_func=lambda x: TYPE_LABEL.get(x, x))
    status_filter = f2.selectbox("Status", status_options, format_func=lambda x: STATUS_LABEL.get(x, x))
    ver_filter = f3.selectbox("Verification", ver_options, format_func=lambda x: VER_LABEL.get(x, x))

    filtered = [
        r for r in rs
        if (type_filter == "All" or r["record_type"] == type_filter)
        and (status_filter == "All" or r["status"] == status_filter)
        and (ver_filter == "All" or r["verification_status"] == ver_filter)
    ]

    if not filtered:
        st.markdown('<div class="go-empty">No records match the selected filters.</div>', unsafe_allow_html=True)
    else:
        labels = {
            r["id"]: f'{TYPE_LABEL.get(r["record_type"], r["record_type"])} · {r["title"]}'
            for r in filtered
        }
        selected_id = st.selectbox(
            "Open operational record",
            options=list(labels),
            format_func=lambda rid: labels[rid],
        )
        r = next(x for x in filtered if x["id"] == selected_id)

        left, right = st.columns([1.08, .92], gap="large")
        with left:
            st.markdown(
                badge(TYPE_LABEL.get(r["record_type"], r["record_type"]), "info")
                + badge(STATUS_LABEL.get(r["status"], r["status"]), status_tone(r["status"]))
                + badge(VER_LABEL.get(r["verification_status"], r["verification_status"]), verification_tone(r["verification_status"])),
                unsafe_allow_html=True,
            )
            st.markdown(f"### {r['title']}")
            if r["description"]:
