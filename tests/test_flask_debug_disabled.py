import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ENTRYPOINTS = [
    ROOT / "keeper_explorer.py",
    ROOT / "contributor_registry.py",
    ROOT / "bridge" / "bridge_api.py",
    ROOT / "faucet_service" / "faucet_service.py",
]


def _is_debug_subscript(node):
    if not isinstance(node, ast.Subscript):
        return False

    slice_node = node.slice
    if isinstance(slice_node, ast.Constant):
        return slice_node.value == "debug"
    return False


def _debug_true_locations(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    locations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "debug" and isinstance(keyword.value, ast.Constant):
                    if keyword.value.value is True:
                        locations.append((node.lineno, "app.run debug=True"))

        if isinstance(node, ast.Assign):
            assigns_true = isinstance(node.value, ast.Constant) and node.value.value is True
            if assigns_true and any(_is_debug_subscript(target) for target in node.targets):
                locations.append((node.lineno, "debug config assignment to True"))

    return locations


def test_public_flask_entrypoints_do_not_enable_debug_mode():
    failures = {
        str(path.relative_to(ROOT)): _debug_true_locations(path)
        for path in ENTRYPOINTS
    }
    failures = {path: locations for path, locations in failures.items() if locations}

    assert failures == {}
