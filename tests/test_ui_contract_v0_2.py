from pathlib import Path
import ast

src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
ast.parse(src)
required = [
    "Document custody",
    "Bounded local extraction",
    "Human review queue",
    "Extract text & detect candidates",
    "Approve & add",
    "Authoritative source",
    "Review progress",
]
missing = [item for item in required if item not in src]
if missing:
    raise SystemExit("Missing v0.2 UI markers: " + ", ".join(missing))
if "DeltaGenerator(" in src:
    raise SystemExit("DeltaGenerator regression detected")
print("PASS_MVP_V0_2_UI_CONTRACT")