# SPDX-License-Identifier: MIT
"""Regression: the canonical /api/v1/* blueprint must be mounted when the main
node module is imported — which is exactly what wsgi.py does under gunicorn.

Before the fix, register_api_v1(...) was called ~3800 lines before
current_slot()/slot_to_epoch() were defined. The call raised NameError, the
surrounding `except Exception` printed one line and moved on, and the node
came up with no /api/v1 routes at all: https://rustchain.org/api/v1/health
answered 404 in production. Nothing tested "is the blueprint actually there",
so it stayed that way.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = PROJECT_ROOT / "node"
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"


def _load_integrated_node(db_path: Path, tag: str):
    """Import the main module the way wsgi.py does (spec_from_file_location)."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    if str(NODE_DIR) not in sys.path:
        sys.path.insert(0, str(NODE_DIR))

    from tests import mock_crypto

    sys.modules["rustchain_crypto"] = mock_crypto
    os.environ["DB_PATH"] = str(db_path)
    os.environ["RUSTCHAIN_DB_PATH"] = str(db_path)
    os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)

    spec = importlib.util.spec_from_file_location(f"integrated_node_api_v1_{tag}", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


@pytest.fixture(scope="module")
def node(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("api_v1") / "node.db"
    return _load_integrated_node(db_path, "reg")


def test_api_v1_blueprint_is_registered_after_import(node):
    # This is the whole bug: the blueprint silently never made it onto the app.
    assert "api_v1" in node.app.blueprints, (
        "api_v1 blueprint missing from app.blueprints — register_api_v1() "
        "failed at import time (was: NameError on current_slot/slot_to_epoch)"
    )
    rules = {r.rule for r in node.app.url_map.iter_rules()}
    assert "/api/v1/health" in rules
    assert "/api/v1/status" in rules


def test_api_v1_index_answers_not_404(node):
    client = node.app.test_client()
    r = client.get("/api/v1/")
    assert r.status_code == 200, r.data
    body = r.get_json()
    assert body["ok"] is True
    assert body["api"] == "rustchain v1"
    assert "/api/v1/health" in body["endpoints"]


def test_api_v1_health_is_served_by_blueprint(node):
    # DB may not have schema_version in this bare test DB, so 503 is a valid
    # blueprint answer. 404 is not: 404 means nginx/Flask never saw a route.
    r = node.app.test_client().get("/api/v1/health")
    assert r.status_code in (200, 503), r.data
    assert r.is_json
    assert "version" in r.get_json()


def test_api_v1_callbacks_are_the_real_helpers(node):
    # The register call captures current_slot/slot_to_epoch by value, so they
    # must be the module's real, already-defined functions at that point.
    epoch_view = node.app.test_client().get("/api/v1/epoch")
    assert epoch_view.status_code in (200, 503), epoch_view.data
    assert epoch_view.is_json
