import os
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _make_client(tmp_path):
    import machine_passport_viewer
    from machine_passport_viewer import passport_viewer_bp

    machine_passport_viewer.PASSPORT_DB_PATH = str(tmp_path / "passports.db")
    machine_passport_viewer._ledger = None

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(passport_viewer_bp)
    return app.test_client()


def test_passport_viewer_rejects_non_integer_limit(tmp_path):
    client = _make_client(tmp_path)

    resp = client.get("/passport/?limit=abc")

    assert resp.status_code == 400
    assert resp.get_data(as_text=True) == "limit must be an integer"


def test_passport_viewer_rejects_negative_limit(tmp_path):
    client = _make_client(tmp_path)

    resp = client.get("/passport/?limit=-1")

    assert resp.status_code == 400
    assert resp.get_data(as_text=True) == "limit must be non-negative"


def test_passport_viewer_clamps_large_limit(tmp_path):
    client = _make_client(tmp_path)

    resp = client.get("/passport/?limit=999")

    assert resp.status_code == 200
    assert "0 passport(s) found" in resp.get_data(as_text=True)

