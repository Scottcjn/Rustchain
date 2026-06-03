# SPDX-License-Identifier: MIT
"""
Tests for three self-contained OTC bridge fixes:
  1. list_trades fail-open — an unsupported pair must 400, not return the full
     unfiltered feed.
  2. init_db runs at import — so WSGI/gunicorn deploys (otc_bridge:app) create
     the schema, not only `python otc_bridge.py`.
  3. rtc_release_escrow dead code removed.
"""
import importlib.util
import os
import sqlite3
import sys
import types
from pathlib import Path


def _load(tmp_path, call_init_db):
    if "flask_cors" not in sys.modules:
        flask_cors = types.ModuleType("flask_cors")
        flask_cors.CORS = lambda app, *args, **kwargs: app
        sys.modules["flask_cors"] = flask_cors

    db_path = tmp_path / "otc_bridge.db"
    os.environ["OTC_DB_PATH"] = str(db_path)
    module_path = Path(__file__).resolve().parents[1] / "otc-bridge" / "otc_bridge.py"
    name = f"otc_bridge_cleanfix_{abs(hash(db_path))}"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    module.app.testing = True
    if call_init_db:
        module.init_db()
    return module


def test_list_trades_rejects_unsupported_pair(tmp_path):
    module = _load(tmp_path, call_init_db=True)
    client = module.app.test_client()
    resp = client.get("/api/trades?pair=BOGUS")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "unsupported pair"


def test_list_trades_supported_pair_ok(tmp_path):
    module = _load(tmp_path, call_init_db=True)
    client = module.app.test_client()
    resp = client.get("/api/trades?pair=RTC/USDC")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_list_trades_no_pair_returns_feed(tmp_path):
    module = _load(tmp_path, call_init_db=True)
    client = module.app.test_client()
    resp = client.get("/api/trades")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_init_db_runs_at_import_for_wsgi(tmp_path):
    """Importing the module (as gunicorn does) must create the schema without
    anyone calling init_db() explicitly."""
    module = _load(tmp_path, call_init_db=False)
    conn = sqlite3.connect(module.DB_PATH)
    try:
        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()
    assert {"orders", "trades", "rate_limits"}.issubset(tables)


def test_dead_release_escrow_removed(tmp_path):
    module = _load(tmp_path, call_init_db=True)
    assert not hasattr(module, "rtc_release_escrow")
