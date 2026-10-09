from __future__ import annotations

from datetime import date
import html
import json
from pathlib import Path
import sqlite3
from typing import Any


WIDE_PROJECT_CODE = "WIDE-ACROSSEU-101158561"
ACTION_NODE_TYPES = ("DELIVERABLE", "MILESTONE", "REPORTING_PERIOD")
VERIFIED_EVIDENCE_STATUSES = {"HUMAN_VERIFIED", "VERIFIED", "ACCEPTED"}
COMPLETED_STATUSES = {"DONE", "COMPLETED", "ACCEPTED"}
EXPLICIT_LATE_STATUSES = {"LATE", "OVERDUE", "PAST_DUE", "IN_RITARDO", "IN RITARDO"}


def _connect_ro(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalized_status(node: dict[str, Any]) -> str:
    meta = _safe_json(node.get("metadata_json"))
    return str(meta.get("status") or "").strip().upper()


def _deadline_for_node(deadlines: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not deadlines:
        return None
    resolved = [d for d in deadlines if d.get("resolution_status") == "RESOLVED" and d.get("resolved_date")]
    if resolved:
        return sorted(resolved, key=lambda d: str(d["resolved_date"]))[0]
    return deadlines[0]


def _verified_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in requirements if str(r.get("verification_status") or "").upper() in VERIFIED_EVIDENCE_STATUSES]


def _evidence_text(requirements: list[dict[str, Any]], items: list[dict[str, Any]]) -> str:
    verified = _verified_requirements(requirements)
    if verified:
        return "; ".join(r["title"] for r in verified)
    if items:
        return "; ".join(i["title"] for i in items)
    return "Non verificato: nessun requisito di evidenza esplicito e verificato è collegato a questo item."


def _evidence_waiting(requirements: list[dict[str, Any]], items: list[dict[str, Any]]) -> bool:
    verified = _verified_requirements(requirements)
    if not verified:
        return False
    if not items:
        return True
    for item in items:
        status = _normalized_status(item)
        verification = str(item.get("verification_status") or "").upper()
        if status not in COMPLETED_STATUSES and verification not in {"READY", "ACCEPTED"}:
            return True
    return False


def _classify_action(node: dict[str, Any], deadline: dict[str, Any] | None, waiting_evidence: bool, today: date) -> dict[str, Any]:
    status = _normalized_status(node)
    owner_missing = not bool(node.get("owner"))
    completed = status in COMPLETED_STATUSES
    blocked = status == "BLOCKED"
    explicit_late = status in EXPLICIT_LATE_STATUSES

    days_to_due: int | None = None
    if deadline and deadline.get("resolved_date"):
        try:
            due_date = date.fromisoformat(str(deadline["resolved_date"])[:10])
            days_to_due = (due_date - today).days
        except Exception:
            days_to_due = None

    timing_unresolved = bool(deadline and not deadline.get("resolved_date"))
    past_unknown = bool(days_to_due is not None and days_to_due < 0 and not completed and not explicit_late)

    if completed:
        risk, tone, priority = "COMPLETATO", "success", 90
        next_action = "Conservare la prova di completamento insieme alla fonte contrattuale e mantenere la tracciabilità."
    elif explicit_late:
        risk, tone, priority = "IN RITARDO · STATO OPERATIVO ESPLICITO", "danger", 0
        next_action = "Confermare il piano di recupero, il responsabile e l'evidenza necessaria; registrare la decisione operativa."
    elif blocked:
        risk, tone, priority = "BLOCCATO", "danger", 1
        next_action = "Rimuovere il blocco o registrare una decisione umana prima di procedere."
    elif past_unknown:
        risk, tone, priority = "STATO DA CONFERMARE", "warning", 2
        next_action = "Confermare se l'item è stato completato e collegare l'evidenza disponibile. GrantOps non lo marca automaticamente come in ritardo."
    elif timing_unresolved:
        risk, tone, priority = "TEMPISTICA DA CONFERMARE", "warning", 3
        next_action = "Verificare il trigger o la data mancante prima di usare questo item come scadenza operativa."
    elif owner_missing:
        risk, tone, priority = "RESPONSABILE DA CONFERMARE", "warning", 4
        next_action = "Confermare il responsabile operativo senza inferirlo dalla sola struttura contrattuale."
    elif waiting_evidence:
        risk, tone, priority = "EVIDENZA DA PREPARARE", "warning", 5
        next_action = "Preparare o collegare l'evidenza verificata richiesta dalla fonte prima della chiusura dell'item."
    elif days_to_due is not None and 0 <= days_to_due <= 90:
        risk, tone, priority = "PROSSIMI 90 GIORNI", "info", 10 + days_to_due
        next_action = "Confermare readiness, owner e prova di completamento prima della scadenza."
    else:
        risk, tone = "PROGRAMMATO", "neutral"
        priority = 200 + (days_to_due if days_to_due is not None else 9999)
        next_action = "Monitorare la tempistica e mantenere collegati fonte, responsabile ed evidenza."

    return {
        "operational_status": status or None,
        "completed": completed,
        "explicit_late": explicit_late,
        "blocked": blocked,
        "past_date_unknown": past_unknown,
        "timing_unresolved": timing_unresolved,
        "needs_attention": bool(not completed and (explicit_late or blocked or past_unknown or timing_unresolved or owner_missing)),
        "next_90_days": bool(not completed and days_to_due is not None and 0 <= days_to_due <= 90),
        "waiting_evidence": bool(waiting_evidence and not completed),
        "risk": risk,
        "risk_tone": tone,
        "next_action": next_action,
        "priority": priority,
        "days_to_due": days_to_due,
    }


def wide_action_centre_snapshot(db_path: Path | str, project_id: int, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    with _connect_ro(db_path) as con:
        project_row = con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project_row:
            raise ValueError("PROJECT_NOT_FOUND")
        project = dict(project_row)
        if project.get("code") != WIDE_PROJECT_CODE:
            raise ValueError("WIDE_ONLY_GUARD")

        graph_row = con.execute(
            "SELECT * FROM operational_graph_runs WHERE project_id=? ORDER BY id DESC LIMIT 1", (project_id,)
        ).fetchone()
        if not graph_row:
            raise ValueError("WIDE_OPERATIONAL_GRAPH_NOT_READY")
        run_id = graph_row["id"]

        nodes = [dict(r) for r in con.execute(
            "SELECT * FROM operational_graph_nodes WHERE run_id=? ORDER BY node_type,node_key", (run_id,)
        ).fetchall()]
        node_by_key = {n["node_key"]: n for n in nodes}

        deadlines = [dict(r) for r in con.execute(
            "SELECT * FROM operational_graph_deadlines WHERE run_id=? ORDER BY node_key,id", (run_id,)
        ).fetchall()]
        deadlines_by_node: dict[str, list[dict[str, Any]]] = {}
        for d in deadlines:
            deadlines_by_node.setdefault(d["node_key"], []).append(d)

        edges = [dict(r) for r in con.execute(
            "SELECT * FROM operational_graph_edges WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()]
        req_for: dict[str, list[dict[str, Any]]] = {}
        items_for: dict[str, list[dict[str, Any]]] = {}
        for e in edges:
            if e["relation_type"] == "EVIDENCE_FOR":
                source = node_by_key.get(e["from_node_key"])
                if source and source.get("node_type") == "EVIDENCE_REQUIREMENT":
                    req_for.setdefault(e["to_node_key"], []).append(source)
            elif e["relation_type"] == "SUPPORTED_BY":
                target = node_by_key.get(e["to_node_key"])
                if target and target.get("node_type") == "EVIDENCE_ITEM":
                    items_for.setdefault(e["from_node_key"], []).append(target)

        prov_row = con.execute(
            "SELECT * FROM provenance_review_runs WHERE project_id=? AND graph_run_id=? ORDER BY id DESC LIMIT 1",
            (project_id, run_id),
        ).fetchone()
        prov_by_node: dict[str, dict[str, Any]] = {}
        if prov_row:
            rows = con.execute(
                "SELECT * FROM provenance_review_items WHERE run_id=? AND item_type='GRAPH_NODE' ORDER BY id",
                (prov_row["id"],),
            ).fetchall()
            for r in rows:
                item = dict(r)
                prov_by_node.setdefault(item["graph_node_key"], item)

        actions: list[dict[str, Any]] = []
        for node in nodes:
            if node["node_type"] not in ACTION_NODE_TYPES:
                continue
            key = node["node_key"]
            deadline = _deadline_for_node(deadlines_by_node.get(key, []))
            reqs = req_for.get(key, [])
            items = items_for.get(key, [])
            classification = _classify_action(node, deadline, _evidence_waiting(reqs, items), today)
            provenance = prov_by_node.get(key)

            if deadline and deadline.get("resolved_date"):
                when = str(deadline["resolved_date"])
                when_detail = deadline.get("relative_rule") or deadline.get("deadline_kind") or "Non verificato"
            elif deadline:
                when = deadline.get("relative_rule") or "Non determinato"
                when_detail = deadline.get("resolution_status") or "Non verificato"
            else:
                when, when_detail = "Non determinato", "Nessuna scadenza o trigger verificato per questo item"

            if provenance:
                page = provenance.get("page_number")
                source_label = f'{provenance.get("document_filename") or "Grant Agreement"} · pagina {page if page is not None else "Non determinata"}'
                source_quote = provenance.get("source_quote") or node.get("source_quote") or "Non verificato"
                source_status = provenance.get("provenance_status") or "Non verificato"
            else:
                page = node.get("source_page")
                source_label = f'Grant Agreement · pagina {page if page is not None else "Non determinata"}'
                source_quote = node.get("source_quote") or "Non verificato"
                source_status = "Non verificato"

            actions.append({
                "key": key,
                "type": node["node_type"],
                "what": node["title"],
                "when": when,
                "when_detail": when_detail,
                "owner": node.get("owner") or "Non determinato",
                "contract_source": source_label,
                "source_quote": source_quote,
                "source_status": source_status,
                "evidence": _evidence_text(reqs, items),
                "verification_status": node.get("verification_status") or "Non verificato",
                **classification,
            })

    actions.sort(key=lambda x: (x["priority"], x["when"], x["what"]))
    source_complete = sum(str(a["source_status"]).upper() == "COMPLETE" for a in actions)
    return {
        "project": project,
        "source_mode": "WIDE_OPERATIONAL_GRAPH_READ_ONLY",
        "graph_run_id": run_id,
        "actions": actions,
        "counts": {
            "total": len(actions),
            "needs_attention": sum(a["needs_attention"] for a in actions),
            "next_90_days": sum(a["next_90_days"] for a in actions),
            "waiting_evidence": sum(a["waiting_evidence"] for a in actions),
            "completed": sum(a["completed"] for a in actions),
            "source_complete": source_complete,
            "source_total": len(actions),
        },
        "recommendation_notice": "Le prossime azioni sono raccomandazioni operative di GrantOps, non testo contrattuale.",
        "db_mutations": 0,
    }


def _badge(text: str, tone: str = "neutral") -> str:
    suffix = "" if tone == "neutral" else f" go-badge-{tone}"
    return f'<span class="go-badge{suffix}">{html.escape(str(text))}</span>'


def _queue_frame(actions: list[dict[str, Any]]) -> Any:
    import pandas as pd
    return pd.DataFrame([{
        "Item": a["what"], "Due": a["when"], "Owner": a["owner"], "Risk / status": a["risk"]
    } for a in actions])


def render_wide_action_centre(snapshot: dict[str, Any]) -> None:
    import streamlit as st
    actions = snapshot["actions"]
    counts = snapshot["counts"]

    st.markdown('<div class="go-section">WIDE · Post-award Action Centre</div>', unsafe_allow_html=True)
    st.caption("v0.6 candidate · operational view derived from the current WIDE graph and provenance · read only")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Needs attention", counts["needs_attention"])
    c2.metric("Next 90 days", counts["next_90_days"])
    c3.metric("Waiting evidence", counts["waiting_evidence"])
    c4.metric("Source coverage", f'{counts["source_complete"]}/{counts["source_total"]}')

    attention = [a for a in actions if a["needs_attention"]]
    upcoming = [a for a in actions if a["next_90_days"] and not a["completed"]]
    waiting = [a for a in actions if a["waiting_evidence"] and not a["completed"]]
    completed = [a for a in actions if a["completed"]]

    primary = attention or waiting or upcoming or actions
    if primary:
        item = primary[0]
        st.markdown('<div class="go-section">Primary action</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="go-panel">'
            f'<div class="go-row-title">{html.escape(item["what"])}</div>'
            f'<div class="go-row-meta">Due: {html.escape(str(item["when"]))} · Owner: {html.escape(item["owner"])}</div>'
            f'<div style="margin-top:.45rem">{_badge(item["risk"], item["risk_tone"])}</div>'
            f'<div class="go-row-meta" style="margin-top:.55rem"><strong>GrantOps next action:</strong> {html.escape(item["next_action"])}</div>'
            '</div>', unsafe_allow_html=True,
        )

    st.markdown('<div class="go-section">Operational queue</div>', unsafe_allow_html=True)
    ta, tu, tw, tc = st.tabs(["Needs attention", "Upcoming", "Waiting evidence", "Completed"])
    with ta:
        st.dataframe(_queue_frame(attention), width="stretch", hide_index=True) if attention else st.info("No WIDE items currently meet the bounded attention criteria.")
    with tu:
        st.dataframe(_queue_frame(upcoming), width="stretch", hide_index=True) if upcoming else st.info("No WIDE items with a verified resolved date fall in the next 90 days.")
    with tw:
        st.dataframe(_queue_frame(waiting), width="stretch", hide_index=True) if waiting else st.info("No verified linked evidence requirement is currently waiting for evidence in this bounded view.")
    with tc:
        st.dataframe(_queue_frame(completed), width="stretch", hide_index=True) if completed else st.info("No explicit completed operational status is available in the current graph.")

    st.markdown('<div class="go-section">Open item</div>', unsafe_allow_html=True)
    options: list[str | None] = [None] + [a["key"] for a in actions]
    by_key = {a["key"]: a for a in actions}
    selected = st.selectbox(
        "Select an item to answer the seven operational questions", options,
        format_func=lambda key: "Select an item…" if key is None else by_key[key]["what"],
        key="wide_action_centre_item_v06",
    )
    if selected is None:
        st.caption("The seven questions appear only after an item is selected.")
        return

    item = by_key[selected]
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**COSA DEVO FARE?**")
        st.write(item["what"])
        st.markdown("**ENTRO QUANDO?**")
        st.write(item["when"])
        st.caption(item["when_detail"])
        st.markdown("**CHI È RESPONSABILE?**")
        st.write(item["owner"])
        st.markdown("**QUAL È LA FONTE CONTRATTUALE?**")
        st.write(item["contract_source"])
        st.caption(f'Stato provenance: {item["source_status"]}')
    with right:
        st.markdown("**CHE EVIDENZA DEVO CONSERVARE?**")
        st.write(item["evidence"])
        st.markdown("**COSA È A RISCHIO / IN RITARDO?**")
        st.markdown(_badge(item["risk"], item["risk_tone"]), unsafe_allow_html=True)
        st.markdown("**QUAL È LA PROSSIMA AZIONE?**")
        st.write(item["next_action"])
        st.caption(snapshot["recommendation_notice"])

    with st.expander("Contract source and exact evidence trail"):
        st.write(f'**Source:** {item["contract_source"]}')
        st.write(f'**Provenance status:** {item["source_status"]}')
        st.markdown('<div class="go-source">' + html.escape(item["source_quote"]) + '</div>', unsafe_allow_html=True)