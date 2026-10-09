from pathlib import Path
import ast

src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
ast.parse(src)

for marker in [
    "MVP v0.5 · buyer-ready demo",
    '"Buyer demo"',
    "From Grant Agreement to operational control",
    "What GrantOps built from this grant",
    "60-second walkthrough",
    "Operational schedule",
    "Show the source",
    "Human-control proof",
    "What this demo does not claim",
]:
    assert marker in src, marker

print("PASS_MVP_V0_5_UI_CONTRACT")