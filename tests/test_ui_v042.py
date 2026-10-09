from pathlib import Path
import ast

src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
ast.parse(src)

for marker in [
    '"Human corrections"',
    "Human corrections & audit",
    "Edit operational record",
    "Reopen review",
    "Change history",
    "Apply audited correction",
    "Reopen for human review",
]:
    assert marker in src, marker

print("PASS_MVP_V0_4_2_UI_CONTRACT")