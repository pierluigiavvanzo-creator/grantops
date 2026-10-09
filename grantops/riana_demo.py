from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


EXPECTED_STATUS = "PASS_PROVENANCE_RECONCILED"
EXPECTED_GATE = "CLOSED_WITH_VERSIONED_PROVENANCE"


def riana_demo_available(final_canonical_path: Path | str) -> bool:
    path = Path(final_canonical_path)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (
        data.get("project") == "RIANA"
        and data.get("status") == EXPECTED_STATUS
        and data.get("identity_fusion_gate") == EXPECTED_GATE
    )


def _id_sort(value: str) -> tuple:
    nums = tuple(int(x) for x in re.findall(r"\d+", value or ""))
    return ((value or "")[:1], nums, value or "")


def _source_page(identity: dict[str, Any]) -> int | None:
    evidence = identity.get("evidence") or {}
    page = evidence.get("official_list_pdf_page_1_based")
    return int(page) if page is not None else None


def _identity_row(identity: dict[str, Any], binding: str) -> dict[str, Any]:
    return {
        "kind": identity.get("kind"),
        "id": identity.get("id"),
        "name": identity.get("name"),
        "work_packages": ", ".join(identity.get("work_packages") or []),
        "lead_beneficiary": identity.get("lead_beneficiary"),
        "due_month": identity.get("due_month"),
        "source_page": _source_page(identity),
        "binding": binding,
    }


