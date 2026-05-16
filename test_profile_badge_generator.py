# SPDX-License-Identifier: MIT
"""Unit tests for profile_badge_generator.py — covers text_field, escape_markdown_alt,
and the /api/badge/create, /api/badge/stats, /api/badge/list endpoints."""

import json
import os
import sqlite3
import tempfile
import pytest

# We need to import the module; patch DB_PATH before import so tests use a temp DB
_test_db = tempfile.mktemp(suffix=".db")
os.environ["PROFILE_BADGE_TEST_DB"] = _test_db

import profile_badge_generator as pbg
pbg.DB_PATH = _test_db


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-init the DB before each test for isolation."""
    pbg.init_badge_db()
    yield
    # cleanup
    try:
        os.unlink(_test_db)
    except FileNotFoundError:
        pass


# ─── text_field ────────────────────────────────────────────────────

def test_text_field_returns_value():
    data = {"username": "alice"}
    assert pbg.text_field(data, "username") == "alice"


def test_text_field_returns_default_when_missing():
    data = {}
    assert pbg.text_field(data, "wallet", "0xdefault") == "0xdefault"


def test_text_field_returns_empty_when_none():
    data = {"wallet": None}
    assert pbg.text_field(data, "wallet") == ""


def test_text_field_strips_whitespace():
    data = {"username": "  bob  "}
    assert pbg.text_field(data, "username") == "bob"


# ─── escape_markdown_alt ───────────────────────────────────────────

def test_escape_markdown_alt_backslash():
    assert pbg.escape_markdown_alt("a\\b") == "a\\\\b"


def test_escape_markdown_alt_brackets():
    assert pbg.escape_markdown_alt("test[1]") == "test\\[1\\]"


def test_escape_markdown_alt_newlines():
    assert pbg.escape_markdown_alt("line1\nline2\rline3") == "line1 line2 line3"


def test_escape_markdown_alt_no_special_chars():
    assert pbg.escape_markdown_alt("RustChain Contributor") == "RustChain Contributor"


# ─── /api/badge/create ─────────────────────────────────────────────

def test_create_badge_success(client):
    resp = client.post("/api/badge/create", json={
        "username": "testuser",
        "wallet": "RTCabc123",
        "badge_type": "contributor",
        "custom_message": "Active Contributor"
    })
    data = resp.get_json()
    assert data["success"] is True
    assert "markdown" in data
    assert "html" in data
    assert "shield_url" in data
    assert "RustChain" in data["markdown"]
    assert "testuser" not in data["shield_url"]  # username not in badge URL


def test_create_badge_missing_username(client):
    resp = client.post("/api/badge/create", json={
        "wallet": "RTCabc123",
        "badge_type": "contributor"
    })
    data = resp.get_json()
    assert data["success"] is False
    assert "error" in data


def test_create_badge_default_type(client):
    resp = client.post("/api/badge/create", json={
        "username": "defaultuser"
    })
    data = resp.get_json()
    assert data["success"] is True
    assert "Contributor" in data["alt_text"]


def test_create_badge_bounty_hunter_type(client):
    resp = client.post("/api/badge/create", json={
        "username": "hunter1",
        "badge_type": "bounty-hunter"
    })
    data = resp.get_json()
    assert data["success"] is True
    assert "Bounty Hunter" in data["alt_text"]
    # green color in URL
    assert "-green" in data["shield_url"]


def test_create_badge_empty_body(client):
    resp = client.post("/api/badge/create", data="", content_type="text/plain")
    data = resp.get_json()
    assert data["success"] is False


# ─── /api/badge/stats ──────────────────────────────────────────────

def test_badge_stats_empty(client):
    resp = client.get("/api/badge/stats")
    data = resp.get_json()
    assert data["total_badges"] == 0
    assert data["badge_types"] == {}
    assert data["total_bounties_earned"] == 0.0


def test_badge_stats_after_creation(client):
    # Create a badge first
    client.post("/api/badge/create", json={"username": "statuser", "badge_type": "developer"})
    resp = client.get("/api/badge/stats")
    data = resp.get_json()
    assert data["total_badges"] == 1
    assert "developer" in data["badge_types"]


# ─── /api/badge/list ───────────────────────────────────────────────

def test_list_badges_empty(client):
    resp = client.get("/api/badge/list")
    data = resp.get_json()
    assert data["badges"] == []


def test_list_badges_after_creation(client):
    client.post("/api/badge/create", json={"username": "listuser1", "badge_type": "supporter"})
    client.post("/api/badge/create", json={"username": "listuser2", "badge_type": "contributor"})
    resp = client.get("/api/badge/list")
    data = resp.get_json()
    assert len(data["badges"]) == 2
    usernames = [b["username"] for b in data["badges"]]
    assert "listuser1" in usernames
    assert "listuser2" in usernames


# ─── Flask test client fixture ─────────────────────────────────────

@pytest.fixture
def client():
    pbg.app.config["TESTING"] = True
    with pbg.app.test_client() as c:
        yield c