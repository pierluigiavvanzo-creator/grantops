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
                st.write(r["description"])

            a, b = st.columns(2)
            a.metric("Due", fmt_date(r["due_date"]))
            b.metric("Owner", r["owner"] or "Not assigned")

            st.markdown('<div class="go-section">Source & provenance</div>', unsafe_allow_html=True)
            if r["verification_status"] == "HUMAN_VERIFIED":
                st.markdown(
                    f'<div class="go-source">'
                    f'<strong>Source:</strong> page {esc(r["source_page"])} · {esc(r["source_section"])}<br><br>'
                    f'“{esc(r["source_quote"])}”'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.caption(f"Source text SHA-256: {r['source_text_sha256'] or '—'}")
            else:
                st.warning("This record is unverified and must not be treated as an authoritative grant requirement.")

            st.markdown('<div class="go-section">Record status</div>', unsafe_allow_html=True)
            new_status = st.selectbox(
                "Current status",
                ["OPEN", "IN_PROGRESS", "DONE", "BLOCKED"],
                index=["OPEN", "IN_PROGRESS", "DONE", "BLOCKED"].index(r["status"]),
                format_func=lambda x: STATUS_LABEL.get(x, x),
                key=f"record_status_{r['id']}",
            )
            if new_status != r["status"]:
                if st.button("Save status", type="primary", key=f"save_status_{r['id']}"):
                    update_record_status(DB, r["id"], new_status)
                    st.rerun()

        with right:
            st.markdown('<div class="go-section">Evidence for this record</div>', unsafe_allow_html=True)
            record_ev = [e for e in ev if e["obligation_id"] == r["id"]]
            if not record_ev:
                st.markdown('<div class="go-empty">No evidence items linked yet.</div>', unsafe_allow_html=True)
            else:
                for e in record_ev:
                    st.markdown(
                        f'<div class="go-row">'
                        f'{badge(STATUS_LABEL.get(e["status"], e["status"]), status_tone(e["status"]))}'
                        f'<div class="go-row-title" style="margin-top:.4rem">{esc(e["label"])}</div>'
                        f'<div class="go-row-meta">{esc(e["evidence_type"])} · {esc(e["location"] or "No repository location")}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown('<div class="go-section">Recent audit events</div>', unsafe_allow_html=True)
            related = [
                a for a in audit_events(DB, pid)
                if a.get("entity_id") == r["id"] or (a.get("entity_type") == "OBLIGATION" and a.get("entity_id") == r["id"])
            ][:5]
            if not related:
                st.markdown('<div class="go-empty">No record-specific audit events.</div>', unsafe_allow_html=True)
            else:
                for a in related:
                    st.markdown(
                        f'<div class="go-row">'
                        f'<div class="go-row-title">{esc(a["event_type"])}</div>'
                        f'<div class="go-row-meta">{esc(a["detail"])} · {esc(a["created_at"])}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    with st.expander("Add operational record"):
        with st.form("new_record", clear_on_submit=True):
            typ = st.selectbox("Type", list(TYPE_LABEL), format_func=lambda x: TYPE_LABEL[x])
            title = st.text_input("Title")
            description = st.text_area("Description")
            c1, c2, c3 = st.columns(3)
            due = c1.date_input("Due date", value=None)
            owner = c2.text_input("Owner")
            ver = c3.selectbox("Verification", ["UNVERIFIED", "HUMAN_VERIFIED"], format_func=lambda x: VER_LABEL[x])
            source_page = source_section = source_quote = source_hash = None
            if ver == "HUMAN_VERIFIED":
                source_page = st.text_input("Source page")
                source_section = st.text_input("Source section")
                source_quote = st.text_area("Exact reviewed source quote")
                source_hash = st.text_input("Source text SHA-256")
            if st.form_submit_button("Add record"):
                try:
                    add_record(
                        DB, pid, typ, title, description,
                        due.isoformat() if due else None,
                        owner or None, "OPEN", ver,
                        source_page or None, source_section or None,
                        source_quote or None, source_hash or None,
                    )
                    st.success("Operational record added.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


elif page == "Operational graph":
    page_header(p, "Grant operational graph")

    st.markdown(
        '<div class="go-panel"><div class="go-row-title">Safety model</div>'
        '<div class="go-health">Annex 1 structural entities may enter the graph as PROPOSED. '
        'Normative obligations and evidence requirements enter only when HUMAN_VERIFIED. '
        'Building the graph does not create or activate operational obligations.</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)

    graph_run = latest_operational_graph_run(DB, pid)
    left_build, right_build = st.columns([1, 2])
    build_label = "Rebuild from latest sources" if graph_run else "Build operational graph"

    if left_build.button(build_label, type="primary", key="build_operational_graph_v04"):
        try:
            with st.spinner("Building deterministic grant graph and resolving deadlines…"):
                result = build_operational_graph(DB, pid)
            st.success(
                f'Graph run #{result["id"]} built. '
                f'{result["structural_node_count"]} structural entities included.'
            )
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    right_build.caption(
        "Versioned build: previous graph runs remain preserved. "
        "Relative event deadlines stay unresolved until their trigger date is known."
    )

    graph_run = latest_operational_graph_run(DB, pid)
    if not graph_run:
        st.info("Build the graph after Annex 1 has been parsed.")
    else:
        summary = operational_graph_summary(DB, graph_run["id"])
        nodes = operational_graph_nodes(DB, graph_run["id"])
        edges = operational_graph_edges(DB, graph_run["id"])
        deadlines = operational_graph_deadlines(DB, graph_run["id"])
        evidence_safety = operational_graph_evidence_safety(DB, pid, graph_run["id"])

        st.markdown('<div class="go-section">Graph readiness</div>', unsafe_allow_html=True)
        g1, g2, g3, g4, g5 = st.columns(5)
        g1.metric("Structural entities", summary["structural_node_count"])
        g2.metric("Verified obligations", summary["verified_obligation_count"])
        g3.metric("Relations", summary["edge_count"])
        g4.metric("Resolved deadlines", summary["resolved_deadline_count"])
        g5.metric("Unresolved deadlines", summary["deadline_count"] - summary["resolved_deadline_count"])
        st.caption(
            f'Graph {summary["graph_version"]} · run #{summary["id"]} · '
            f'Annex 1 run #{summary["annex1_run_id"]} · state {summary["status"]}'
        )

        st.markdown('<div class="go-section">Operational structure</div>', unsafe_allow_html=True)
        structural_rows = []
        for n in nodes:
            if n["node_type"] in {"PROJECT", "RESPONSIBLE_PARTY"}:
                continue
            meta = json.loads(n["metadata_json"] or "{}")
            structural_rows.append({
                "Type": n["node_type"].replace("_", " ").title(),
                "Record": n["title"],
                "Owner": n["owner"] or "—",
                "Verification": n["verification_status"],
                "Source page": n["source_page"] if n["source_page"] is not None else "—",
                "Relative due": (
                    f'M{meta.get("due_month")}'
                    if meta.get("due_month") is not None
                    else (
                        f'M{meta.get("month_from")}–M{meta.get("month_to")}'
                        if meta.get("month_from") is not None else "—"
                    )
                ),
            })
        if structural_rows:
            st.dataframe(pd.DataFrame(structural_rows), width="stretch", hide_index=True)
        else:
            st.markdown('<div class="go-empty">No graph entities yet.</div>', unsafe_allow_html=True)

        st.markdown('<div class="go-section">Deadline engine</div>', unsafe_allow_html=True)
        if deadlines:
            st.dataframe(
                pd.DataFrame([{
                    "Entity": d["node_title"],
                    "Type": d["node_type"].replace("_", " ").title(),
                    "Deadline": d["deadline_kind"].replace("_", " ").title(),
                    "Relative rule": d["relative_rule"] or "—",
                    "Resolved date": d["resolved_date"] or "Awaiting trigger",
                    "State": d["resolution_status"],
                } for d in deadlines]),
                width="stretch",
                hide_index=True,
            )

        st.markdown('<div class="go-section">Responsibility & dependency relations</div>', unsafe_allow_html=True)
        if edges:
            relation_filter = st.selectbox(
                "Relation type",
                ["ALL"] + sorted({e["relation_type"] for e in edges}),
                key="graph_relation_filter_v04",
            )
            filtered_edges = [e for e in edges if relation_filter == "ALL" or e["relation_type"] == relation_filter]
            st.dataframe(
                pd.DataFrame([{
                    "From": e["from_title"] or e["from_node_key"],
                    "Relation": e["relation_type"].replace("_", " ").title(),
                    "To": e["to_title"] or e["to_node_key"],
                    "Basis": e["basis"],
                } for e in filtered_edges]),
                width="stretch",
                hide_index=True,
            )

        st.markdown('<div class="go-section">Evidence safety</div>', unsafe_allow_html=True)
        e1, e2, e3 = st.columns(3)
        e1.metric("Verified requirements", evidence_safety["verified_evidence_requirements"])
        e2.metric("Evidence items", evidence_safety["evidence_items"])
        e3.metric("Unverified candidates excluded", evidence_safety["pending_unverified_evidence_candidates_excluded"])
        if evidence_safety["non_verified_evidence_nodes_in_graph"]:
            st.error("Safety regression: a non-verified evidence requirement entered the graph.")
        else:
            st.success("Evidence gate intact: no unverified evidence requirement entered the graph.")

elif page == "Provenance review":
    page_header(p, "Provenance review")

    st.markdown(
        '<div class="go-panel"><div class="go-row-title">Why this exists</div>'
        '<div class="go-health">Every structural record and derived deadline should be traceable '
        'back through document → extraction → page → graph entity. '
        'The review is read-oriented and does not alter obligations or review decisions.</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)

    latest_graph = latest_operational_graph_run(DB, pid)
    latest_prov = latest_provenance_review(DB, pid)

    build_col, info_col = st.columns([1, 2])
    label = "Rebuild provenance review" if latest_prov else "Build provenance review"
    if build_col.button(label, type="primary", key="build_provenance_v041"):
        try:
            if not latest_graph:
                raise ValueError("Build the operational graph first.")
            with st.spinner("Resolving document, extraction, page and graph lineage…"):
                result = build_provenance_review(DB, pid, latest_graph["id"])
            st.success(
                f'Provenance review #{result["id"]} built for graph run #{result["graph_run_id"]}.'
            )
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    info_col.caption(
        "A new review run is versioned; previous reviews remain available in the database. "
        "No source gap is silently filled."
    )

    latest_prov = latest_provenance_review(DB, pid)
    if not latest_prov:
        st.info("Build an operational graph, then build the provenance review.")
    else:
        summary = provenance_review_summary(DB, latest_prov["id"])
        items = list_provenance_items(DB, latest_prov["id"])

        st.markdown('<div class="go-section">Provenance gate</div>', unsafe_allow_html=True)
        p1, p2, p3, p4, p5 = st.columns(5)
        p1.metric(
            "Structural nodes",
            f'{summary["node_complete_count"]}/{summary["node_item_count"]}',
        )
        p2.metric(
            "Structural deadlines",
            f'{summary["deadline_complete_count"]}/{summary["deadline_item_count"]}',
        )
        p3.metric("Source documents", summary["document_count"])
        p4.metric("Graph relations", summary["edge_count"])
        p5.metric("Orphan relations", summary["orphan_edge_count"])

        if summary["status"] == "PASS":
            st.success("Provenance gate PASS: structural nodes and deadlines have complete source chains.")
        else:
            st.warning("Provenance gate requires review. Inspect incomplete or ambiguous chains below.")

        st.caption(
            f'Provenance {summary["provenance_version"]} · review #{summary["id"]} · '
            f'graph run #{summary["graph_run_id"]} · state {summary["status"]}'
        )

        st.markdown('<div class="go-section">Traceability matrix</div>', unsafe_allow_html=True)
        status_options = ["ALL"] + sorted({x["provenance_status"] for x in items})
        status_filter = st.selectbox(
            "Provenance state",
            status_options,
            key="provenance_status_filter_v041",
        )
        filtered = [
            x for x in items
            if status_filter == "ALL" or x["provenance_status"] == status_filter
        ]

        st.dataframe(
            pd.DataFrame([{
                "Item": x["graph_node_key"] if x["item_type"] == "GRAPH_NODE"
                        else f'{x["graph_node_key"]} · deadline #{x["graph_deadline_id"]}',
                "Layer": x["item_type"].replace("_", " ").title(),
                "Document": x["document_filename"] or "—",
                "Page": x["page_number"] if x["page_number"] is not None else "—",
                "Strategy": x["source_strategy"].replace("_", " ").title(),
                "State": x["provenance_status"],
            } for x in filtered]),
            width="stretch",
            hide_index=True,
        )

        if filtered:
            labels = [
                f'{x["item_key"]} · {x["provenance_status"]}'
                for x in filtered
            ]
            chosen = st.selectbox(
                "Inspect provenance chain",
                range(len(filtered)),
                format_func=lambda i: labels[i],
                key="provenance_chain_select_v041",
            )
            item = filtered[chosen]
            chain = json.loads(item["chain_json"])
            warnings = json.loads(item["warnings_json"])

            c1, c2 = st.columns([1, 1])
            with c1:
                st.markdown('<div class="go-section">Source identity</div>', unsafe_allow_html=True)
                st.write(f'**Document:** {item["document_filename"] or "—"}')
                st.write(f'**Document SHA-256:** `{item["document_sha256"] or "—"}`')
                st.write(f'**Extraction:** {item["extraction_id"] or "—"}')
                st.write(f'**Page:** {item["page_number"] if item["page_number"] is not None else "—"}')
                st.write(f'**Page text SHA-256:** `{item["page_text_sha256"] or "—"}`')
                st.write(f'**Strategy:** {item["source_strategy"]}')
            with c2:
                st.markdown('<div class="go-section">Chain</div>', unsafe_allow_html=True)
                for step in chain:
                    detail = " · ".join(
                        f"{k}={v}" for k, v in step.items()
                        if k not in {"layer", "ref"} and v not in {None, ""}
                    )
                    st.write(
                        f'**{step.get("layer")}** → `{step.get("ref")}`'
                        + (f" · {detail}" if detail else "")
                    )

            st.markdown('<div class="go-section">Exact source quote</div>', unsafe_allow_html=True)
            st.code(item["source_quote"] or "No source quote stored.", language=None)
            if warnings:
                st.warning(" · ".join(warnings))

elif page == "Human corrections":
    page_header(p, "Human corrections & audit")

    st.markdown(
        '<div class="go-panel"><div class="go-row-title">Human-control boundary</div>'
        '<div class="go-health">Operational fields may be corrected by an identified reviewer with a reason. '
        'Source page, source quote, source hash and verification provenance are not editable here. '
        'Reopening an approved candidate temporarily removes HUMAN_VERIFIED status until it is reviewed again.</div></div>',
        unsafe_allow_html=True,
    )

    if corrections_after_latest_graph(DB, pid):
        st.warning(
            "A human correction is newer than the latest operational graph. "
            "Rebuild Operational graph, then Provenance review, before relying on the current graph."
        )

    edit_tab, reopen_tab, history_tab = st.tabs(
        ["Edit operational record", "Reopen review", "Change history"]
    )

    with edit_tab:
        editable_records = correction_operational_records(DB, pid)
        if not editable_records:
            st.info("No operational records exist for this project.")
        else:
            record_id = st.selectbox(
                "Operational record",
                [r["id"] for r in editable_records],
                format_func=lambda rid: next(
                    f'#{r["id"]} · {r["record_type"].replace("_", " ").title()} · {r["title"]}'
                    for r in editable_records if r["id"] == rid
                ),
                key="correction_record_v042",
            )
            record = next(r for r in editable_records if r["id"] == record_id)

            left, right = st.columns([1.25, 1])
            with left:
                st.markdown('<div class="go-section">Editable operational fields</div>', unsafe_allow_html=True)
                title_value = st.text_input(
                    "Title",
                    value=record["title"] or "",
                    key=f"corr_title_{record_id}",
                )
                description_value = st.text_area(
                    "Description",
                    value=record["description"] or "",
                    key=f"corr_desc_{record_id}",
                )
                owner_value = st.text_input(
                    "Owner",
                    value=record["owner"] or "",
                    key=f"corr_owner_{record_id}",
                )
                due_value = st.text_input(
                    "Due date · YYYY-MM-DD or blank",
                    value=record["due_date"] or "",
                    key=f"corr_due_{record_id}",
                )
                status_values = ["OPEN", "IN_PROGRESS", "DONE", "BLOCKED"]
                current_status = record["status"] if record["status"] in status_values else "OPEN"
                status_value = st.selectbox(
                    "Operational status",
                    status_values,
                    index=status_values.index(current_status),
                    format_func=lambda x: x.replace("_", " ").title(),
                    key=f"corr_status_{record_id}",
                )

            with right:
                st.markdown('<div class="go-section">Immutable source identity</div>', unsafe_allow_html=True)
                st.write(f'**Verification:** {record["verification_status"]}')
                st.write(f'**Source page:** {record["source_page"] or "—"}')
                st.write(f'**Source section:** {record["source_section"] or "—"}')
                st.write(f'**Source SHA-256:** `{record["source_text_sha256"] or "—"}`')
                with st.expander("Exact source quote"):
                    st.write(record["source_quote"] or "—")

                actor = st.text_input(
                    "Reviewer / editor",
                    key=f"corr_actor_{record_id}",
                )
                reason = st.text_area(
                    "Reason for correction",
                    key=f"corr_reason_{record_id}",
                )
                immutable_ok = st.checkbox(
                    "I confirm that this correction must not alter the source quote, page or hash.",
                    key=f"corr_source_confirm_{record_id}",
                )

                if st.button(
                    "Apply audited correction",
                    type="primary",
                    disabled=not (actor.strip() and reason.strip() and immutable_ok),
                    key=f"corr_apply_{record_id}",
                ):
                    try:
                        result = edit_operational_record(
                            DB,
                            record_id,
                            actor,
                            reason,
                            {
                                "title": title_value,
                                "description": description_value,
                                "owner": owner_value,
                                "due_date": due_value,
                                "status": status_value,
                            },
                            confirm_source_immutable=immutable_ok,
                        )
                        st.success(
                            f'Correction event #{result["event_id"]} recorded. '
                            "Rebuild graph and provenance before operational reliance."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    with reopen_tab:
        finalized = correction_finalized_candidates(DB, pid)
        if not finalized:
            st.info("No approved or rejected candidate is available to reopen.")
        else:
            candidate_id = st.selectbox(
                "Finalized candidate",
                [c["id"] for c in finalized],
                format_func=lambda cid: next(
                    f'#{c["id"]} · {c["review_status"].title()} · '
                    f'{c["record_type"].replace("_", " ").title()} · page {c["source_page"]}'
                    for c in finalized if c["id"] == cid
                ),
                key="reopen_candidate_v042",
            )
            candidate = next(c for c in finalized if c["id"] == candidate_id)

            st.write(f'**Current decision:** {candidate["review_status"]}')
            st.write(f'**Previous reviewer:** {candidate["reviewer"] or "—"}')
            st.write(f'**Promoted record:** {candidate["promoted_record_id"] or "—"}')
            if candidate["promoted_record_id"]:
                st.warning(
                    "Reopening this approved candidate will keep the operational record, "
                    "but mark it UNVERIFIED and BLOCKED until the candidate is approved again. "
                    "Re-approval reuses the same record ID."
                )
            else:
                st.info("This rejected candidate has no promoted operational record.")

            reopen_actor = st.text_input(
                "Reviewer reopening the decision",
                key=f"reopen_actor_{candidate_id}",
            )
            reopen_reason = st.text_area(
                "Reason for reopening",
                key=f"reopen_reason_{candidate_id}",
            )
            reopen_ok = st.checkbox(
                "I understand the verification-state effect and want to reopen this decision.",
                key=f"reopen_confirm_{candidate_id}",
            )

            if st.button(
                "Reopen for human review",
                type="primary",
                disabled=not (reopen_actor.strip() and reopen_reason.strip() and reopen_ok),
                key=f"reopen_apply_{candidate_id}",
            ):
                try:
                    result = reopen_candidate(
                        DB,
                        candidate_id,
                        reopen_actor,
                        reopen_reason,
                        confirm_effect=reopen_ok,
                    )
                    st.success(
                        f'Candidate #{result["candidate_id"]} reopened as Needs clarification. '
                        "Return to Grant Agreement → Review queue to review it again."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with history_tab:
        changes = list_change_events(DB, pid)
        if not changes:
            st.markdown('<div class="go-empty">No human correction events recorded.</div>', unsafe_allow_html=True)
        else:
            st.dataframe(
                pd.DataFrame([{
                    "Event": x["id"],
                    "When": x["created_at"],
                    "Entity": f'{x["entity_type"]} #{x["entity_id"]}',
                    "Action": x["action"].replace("_", " ").title(),
                    "Actor": x["actor"],
                    "Reason": x["reason"],
                    "Graph rebuild": "Required" if x["requires_graph_rebuild"] else "No",
                } for x in changes]),
                width="stretch",
                hide_index=True,
            )

            selected_event = st.selectbox(
                "Inspect change event",
                [x["id"] for x in changes],
                format_func=lambda eid: next(
                    f'#{x["id"]} · {x["action"]} · {x["actor"]}'
                    for x in changes if x["id"] == eid
                ),
                key="change_event_select_v042",
            )
            event = next(x for x in changes if x["id"] == selected_event)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="go-section">Before</div>', unsafe_allow_html=True)
                st.json(json.loads(event["before_json"]))
            with c2:
                st.markdown('<div class="go-section">After</div>', unsafe_allow_html=True)
                st.json(json.loads(event["after_json"]))
            st.markdown('<div class="go-section">Source integrity / impact</div>', unsafe_allow_html=True)
            st.json(json.loads(event["source_integrity_json"]))

elif page == "Evidence":
    page_header(p, "Evidence control")
    total = len(ev)
    missing = sum(e["status"] == "MISSING" for e in ev)
    progress = sum(e["status"] == "IN_PROGRESS" for e in ev)
    ready = sum(e["status"] in {"READY", "ACCEPTED"} for e in ev)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Evidence items", total)
    c2.metric("Missing", missing)
    c3.metric("In progress", progress)
    c4.metric("Ready / accepted", ready)

    st.markdown('<div class="go-section">Evidence register</div>', unsafe_allow_html=True)
    if ev:
        st.dataframe(
            pd.DataFrame([{
                "Operational record": e["obligation_title"],
                "Evidence": e["label"],
                "Type": e["evidence_type"],
                "Status": STATUS_LABEL.get(e["status"], e["status"]),
                "Location": e["location"] or "—",
            } for e in ev]),
            width="stretch",
            hide_index=True,
        )
    else:
        st.markdown('<div class="go-empty">No evidence items yet.</div>', unsafe_allow_html=True)

    with st.expander("Add evidence item"):
        if not rs:
            st.info("Create an operational record first.")
        else:
            with st.form("new_evidence", clear_on_submit=True):
                oid = st.selectbox(
                    "Operational record",
                    [r["id"] for r in rs],
                    format_func=lambda x: next(r["title"] for r in rs if r["id"] == x),
                )
                label = st.text_input("Evidence label")
                a, b = st.columns(2)
                etype = a.selectbox("Type", ["DOCUMENT", "CHECKLIST", "LINK", "DATASET", "OTHER"])
                status = b.selectbox("Status", ["MISSING", "IN_PROGRESS", "READY", "ACCEPTED"], format_func=lambda x: STATUS_LABEL.get(x, x))
                location = st.text_input("Repository / location")
                notes = st.text_area("Notes")
                if st.form_submit_button("Add evidence"):
                    add_evidence(DB, oid, label, etype, location or None, status, notes or None)
                    st.success("Evidence item added.")
                    st.rerun()


elif page == "Grant Agreement":
    page_header(p, "Authoritative source")

    ds = documents(DB, pid)
    refresh_context_for_project(DB, pid)
    doc_tab, extraction_tab, annex1_tab, review_tab = st.tabs(
        ["Document custody", "Extraction", "Annex 1 structure", "Review queue"]
    )

    with doc_tab:
        st.markdown(
            '<div class="go-panel"><div class="go-row-title">Grant Agreement custody</div>'
            '<div class="go-health">PDFs remain local. GrantOps records SHA-256 before extraction. '
            'Nothing extracted becomes an operational record without human review.</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

        st.markdown('<div class="go-section">Staged documents</div>', unsafe_allow_html=True)
        if ds:
            st.dataframe(
                pd.DataFrame([{
                    "ID": d["id"],
                    "File": d["filename"],
                    "Status": d["status"],
                    "Bytes": d["byte_count"],
                    "SHA-256": d["sha256"],
                } for d in ds]),
                width="stretch",
                hide_index=True,
            )
        else:
            st.markdown(
                '<div class="go-empty">No Grant Agreement staged for this project.</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="go-section">Stage a Grant Agreement</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "PDF only · maximum 25 MiB · extraction is local",
            type=["pdf"],
            key="ga_upload_v02",
        )
        if uploaded is not None and st.button(
            "Stage locally",
            type="primary",
            key="stage_ga_v02",
        ):
            tmp = Path(tempfile.gettempdir()) / uploaded.name
            tmp.write_bytes(uploaded.getbuffer())
            try:
                result = stage_pdf(DB, pid, tmp, UPLOADS)
                st.success("Grant Agreement staged and hashed.")
                st.code(result["sha256"], language=None)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
            finally:
                try:
                    tmp.unlink()
                except Exception:
                    pass

    with extraction_tab:
        st.markdown('<div class="go-section">Bounded local extraction</div>', unsafe_allow_html=True)
        st.caption(
            "pypdf only · no OCR · no LLM · no network request · max 25 MiB · max 250 pages."
        )

        if not ds:
            st.info("Stage a Grant Agreement first.")
        else:
            selected_doc_id = st.selectbox(
                "Grant Agreement",
                [d["id"] for d in ds],
                format_func=lambda doc_id: next(
                    f'{d["filename"]} · '
                    f'{"EXTRACTED_REVIEW_PENDING" if extraction_for_document(DB, doc_id) else d["status"]}'
                    for d in ds if d["id"] == doc_id
                ),
                key="ga_extract_doc",
            )
            selected_doc = next(d for d in ds if d["id"] == selected_doc_id)
            current_ext = extraction_for_document(DB, selected_doc_id)

            if current_ext:
                summary = extraction_summary(DB, current_ext["id"])
                st.success("Text extraction already completed for this exact document hash.")
            else:
                summary = None
                if st.button(
                    "Extract text & detect candidates",
                    type="primary",
                    key="run_ga_extraction",
                ):
                    try:
                        with st.spinner("Extracting locally and detecting conservative candidates…"):
                            summary = extract_pdf_and_detect(DB, selected_doc_id)
                        st.success("Extraction completed. Candidates are ready for human review.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

            if current_ext:
                summary = extraction_summary(DB, current_ext["id"])

            if summary:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Pages", summary["page_count"])
                c2.metric("Extracted characters", f'{summary["total_text_chars"]:,}')
                c3.metric("Candidates", summary["candidate_count"])
                c4.metric("OCR used", "No")

                counts = summary.get("candidate_counts_by_type", {})
                st.markdown('<div class="go-section">Candidate summary</div>', unsafe_allow_html=True)
                if counts:
                    st.dataframe(
                        pd.DataFrame([
                            {
                                "Type": TYPE_LABEL.get(record_type, record_type),
                                "Candidates": count,
                            }
                            for record_type, count in sorted(counts.items())
                        ]),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.warning(
                        "No candidates were detected by the conservative deterministic rules. "
                        "This is not evidence that the Grant Agreement contains no obligations."
                    )

                context_counts = summary.get("context_counts", {})
                st.markdown('<div class="go-section">Context quality</div>', unsafe_allow_html=True)
                known_context = {
                    "READY",
                    "CONTEXT_REQUIRED",
                    "PARENT_CONTROL",
                    "MERGE_REQUIRED",
                    "TEMPLATE_ONLY",
                }
                other_blocked = sum(
                    count for status, count in context_counts.items()
                    if status not in known_context
                )
                q1, q2, q3, q4, q5 = st.columns(5)
                q1.metric("Promotable now", summary.get("promotable_count", 0))
                q2.metric("Context required", context_counts.get("CONTEXT_REQUIRED", 0))
                q3.metric("Parent / merge", context_counts.get("PARENT_CONTROL", 0) + context_counts.get("MERGE_REQUIRED", 0))
                q4.metric("Template only", context_counts.get("TEMPLATE_ONLY", 0))
                q5.metric("Other blocked", other_blocked)
                accounted = sum(context_counts.values())
                st.caption(f"Context accounting: {accounted}/{summary.get('candidate_count', 0)} candidates classified.")
                st.caption(f'Document profile: {summary.get("document_kind", "UNKNOWN")} · context analysis v0.2.3a')

                st.markdown(
                    '<div class="go-panel">'
                    '<div class="go-row-title">Safety state</div>'
                    '<div class="go-health">Candidates are proposals only. '
                    'They are not yet operational obligations and are not shown in the workspace '
                    'until a reviewer explicitly approves them.</div></div>',
                    unsafe_allow_html=True,
                )


    with annex1_tab:
        st.markdown('<div class="go-section">Project structure from Annex 1</div>', unsafe_allow_html=True)
        st.caption(
            "Deterministic structural parser · stored extracted pages only · no OCR · no LLM · no network. "
            "Results remain PROPOSED and do not become operational records automatically."
        )
    
        extracted_docs = []
        for d in ds:
            ext = extraction_for_document(DB, d["id"])
            if ext:
                extracted_docs.append((d, ext))
    
        if not extracted_docs:
            st.info("Extract a Grant Agreement first.")
        else:
            annex_doc_id = st.selectbox(
                "Extracted Grant Agreement",
                [d["id"] for d, _ in extracted_docs],
                format_func=lambda doc_id: next(
                    d["filename"] for d, _ in extracted_docs if d["id"] == doc_id
                ),
                key="annex1_doc_v03",
            )
            annex_doc, annex_ext = next(
                (d, ext) for d, ext in extracted_docs if d["id"] == annex_doc_id
            )
    
            current_run = latest_annex1_run_for_extraction(DB, annex_ext["id"])
    
            run_col, info_col = st.columns([1, 2])
            run_label = "Re-run Annex 1 parser" if current_run else "Parse Annex 1 structure"
            if run_col.button(run_label, type="primary", key="run_annex1_v03"):
                try:
                    with st.spinner("Parsing Annex 1 structure from stored extracted pages…"):
                        parse_annex1_extraction(DB, annex_ext["id"])
                    st.success("Annex 1 structure parsed as PROPOSED entities.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
    
            info_col.markdown(
                '<div class="go-panel"><div class="go-row-title">Safety state</div>'
                '<div class="go-health">Work packages, deliverables, milestones and reporting periods '
                'are structural proposals only. No operational obligation is created by this parser.</div></div>',
                unsafe_allow_html=True,
            )
    
            current_run = latest_annex1_run_for_extraction(DB, annex_ext["id"])
            if current_run:
                wps = annex1_work_packages(DB, current_run["id"])
                dels = annex1_deliverables(DB, current_run["id"])
                mss = annex1_milestones(DB, current_run["id"])
                rps = annex1_reporting_periods(DB, current_run["id"])
    
                st.markdown('<div class="go-section">Structural coverage</div>', unsafe_allow_html=True)
                a1, a2, a3, a4 = st.columns(4)
                a1.metric("Work packages", len(wps))
                a2.metric("Deliverables", len(dels))
                a3.metric("Milestones", len(mss))
                a4.metric("Reporting periods", len(rps))
                st.caption(
                    f'Parser: {current_run["parser_version"]} · '
                    f'Annex 1 pages {current_run["source_page_from"]}–{current_run["source_page_to"]} · '
                    'all entities PROPOSED'
                )
    
                st.markdown('<div class="go-section">Work packages</div>', unsafe_allow_html=True)
                if wps:
                    st.dataframe(
                        pd.DataFrame([{
                            "WP": x["wp_code"],
                            "Name": x["name"],
                            "Lead": x["lead_beneficiary"],
                            "Start": f'M{x["start_month"]}' if x["start_month"] is not None else "—",
                            "End": f'M{x["end_month"]}' if x["end_month"] is not None else "—",
                            "Page": x["source_page"],
                            "State": x["review_status"],
                        } for x in wps]),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.warning("No Work Packages detected.")
    
                st.markdown('<div class="go-section">Deliverables</div>', unsafe_allow_html=True)
                if dels:
                    st.dataframe(
                        pd.DataFrame([{
                            "Deliverable": x["deliverable_code"],
                            "Name": x["name"],
                            "WP": x["work_package_code"],
                            "Lead": x["lead_beneficiary"],
                            "Due": f'M{x["due_month"]}' if x["due_month"] is not None else "—",
                            "Type": x["deliverable_type"],
                            "Page": x["source_page"],
                            "State": x["review_status"],
                        } for x in dels]),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.warning("No deliverables detected by the Annex 1 structural parser.")
    
                st.markdown('<div class="go-section">Milestones</div>', unsafe_allow_html=True)
                if mss:
                    st.dataframe(
                        pd.DataFrame([{
                            "Milestone": x["milestone_code"],
                            "Name": x["name"],
                            "WPs": ", ".join(json.loads(x["work_package_codes_json"])),
                            "Lead": x["lead_beneficiary"] or "—",
                            "Due": f'M{x["due_month"]}' if x["due_month"] is not None else "—",
                            "Page": x["source_page"],
                            "State": x["review_status"],
                        } for x in mss]),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.warning("No milestones detected.")
    
                st.markdown('<div class="go-section">Reporting periods</div>', unsafe_allow_html=True)
                if rps:
                    st.dataframe(
                        pd.DataFrame([{
                            "Period": x["rp_code"],
                            "From": f'M{x["month_from"]}',
                            "To": f'M{x["month_to"]}',
                            "Report": x["report_type"],
                            "Deadline rule": x["report_deadline_rule"] or "—",
                            "Page": x["source_page"],
                            "State": x["review_status"],
                        } for x in rps]),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.warning("No reporting periods detected.")
    
    with review_tab:
        st.markdown('<div class="go-section">Human review queue</div>', unsafe_allow_html=True)
        st.caption(
            "Approve promotes one candidate into the workspace as HUMAN_VERIFIED. "
            "Reject and Needs clarification do not create operational records."
        )

        project_candidates = list_candidates(DB, pid)
        if not project_candidates:
            st.info("No Grant Agreement candidates are available for review.")
        else:
            if "ga_reviewer_v021" not in st.session_state:
                st.session_state["ga_reviewer_v021"] = ""

            reviewer = st.text_input(
                "Reviewer name",
                key="ga_reviewer_v021",
                placeholder="Enter once; it stays for this review session",
            )

            f1, f2 = st.columns(2)
            review_filter = f1.selectbox(
                "Review state",
                ["PENDING", "NEEDS_CLARIFICATION", "APPROVED", "REJECTED", "ALL"],
                key="ga_review_status_filter_v021",
            )
            type_values = ["ALL"] + sorted(
                {candidate["record_type"] for candidate in project_candidates}
            )
            type_filter = f2.selectbox(
                "Candidate type",
                type_values,
                format_func=lambda value: TYPE_LABEL.get(value, value),
                key="ga_review_type_filter_v021",
            )

            filtered_candidates = list_candidates(
                DB,
                pid,
                review_status=review_filter,
                record_type=type_filter,
            )

            if not filtered_candidates:
                st.markdown(
                    '<div class="go-empty">No candidates match these filters.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="go-section">Candidates ({len(filtered_candidates)})</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(
                    pd.DataFrame([
                        {
                            "#": idx + 1,
                            "Page": c["source_page"],
                            "Type": TYPE_LABEL.get(c["record_type"], c["record_type"]),
                            "Subject": c["candidate_subject"],
                            "Context": (c.get("context_status") or "NOT_ANALYZED").replace("_", " ").title(),
                            "Applicability": (c.get("applicability") or "UNKNOWN").replace("_", " ").title(),
                            "State": c["review_status"].replace("_", " ").title(),
                        }
                        for idx, c in enumerate(filtered_candidates)
                    ]),
                    width="stretch",
                    hide_index=True,
                    height=min(290, 42 + 35 * min(len(filtered_candidates), 7)),
                )

                ids = [c["id"] for c in filtered_candidates]
                target_id = st.session_state.get("ga_candidate_target_v021")
                if target_id not in ids:
                    target_id = ids[0]
                    st.session_state["ga_candidate_target_v021"] = target_id

                selected_index = ids.index(target_id)

                st.markdown(
                    f'<div class="go-kicker">Candidate {selected_index + 1} of {len(ids)}</div>',
                    unsafe_allow_html=True,
                )

                candidate_id = st.selectbox(
                    "Open candidate",
                    ids,
                    index=selected_index,
                    format_func=lambda cid: next(
                        f'Page {c["source_page"]} · '
                        f'{TYPE_LABEL.get(c["record_type"], c["record_type"])} · '
                        f'{c["candidate_subject"]}'
                        for c in filtered_candidates
                        if c["id"] == cid
                    ),
                    key=f"ga_candidate_selector_v021_{target_id}",
                )
                st.session_state["ga_candidate_target_v021"] = candidate_id

                selected_index = ids.index(candidate_id)
                prev_id = ids[selected_index - 1] if selected_index > 0 else None
                next_id = ids[selected_index + 1] if selected_index < len(ids) - 1 else None

                nav1, nav2, nav3 = st.columns([1, 1, 3])
                if nav1.button(
                    "← Previous",
                    disabled=prev_id is None,
                    key=f"ga_prev_{candidate_id}",
                ):
                    st.session_state["ga_candidate_target_v021"] = prev_id
                    st.rerun()

                if nav2.button(
                    "Next →",
                    disabled=next_id is None,
                    key=f"ga_next_{candidate_id}",
                ):
                    st.session_state["ga_candidate_target_v021"] = next_id
                    st.rerun()

                nav3.caption(
                    "After a decision, GrantOps automatically opens the next candidate "
                    "that remains in the selected review state."
                )

                candidate = get_candidate(DB, candidate_id)

                left, right = st.columns([1.06, .94], gap="large")

                with left:
                    tone = (
                        "success" if candidate["review_status"] == "APPROVED"
                        else "danger" if candidate["review_status"] == "REJECTED"
                        else "warning" if candidate["review_status"] == "NEEDS_CLARIFICATION"
                        else "info"
                    )
                    st.markdown(
                        badge(
                            TYPE_LABEL.get(candidate["record_type"], candidate["record_type"]),
                            "info",
                        )
                        + badge(candidate["review_status"].replace("_", " ").title(), tone),
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"### {esc(candidate['candidate_subject'])}")
                    if candidate["candidate_action"]:
                        st.write(candidate["candidate_action"])

                    if candidate.get("candidate_trigger_or_due"):
                        st.info(
                            "Timing in source: "
                            + candidate["candidate_trigger_or_due"]
                            + ". GrantOps has not converted this into an absolute date."
                        )

                    blocking_reasons = []
                    warnings = []
                    try:
                        import json as _json
                        blocking_reasons = _json.loads(candidate.get("blocking_reasons_json") or "[]")
                        warnings = _json.loads(candidate.get("warnings_json") or "[]")
                    except Exception:
                        pass

                    st.markdown('<div class="go-section">Context-aware analysis</div>', unsafe_allow_html=True)
                    context_tone = "success" if candidate.get("promotable") == 1 else "warning"
                    st.markdown(
                        badge((candidate.get("context_status") or "NOT_ANALYZED").replace("_", " ").title(), context_tone)
                        + badge((candidate.get("applicability") or "UNKNOWN").replace("_", " ").title(), "info")
                        + badge(candidate.get("document_kind") or "UNKNOWN", "neutral"),
                        unsafe_allow_html=True,
                    )
                    if candidate.get("source_article") or candidate.get("source_heading"):
                        st.caption("Source structure: " + " · ".join(
                            x for x in [candidate.get("source_article"), candidate.get("source_heading")] if x
                        ))
                    if candidate.get("trigger_text"):
                        st.info("Trigger / applicability: " + candidate["trigger_text"])
                    if blocking_reasons:
                        st.warning("Promotion blocked: " + ", ".join(r.replace("_", " ") for r in blocking_reasons))
                    if warnings:
                        st.caption("Recovered/context warnings: " + ", ".join(r.replace("_", " ") for r in warnings))

                    st.markdown(
                        '<div class="go-section">Authoritative source</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div class="go-source">'
                        f'<strong>Grant Agreement · page {esc(candidate["source_page"])}</strong>'
                        f'<br><br>“{esc(candidate.get("context_quote") or candidate["source_quote"])}”'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if candidate.get("context_before"):
                        st.caption("Previous context: " + candidate["context_before"])
                    if candidate.get("context_after"):
                        st.caption("Next context: " + candidate["context_after"])
                    with st.expander("Show original detector quote"):
                        st.write(candidate["source_quote"])
                    st.caption(
                        "Source page text SHA-256: "
                        + candidate["source_text_sha256"]
                    )

                    page = ga_page_text(
                        DB,
                        candidate["extraction_id"],
                        candidate["source_page"],
                    )
                    with st.expander("Show extracted source page"):
                        if page:
                            st.text(page["text"])
                        else:
                            st.error("Source page record not found.")

                with right:
                    st.markdown(
                        '<div class="go-section">Review decision</div>',
                        unsafe_allow_html=True,
                    )

                    if candidate["review_status"] in {"APPROVED", "REJECTED"}:
                        st.markdown(
                            f'<div class="go-panel">'
                            f'<div class="go-row-title">Finalized: {esc(candidate["review_status"])}</div>'
                            f'<div class="go-health">Reviewer: {esc(candidate["reviewer"] or "—")}<br>'
                            f'Reviewed: {esc(candidate["reviewed_at"] or "—")}<br>'
                            f'Promoted record ID: {esc(candidate["promoted_record_id"] or "—")}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        if not reviewer.strip():
                            st.warning(
                                "Reviewer name required before Approve, Reject or Needs clarification."
                            )

                        page_ok = st.checkbox(
                            "I verified the source page.",
                            key=f"page_ok_v021_{candidate_id}",
                        )
                        quote_ok = st.checkbox(
                            "I verified that the quoted text matches the source.",
                            key=f"quote_ok_v021_{candidate_id}",
                        )
                        hash_ok = st.checkbox(
                            "I verified the provenance/hash chain shown by GrantOps.",
                            key=f"hash_ok_v021_{candidate_id}",
                        )
                        notes = st.text_area(
                            "Review notes",
                            key=f"review_notes_v021_{candidate_id}",
                        )

                        if candidate.get("promotable") != 1:
                            st.caption("Approve & add is disabled until context quality is READY. Reject and Needs clarification remain available.")

                        approve_col, reject_col, clarify_col = st.columns(3)

                        if approve_col.button(
                            "Approve & add",
                            type="primary",
                            disabled=(not reviewer.strip()) or candidate.get("promotable") != 1,
                            key=f"approve_v021_{candidate_id}",
                        ):
                            try:
                                result = review_candidate(
                                    DB,
                                    candidate_id,
                                    "APPROVE",
                                    reviewer,
                                    page_ok,
                                    quote_ok,
                                    hash_ok,
                                    notes,
                                )
                                st.session_state["ga_last_action_v021"] = (
                                    f'Approved candidate #{candidate_id}; '
                                    f'created operational record #{result["promoted_record_id"]}.'
                                )
                                st.session_state["ga_candidate_target_v021"] = (
                                    next_id if next_id is not None else prev_id
                                )
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

                        if reject_col.button(
                            "Reject",
                            disabled=not reviewer.strip(),
                            key=f"reject_v021_{candidate_id}",
                        ):
                            try:
                                review_candidate(
                                    DB,
                                    candidate_id,
                                    "REJECT",
                                    reviewer,
                                    page_ok,
                                    quote_ok,
                                    hash_ok,
                                    notes,
                                )
                                st.session_state["ga_last_action_v021"] = (
                                    f"Rejected candidate #{candidate_id}. No operational record was created."
                                )
                                st.session_state["ga_candidate_target_v021"] = (
                                    next_id if next_id is not None else prev_id
                                )
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

                        if clarify_col.button(
                            "Needs clarification",
                            disabled=not reviewer.strip(),
                            key=f"clarify_v021_{candidate_id}",
                        ):
                            try:
                                review_candidate(
                                    DB,
                                    candidate_id,
                                    "NEEDS_CLARIFICATION",
                                    reviewer,
                                    page_ok,
                                    quote_ok,
                                    hash_ok,
                                    notes,
                                )
                                st.session_state["ga_last_action_v021"] = (
                                    f"Candidate #{candidate_id} marked Needs clarification."
                                )
                                st.session_state["ga_candidate_target_v021"] = (
                                    next_id if next_id is not None else prev_id
                                )
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

                if st.session_state.get("ga_last_action_v021"):
                    st.success(st.session_state.pop("ga_last_action_v021"))

                current_extraction = extraction_for_document(
                    DB,
                    candidate["document_id"],
                )
                if current_extraction:
                    summary = extraction_summary(DB, current_extraction["id"])
                    review_counts = summary.get("review_counts", {})
                    st.markdown(
                        '<div class="go-section">Review progress</div>',
                        unsafe_allow_html=True,
                    )
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Pending", review_counts.get("PENDING", 0))
                    c2.metric("Approved", review_counts.get("APPROVED", 0))
                    c3.metric("Rejected", review_counts.get("REJECTED", 0))
                    c4.metric(
                        "Clarification",
                        review_counts.get("NEEDS_CLARIFICATION", 0),
                    )


elif page == "Timeline":
    page_header(p, "Deadline intelligence")
    dated = []
    undated = []
    for r in rs:
        if r["due_date"]:
            dated.append(r)
        else:
            undated.append(r)
    dated.sort(key=lambda x: x["due_date"])

    overdue = [r for r in dated if due_state(r["due_date"], r["status"]) == "overdue"]
    due_soon = [r for r in dated if due_state(r["due_date"], r["status"]) == "due_soon"]
    later = [r for r in dated if due_state(r["due_date"], r["status"]) == "normal" and r["status"] != "DONE"]

    for title, subset, tone in [
        ("Overdue", overdue, "danger"),
        ("Next 30 days", due_soon, "warning"),
        ("Later", later, "info"),
    ]:
        st.markdown(f'<div class="go-section">{title}</div>', unsafe_allow_html=True)
        if not subset:
            st.markdown('<div class="go-empty">None.</div>', unsafe_allow_html=True)
        else:
            for r in subset:
                st.markdown(
                    f'<div class="go-row">'
                    f'{badge(fmt_date(r["due_date"]), tone)}'
                    f'{badge(STATUS_LABEL.get(r["status"], r["status"]), status_tone(r["status"]))}'
                    f'<div class="go-row-title" style="margin-top:.42rem">{esc(r["title"])}</div>'
                    f'<div class="go-row-meta">{esc(TYPE_LABEL.get(r["record_type"], r["record_type"]))} · {esc(r["owner"] or "No owner")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    if undated:
        st.markdown('<div class="go-section">No due date</div>', unsafe_allow_html=True)
        for r in undated:
            st.markdown(
                f'<div class="go-row"><div class="go-row-title">{esc(r["title"])}</div>'
                f'<div class="go-row-meta">{esc(TYPE_LABEL.get(r["record_type"], r["record_type"]))} · {esc(r["owner"] or "No owner")}</div></div>',
                unsafe_allow_html=True,
            )


graph_run = latest_operational_graph_run(DB, pid)
if graph_run:
    grant_deadlines = [
        d for d in operational_graph_deadlines(DB, graph_run["id"])
        if d["resolution_status"] == "RESOLVED"
        and d["deadline_kind"] in {
            "DELIVERABLE_DUE",
            "MILESTONE_DUE",
            "REPORT_DUE",
            "REPORTING_PERIOD_END",
        }
    ]
    st.markdown('<div class="go-section">Grant-derived schedule</div>', unsafe_allow_html=True)
    st.caption(
        "Deterministic dates derived from project start + explicit Annex 1/Data Sheet month rules. "
        "These graph dates do not auto-create operational tasks."
    )
    if grant_deadlines:
        st.dataframe(
            pd.DataFrame([{
                "Date": d["resolved_date"],
                "Entity": d["node_title"],
                "Type": d["node_type"].replace("_", " ").title(),
                "Deadline": d["deadline_kind"].replace("_", " ").title(),
                "Rule": d["relative_rule"] or "—",
            } for d in grant_deadlines]),
            width="stretch",
            hide_index=True,
        )
    else:
        st.markdown('<div class="go-empty">No resolved graph deadlines.</div>', unsafe_allow_html=True)

elif page == "Audit":
    page_header(p, "Audit trail")
    events = audit_events(DB, pid)
    if events:
        st.dataframe(
            pd.DataFrame([{
                "When": e["created_at"],
                "Event": e["event_type"],
                "Entity": e["entity_type"] or "—",
                "Entity ID": e["entity_id"] or "—",
                "Detail": e["detail"],
            } for e in events]),
            width="stretch",
            hide_index=True,
        )
    else:
        st.markdown('<div class="go-empty">No audit events.</div>', unsafe_allow_html=True)


elif page == "Project setup" and not is_riana:
    page_header(p, "Project setup")

    c1, c2, c3 = st.columns(3)
    c1.metric("Project code", p["code"])
    c2.metric("Status", p["status"])
    c3.metric("Coordinator", p["coordinator"])

    st.markdown('<div class="go-section">Project information</div>', unsafe_allow_html=True)
    info = {
        "Programme": p["programme"],
        "Start": p["start_date"] or "—",
        "End": p["end_date"] or "—",
        "Public source": p["source_url"] or "—",
        "Notes": p["notes"] or "—",
    }
    st.dataframe(pd.DataFrame([{"Field": k, "Value": v} for k, v in info.items()]), width="stretch", hide_index=True)

    with st.expander("Add another project"):
        with st.form("new_project", clear_on_submit=True):
            a, b = st.columns(2)
            code = a.text_input("Code")
            title = b.text_input("Title")
            coordinator = st.text_input("Coordinator")
            programme = st.text_input("Programme", value="Horizon Europe")
            a, b = st.columns(2)
            start = a.date_input("Start", value=None)
            end = b.date_input("End", value=None)
            source = st.text_input("Public source URL")
            notes = st.text_area("Notes")
            if st.form_submit_button("Create project"):
                try:
                    add_project(
                        DB, code, title, coordinator, programme,
                        start.isoformat() if start else None,
                        end.isoformat() if end else None,
                        "ACTIVE", source or None, notes or None,
                    )
                    st.success("Project created.")
                    st.rerun()
                except sqlite3.IntegrityError as exc:
                    if "projects.code" in str(exc):
                        st.warning("Project already exists — select it from the project menu.")
                    else:
                        st.error("Project could not be created because a unique database value already exists.")
