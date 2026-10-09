import json
from pathlib import Path

from grantops.riana_demo import riana_demo_available, riana_demo_snapshot


def _identity(kind, id_, name, wp, month):
    return {
        "kind": kind,
        "id": id_,
        "name": name,
        "work_packages": [wp],
        "lead_beneficiary": "1 - TEST",
        "due_month": month,
        "evidence": {"official_list_pdf_page_1_based": 100},
    }


def test_final_riana_artifact_is_versioned_and_read_only(tmp_path: Path):
    deliverables = [_identity("D", f"D1.{i}", f"D {i}", "WP1", i) for i in range(1, 34)]
    milestones = [_identity("M", f"M{i}", f"M {i}", "WP1", i) for i in range(1, 22)]

    fusion = []
    marker = 1
    for identity in deliverables[:30] + milestones:
        fusion.append({
            "marker_index": marker,
            "kind": identity["kind"],
            "task_code": "1.1",
            "task_title": "Synthetic",
            "month": identity["due_month"],
            "selected_identity": identity,
            "stage3_status": "EXACT_PRESERVED",
            "stage4_status": "UNCHANGED_FROM_STAGE3",
        })
        marker += 1

    # One historical/proposal-only marker makes 52.
    fusion.append({
        "marker_index": 52,
        "kind": "D",
        "task_code": "6.1",
        "task_title": "Dissemination",
        "month": 18,
        "selected_identity": None,
        "proposal_era_identity": {
            "qualified_id": "proposal_part_b:D6.3",
            "bare_id": "D6.3",
            "semantic_label": "Plan update",
        },
        "stage4_status": "PROVENANCE_RESOLVED_PROPOSAL_ERA_ONLY",
    })

    payload = {
        "project": "RIANA",
        "status": "PASS_PROVENANCE_RECONCILED",
        "identity_fusion_gate": "CLOSED_WITH_VERSIONED_PROVENANCE",
        "db_mutations": 0,
        "ocr_used": False,
        "fusion": fusion,
        "unordered_group_bindings": [],
        "official_current_ids_not_distinctly_bound_to_visual_markers": deliverables[30:],
        "coverage_final": {
            "current_part_a_ids_not_gantt_bound": ["D1.31", "D1.32", "D1.33"],
        },
        "counts": {},
        "provenance_reconciliation": {
            "identifier_reuse": {
                "bare_id": "D6.3",
                "collision_type": "IDENTIFIER_REUSED_ACROSS_DOCUMENT_ERAS",
                "proposal_era": {
                    "qualified_id": "proposal_part_b:D6.3",
                    "marker_index": 52,
                    "task_code": "6.1",
                    "month": 18,
                    "semantic_label": "Plan update",
                },
                "current_part_a": {
                    "qualified_id": "current_part_a:D6.3",
                    "marker_index": 49,
                    "task_code": "6.4",
                    "month": 31,
                    "name": "Survey",
                },
                "join_rule": "Qualified identity only; bare-ID join forbidden.",
            },
        },
    }

    path = tmp_path / "final.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert riana_demo_available(path) is True
    snap = riana_demo_snapshot(path)
    assert snap["counts"]["deliverables"] == 33
    assert snap["counts"]["milestones"] == 21
    assert snap["counts"]["visual_markers"] == 52
    assert snap["counts"]["proposal_era_only_markers"] == 1
    assert snap["identifier_reuse"]["proposal_qualified_id"] == "proposal_part_b:D6.3"
    assert snap["identifier_reuse"]["current_qualified_id"] == "current_part_a:D6.3"
    assert snap["db_mutations"] == 0