import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_apply_transaction_has_single_own_assignment():
    tree = ast.parse((ROOT / "node" / "utxo_db.py").read_text())
    apply_transaction = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "apply_transaction"
    )

    own_assignments = [
        node for node in ast.walk(apply_transaction)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "own"
    ]

    assert len(own_assignments) == 1
