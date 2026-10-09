from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--result")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    sys.path.insert(0, str(root))
    db = root / "data" / "grantops.db"
    app = root / "app.py"

    from grantops.buyer_demo import buyer_demo_snapshot
    from grantops.wide_action_centre import WIDE_PROJECT_CODE, wide_action_centre_snapshot

    before_db = sha256(db)
    app_text = app.read_text(encoding="utf-8")
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT id FROM projects WHERE code=?", (WIDE_PROJECT_CODE,)).fetchone()
        if not row:
            raise SystemExit("WIDE_PROJECT_NOT_FOUND")
        wide_id = row["id"]

    demo = buyer_demo_snapshot(db, wide_id)
    action = wide_action_centre_snapshot(db, wide_id)
    after_db = sha256(db)

    false_overdue = [a for a in action["actions"] if a["past_date_unknown"] and ("IN RITARDO" in a["risk"].upper() or "OVERDUE" in a["risk"].upper())]
    missing_source = [a for a in action["actions"] if str(a["source_status"]).upper() != "COMPLETE"]
    module_text = (root / "grantops" / "wide_action_centre.py").read_text(encoding="utf-8")
    labels = [
        "COSA DEVO FARE?", "ENTRO QUANDO?", "CHI È RESPONSABILE?",
        "QUAL È LA FONTE CONTRATTUALE?", "CHE EVIDENZA DEVO CONSERVARE?",
        "COSA È A RISCHIO / IN RITARDO?", "QUAL È LA PROSSIMA AZIONE?",
    ]

    gates = {
        "wide_exact_project_found": True,
        "buyer_demo_ready": bool(demo["demo_ready"]),
        "structural_nodes_22": demo["structure"]["total"] == 22,
        "resolved_structural_deadlines_32": demo["deadlines"]["resolved_structural"] == 32,
        "provenance_core_54": demo["provenance"]["core_complete"] == 54 and demo["provenance"]["core_total"] == 54,
        "action_items_non_empty": len(action["actions"]) > 0,
        "source_coverage_preserved": len(missing_source) == 0,
        "zero_false_structural_overdue": len(false_overdue) == 0,
        "db_mutations_zero": before_db == after_db,
        "riana_guard_unchanged": 'if page == "Buyer demo" and is_riana:' in app_text,
        "demo_guard_wide_only": 'if p["code"] == WIDE_PROJECT_CODE:' in app_text,
        "seven_questions_present": all(label in module_text for label in labels),
        "db_read_only_declared": action.get("db_mutations") == 0,
    }
    gates["pass"] = all(gates.values())

    result = {
        "schema_version": "grantops.v0_6_wide_action_centre_validation.v1",
        "wide_project_code": WIDE_PROJECT_CODE,
        "buyer_demo": {
            "demo_ready": demo["demo_ready"],
            "structural_nodes": demo["structure"]["total"],
            "resolved_structural_deadlines": demo["deadlines"]["resolved_structural"],
            "provenance_core_complete": demo["provenance"]["core_complete"],
            "provenance_core_total": demo["provenance"]["core_total"],
        },
        "action_centre": {
            "action_items": len(action["actions"]),
            "counts": action["counts"],
            "false_overdue_count": len(false_overdue),
            "missing_source_count": len(missing_source),
        },
        "db_sha256_before": before_db,
        "db_sha256_after": after_db,
        "gates": gates,
    }
    result_path = Path(args.result).resolve() if args.result else root / "audit_exports" / "GRANTOPS_V0_6_WIDE_ACTION_CENTRE_VALIDATION.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    for key, value in gates.items():
        print(f"{key.upper()}={'PASS' if value else 'FAIL'}")
    print(f"WIDE_ACTION_ITEMS={len(action['actions'])}")
    print(f"NEEDS_ATTENTION={action['counts']['needs_attention']}")
    print(f"NEXT_90_DAYS={action['counts']['next_90_days']}")
    print(f"WAITING_EVIDENCE={action['counts']['waiting_evidence']}")
    print(f"COMPLETED={action['counts']['completed']}")
    print(f"SOURCE_COVERAGE={action['counts']['source_complete']}/{action['counts']['source_total']}")
    print(f"RESULT={result_path}")
    return 0 if gates["pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())