def riana_demo_snapshot(final_canonical_path: Path | str) -> dict[str, Any]:
    path = Path(final_canonical_path)
    if not path.is_file():
        raise FileNotFoundError(f"RIANA_FINAL_CANONICAL_NOT_FOUND:{path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("project") != "RIANA":
        raise ValueError("RIANA_PROJECT_MISMATCH")
    if data.get("status") != EXPECTED_STATUS:
        raise ValueError(f"RIANA_STATUS_NOT_FINAL:{data.get('status')}")
    if data.get("identity_fusion_gate") != EXPECTED_GATE:
        raise ValueError(f"RIANA_IDENTITY_GATE_NOT_CLOSED:{data.get('identity_fusion_gate')}")

    current: dict[tuple[str, str], dict[str, Any]] = {}
    current_binding: dict[tuple[str, str], str] = {}

    for marker in data.get("fusion") or []:
        selected = marker.get("selected_identity")
        if selected and selected.get("id"):
            key = (str(selected.get("kind")), str(selected.get("id")))
            current[key] = selected
            current_binding.setdefault(key, "Gantt marker")

    for group in data.get("unordered_group_bindings") or []:
        for identity in group.get("identities") or []:
            if identity.get("id"):
                key = (str(identity.get("kind")), str(identity.get("id")))
                current[key] = identity
                current_binding.setdefault(key, "Gantt marker (unordered group)")

    for identity in data.get("official_current_ids_not_distinctly_bound_to_visual_markers") or []:
        if identity.get("id"):
            key = (str(identity.get("kind")), str(identity.get("id")))
            current[key] = identity
            current_binding[key] = "Current Part A only"

    identities = [
        _identity_row(identity, current_binding[key])
        for key, identity in current.items()
    ]
    identities.sort(key=lambda x: _id_sort(x["id"]))

    deliverables = [x for x in identities if x["kind"] == "D"]
    milestones = [x for x in identities if x["kind"] == "M"]

    # Build one display row for every accepted visual marker.
    group_map: dict[int, dict[str, Any]] = {}
    for group in data.get("unordered_group_bindings") or []:
        ids = list(group.get("current_ids") or [])
        for marker_index in group.get("marker_indices") or []:
            group_map[int(marker_index)] = {
                "current_id": " / ".join(ids),
                "status": "CURRENT · unordered pair",
            }

    marker_rows = []
    historical_rows = []
    for marker in sorted(data.get("fusion") or [], key=lambda x: int(x.get("marker_index") or 0)):
        idx = int(marker.get("marker_index") or 0)
        selected = marker.get("selected_identity")
        proposal = marker.get("proposal_era_identity")

        current_id = selected.get("id") if selected else None
        identity_status = "CURRENT" if current_id else None

        if idx in group_map:
            current_id = group_map[idx]["current_id"]
            identity_status = group_map[idx]["status"]

        proposal_id = None
        proposal_label = None
        if proposal:
            proposal_id = proposal.get("qualified_id") or proposal.get("id")
            proposal_label = proposal.get("semantic_label")
            identity_status = "PROPOSAL-ERA ONLY"
            historical_rows.append({
                "marker_index": idx,
                "qualified_id": proposal_id,
                "bare_id": proposal.get("bare_id") or proposal.get("id"),
                "semantic_label": proposal_label,
                "task_code": marker.get("task_code"),
                "month": marker.get("month"),
                "status": "Historical/provenance identity",
            })

        marker_rows.append({
            "marker_index": idx,
            "kind": marker.get("kind"),
            "task_code": marker.get("task_code"),
            "task_title": marker.get("task_title"),
            "month": marker.get("month"),
            "identity": current_id or proposal_id or "—",
            "identity_status": identity_status or marker.get("stage4_status") or marker.get("stage3_status"),
        })

    ledger = data.get("provenance_reconciliation") or {}
    reuse = ledger.get("identifier_reuse") or {}
    proposal_reuse = reuse.get("proposal_era") or {}
    current_reuse = reuse.get("current_part_a") or {}

    wps = sorted({
        wp
        for identity in current.values()
        for wp in (identity.get("work_packages") or [])
    })

    coverage = data.get("coverage_final") or {}
    counts = data.get("counts") or {}

    # Final hard gates: the dashboard must not present a partial/older artifact as final.
    expected = {
        "deliverables": 33,
        "milestones": 21,
        "visual_markers": 52,
    }
    observed = {
        "deliverables": len(deliverables),
        "milestones": len(milestones),
        "visual_markers": len(marker_rows),
    }
    if observed != expected:
        raise ValueError(f"RIANA_FINAL_COUNT_GATE_FAILED:{observed}")

    if len(historical_rows) != 1:
        raise ValueError(f"RIANA_HISTORICAL_MARKER_GATE_FAILED:{len(historical_rows)}")

    return {
        "project": {
            "code": "RIANA",
            "title": "RIANA — validated Grant Agreement identity workspace",
            "coordinator": "Read-only validated source workspace",
            "programme": "Horizon Europe",
            "status": "VALIDATED",
        },
        "status": data["status"],
        "identity_gate": data["identity_fusion_gate"],
        "source_path": str(path),
        "work_packages": wps,
        "counts": {
            "work_packages": len(wps),
            "deliverables": len(deliverables),
            "milestones": len(milestones),
            "visual_markers": len(marker_rows),
            "current_marker_bindings": 51,
            "proposal_era_only_markers": len(historical_rows),
            "current_part_a_not_gantt_bound": len(
                coverage.get("current_part_a_ids_not_gantt_bound") or []
            ),
        },
        "coverage": coverage,
        "current_identities": identities,
        "deliverables": deliverables,
        "milestones": milestones,
        "marker_rows": marker_rows,
        "historical_rows": historical_rows,
        "current_only_ids": coverage.get("current_part_a_ids_not_gantt_bound") or [],
        "identifier_reuse": {
            "bare_id": reuse.get("bare_id"),
            "collision_type": reuse.get("collision_type"),
            "proposal_qualified_id": proposal_reuse.get("qualified_id"),
            "proposal_marker_index": proposal_reuse.get("marker_index"),
            "proposal_task_code": proposal_reuse.get("task_code"),
            "proposal_month": proposal_reuse.get("month"),
            "proposal_label": proposal_reuse.get("semantic_label"),
            "current_qualified_id": current_reuse.get("qualified_id"),
            "current_marker_index": current_reuse.get("marker_index"),
            "current_task_code": current_reuse.get("task_code"),
            "current_month": current_reuse.get("month"),
            "current_name": current_reuse.get("name"),
            "join_rule": reuse.get("join_rule"),
        },
        "db_mutations": int(data.get("db_mutations") or 0),
        "ocr_used": bool(data.get("ocr_used")),
    }