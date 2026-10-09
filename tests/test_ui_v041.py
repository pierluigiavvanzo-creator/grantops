from pathlib import Path
import ast

src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
ast.parse(src)

for marker in [
    '"Provenance review"',
    '"Provenance review"',
    "Build provenance review",
    "Provenance gate",
    "Traceability matrix",
    "Inspect provenance chain",
    "Exact source quote",
]:
    assert marker in src, marker

print("PASS_MVP_V0_4_1_UI_CONTRACT")