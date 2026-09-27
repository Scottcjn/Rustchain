# SPDX-License-Identifier: MIT
"""Regression: the node's best-effort rewards import must actually succeed.

Production ran for months with HAVE_REWARDS False because the node imported
``_epoch_eligible_miners`` (never defined in rewards_implementation_rip200) and
later called ``register_rewards`` (the module defines ``register_rewards_rip200``).
The import sits in try/except, so the only symptom was a "WARN: Rewards module
not loaded" line on every worker start. Fixed on main by #8249; these tests pin it.
"""

import ast
import sqlite3
import sys
from pathlib import Path

import pytest

import rewards_implementation_rip200 as rewards

integrated_node = sys.modules["integrated_node"]

NODE_SRC = Path(__file__).resolve().parent.parent / "node" / "rustchain_v2_integrated_v2.2.1_rip200.py"
ADMIN_KEY = "0" * 32  # set by tests/conftest.py before the node module loads


def _node_tree():
    return ast.parse(NODE_SRC.read_text(encoding="utf-8"))


def test_every_name_imported_from_rewards_module_exists():
    imported = [
        alias.name
        for node in ast.walk(_node_tree())
        if isinstance(node, ast.ImportFrom) and node.module == "rewards_implementation_rip200"
        for alias in node.names
    ]
    assert imported, "node no longer imports from rewards_implementation_rip200"
    missing = [name for name in imported if not hasattr(rewards, name)]
    assert missing == [], f"node imports names the rewards module does not define: {missing}"


def test_node_loads_rewards_module():
    assert integrated_node.HAVE_REWARDS is True
    assert integrated_node.settle_epoch.__name__ == "settle_epoch_rip200"
    assert integrated_node.settle_epoch.__module__ == "rewards_implementation_rip200"
    assert integrated_node.total_balances.__module__ == "rewards_implementation_rip200"


def test_node_never_registers_module_routes():
    """register_rewards_rip200 would shadow the native public balance handlers."""
    calls = [
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(_node_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    ]
    assert not [c for c in calls if c.startswith("register_rewards")]


@pytest.mark.parametrize(
    "rule, method, endpoint",
    [
        ("/rewards/settle", "POST", "api_rewards_settle"),
        ("/consensus/round_robin_status", "GET", "consensus_round_robin_status"),
        ("/wallet/balance", "GET", "api_wallet_balance"),
        ("/wallet/balances/all", "GET", "api_wallet_balances_all"),
        ("/lottery/eligibility", "GET", "lottery_eligibility"),
    ],
)
def test_reward_routes_are_the_native_handlers(rule, method, endpoint):
    rules = [r for r in integrated_node.app.url_map.iter_rules() if r.rule == rule]
    assert len(rules) == 1, f"{rule} registered {len(rules)} times"
    assert rules[0].endpoint == endpoint
    assert method in rules[0].methods
    assert integrated_node.app.view_functions[endpoint].__module__ == "integrated_node"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client


@pytest.mark.parametrize(
    "method, path",
    [("post", "/rewards/settle"), ("get", "/consensus/round_robin_status")],
)
@pytest.mark.parametrize("headers", [{}, {"X-Admin-Key": "wrong"}])
def test_admin_reward_routes_reject_missing_or_wrong_key(client, method, path, headers):
    response = getattr(client, method)(path, headers=headers, json={"epoch": 0})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "method, path",
    [("post", "/rewards/settle"), ("get", "/consensus/round_robin_status")],
)
def test_admin_reward_routes_disabled_when_admin_key_unset(client, monkeypatch, method, path):
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    response = getattr(client, method)(path, headers={"X-Admin-Key": ""}, json={"epoch": 0})
    assert response.status_code == 503


def test_settle_fails_closed_without_rewards_module(client, monkeypatch):
    monkeypatch.setattr(integrated_node, "HAVE_REWARDS", False)
    monkeypatch.setattr(integrated_node, "settle_epoch", None)
    unauth = client.post("/rewards/settle", json={"epoch": 0})
    assert unauth.status_code == 401  # auth still checked first
    response = client.post("/rewards/settle", headers={"X-Admin-Key": ADMIN_KEY}, json={"epoch": 0})
    assert response.status_code == 503
    assert response.get_json()["code"] == "REWARDS_MODULE_UNAVAILABLE"


def test_native_total_balances_matches_module():
    db = sqlite3.connect(":memory:")
    assert integrated_node._native_total_balances(db) == rewards.total_balances(db) == 0  # no table
    db.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)")
    assert integrated_node._native_total_balances(db) == rewards.total_balances(db) == 0
    db.executemany("INSERT INTO balances VALUES (?, ?)", [("a", 1_500_000), ("b", 250)])
    assert integrated_node._native_total_balances(db) == rewards.total_balances(db) == 1_500_250
