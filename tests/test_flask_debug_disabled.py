# SPDX-License-Identifier: MIT
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_FLASK_ENTRYPOINTS = [
    ROOT / "bcos_directory.py",
    ROOT / "bridge" / "bridge_api.py",
    ROOT / "contributor_registry.py",
    ROOT / "explorer" / "app.py",
    ROOT / "faucet_service" / "faucet_service.py",
    ROOT / "keeper_explorer.py",
    ROOT / "profile_badge_generator.py",
    ROOT / "security_test_payment_widget.py",
]

LOCAL_POC_DEBUG_HARNESSES = {
    "xss_poc_templates.py",
}

PARSE_INCOMPATIBLE_PYTHON = {
    # Existing static site builder uses syntax that is not parseable by this
    # merge-gate probe. It is not a Flask entrypoint, so keep it documented here
    # instead of letting the broad scan fail before checking the public surface.
    "build_static.py",
}


def repo_path(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


def is_debug_subscript(node):
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == "debug"
    )


def debug_true_locations(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        relative = repo_path(path)
        if relative in PARSE_INCOMPATIBLE_PYTHON:
            return []
        raise AssertionError(f"{relative} could not be parsed by the Flask debug scan: {exc}") from exc
    locations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if (
                    keyword.arg == "debug"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ):
                    locations.append((node.lineno, "app.run debug=True"))

        if isinstance(node, ast.Assign):
            assigns_true = isinstance(node.value, ast.Constant) and node.value.value is True
            if assigns_true and any(is_debug_subscript(target) for target in node.targets):
                locations.append((node.lineno, "debug config assignment to True"))

    return locations


def python_sources():
    skipped_dirs = {".git", ".mypy_cache", ".pytest_cache", "__pycache__", "venv", ".venv"}
    for path in ROOT.rglob("*.py"):
        if skipped_dirs.intersection(path.relative_to(ROOT).parts):
            continue
        yield path


def test_public_flask_entrypoints_do_not_enable_debug_mode():
    failures = {
        str(path.relative_to(ROOT)): debug_true_locations(path)
        for path in PUBLIC_FLASK_ENTRYPOINTS
    }
    failures = {path: locations for path, locations in failures.items() if locations}

    assert failures == {}


def test_no_undocumented_flask_debug_true_entrypoints():
    failures = {}
    for path in python_sources():
        relative = repo_path(path)
        if relative in LOCAL_POC_DEBUG_HARNESSES:
            continue
        locations = debug_true_locations(path)
        if locations:
            failures[relative] = locations

    assert failures == {}
