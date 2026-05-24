"""
Regression tests for Hall of Rust non-object JSON body handling.
Covers: POST /hall/induct and POST /hall/eulogy/<fingerprint>
Issue: #6134 — endpoints accepted non-object JSON bodies
"""
import json
import sqlite3
import tempfile
import os
import sys

import pytest

# Add parent dir to path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask

def create_test_app(db_path):
    """Create a Flask test app with the hall_of_rust blueprint."""
    from hall_of_rust import hall_bp, init_hall_tables
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path
    app.register_blueprint(hall_bp)
    init_hall_tables(db_path)
    return app


@pytest.fixture
def app_and_db():
    """Provide a test Flask app with a temporary database."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test_hall.db")
    app = create_test_app(db_path)
    app.config["TESTING"] = True
    yield app, db_path
    # Cleanup
    os.unlink(db_path)
    os.rmdir(tmp)


@pytest.fixture
def client(app_and_db):
    app, _ = app_and_db
    return app.test_client()


# ---- /hall/induct tests ----

class TestInductNonObjectJSON:
    """POST /hall/induct should reject non-object JSON bodies with 400."""

    def test_induct_array_body_returns_400(self, client):
        """Array JSON body should be rejected."""
        resp = client.post("/hall/induct", json=["not", "an", "object"])
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "JSON object required" in data["error"]

    def test_induct_string_body_returns_400(self, client):
        """String JSON body should be rejected."""
        resp = client.post("/hall/induct", json="just a string")
        assert resp.status_code == 400

    def test_induct_number_body_returns_400(self, client):
        """Numeric JSON body should be rejected."""
        resp = client.post("/hall/induct", json=42)
        assert resp.status_code == 400

    def test_induct_null_body_returns_400_or_empty(self, client):
        """Null JSON body should be handled gracefully."""
        # request.get_json(silent=True) returns None for null
        resp = client.post("/hall/induct",
                          data="null",
                          content_type="application/json")
        # None is not a dict, so should get 400
        assert resp.status_code == 400

    def test_induct_valid_object_works(self, client):
        """Valid JSON object should be accepted (even if it creates an entry)."""
        resp = client.post("/hall/induct", json={
            "device_model": "PowerMac3,4",
            "device_arch": "G4",
            "cpu_serial": "test-serial-001",
            "miner_id": "test-miner"
        })
        assert resp.status_code == 200

    def test_induct_empty_object_works(self, client):
        """Empty JSON object should be accepted (uses defaults)."""
        resp = client.post("/hall/induct", json={})
        assert resp.status_code == 200


# ---- /hall/eulogy tests ----

class TestEulogyNonObjectJSON:
    """POST /hall/eulogy/<fingerprint> should reject non-object JSON bodies with 400."""

    def test_eulogy_array_body_returns_400(self, client):
        """Array JSON body should be rejected."""
        # First induct a machine so the fingerprint exists
        client.post("/hall/induct", json={
            "device_model": "PowerBook5,1",
            "device_arch": "G4",
            "cpu_serial": "eulogy-test-serial",
            "miner_id": "eulogy-tester"
        })
        # Need to figure out what fingerprint hash was generated
        # For this test we just need the endpoint to reject bad JSON
        resp = client.post("/hall/eulogy/anyfingerprint", json=["nickname"])
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_eulogy_string_body_returns_400(self, client):
        """String JSON body should be rejected."""
        resp = client.post("/hall/eulogy/somefp", json="just-a-string")
        assert resp.status_code == 400

    def test_eulogy_number_body_returns_400(self, client):
        """Numeric JSON body should be rejected."""
        resp = client.post("/hall/eulogy/somefp", json=123)
        assert resp.status_code == 400

    def test_eulogy_valid_object_works(self, client):
        """Valid JSON object should be accepted."""
        # Even if fingerprint doesn't exist, the endpoint should not crash
        resp = client.post("/hall/eulogy/nonexistent", json={
            "nickname": "Old Reliable"
        })
        # Should return 200 (no rows updated is OK, just not crash)
        assert resp.status_code == 200

    def test_eulogy_empty_object_works(self, client):
        """Empty JSON object should be accepted (no-op update)."""
        resp = client.post("/hall/eulogy/somefp", json={})
        assert resp.status_code == 200
