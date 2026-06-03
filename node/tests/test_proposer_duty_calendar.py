# SPDX-License-Identifier: MIT

import os
import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_DIR))

from proposer_duty_calendar import (  # noqa: E402
    build_proposer_duty_calendar,
    build_proposer_schedule,
    parse_peer_config,
)


def test_build_proposer_schedule_uses_sorted_round_robin_nodes():
    schedule = build_proposer_schedule(
        current_epoch=4,
        nodes=["node3", "node1", "node2"],
        lookahead=3,
    )

    assert [row["epoch"] for row in schedule] == [4, 5, 6, 7]
    assert [row["proposer"] for row in schedule] == [
        "node2",
        "node3",
        "node1",
        "node2",
    ]
    assert schedule[0]["is_current"] is True


def test_parse_peer_config_ignores_malformed_entries():
    peers = parse_peer_config(
        "node2=https://node2.example,node3=http://127.0.0.1:9002,bad,no_url="
    )

    assert peers == {
        "node2": "https://node2.example",
        "node3": "http://127.0.0.1:9002",
    }


def test_calendar_includes_recent_vote_history():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "votes.db")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE p2p_epoch_votes (
                    epoch INTEGER NOT NULL,
                    proposal_hash TEXT NOT NULL,
                    voter TEXT NOT NULL,
                    vote TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    PRIMARY KEY (epoch, proposal_hash, voter)
                )
                """
            )
            conn.executemany(
                "INSERT INTO p2p_epoch_votes VALUES (?, ?, ?, ?, ?)",
                [
                    (4, "hash-a", "node1", "accept", 100),
                    (4, "hash-a", "node2", "accept", 101),
                    (3, "hash-b", "node3", "reject", 90),
                ],
            )

        calendar = build_proposer_duty_calendar(
            current_epoch=4,
            node_id="node2",
            peers={"node1": "https://node1.example", "node3": "https://node3.example"},
            db_path=db_path,
            lookahead=1,
            history_limit=2,
        )

    assert calendar["current_proposer"] == "node2"
    assert calendar["current_node_is_proposer"] is True
    assert calendar["metrics"]["scheduled_epochs"] == 2
    assert calendar["history"][0]["epoch"] == 4
    assert calendar["history"][0]["votes"] == {"accept": 2}
    assert calendar["history"][0]["voters"] == ["node1", "node2"]


class _NoopMetric:
    def __init__(self, *args, **kwargs):
        pass

    def inc(self, *args, **kwargs):
        pass

    def dec(self, *args, **kwargs):
        pass

    def set(self, *args, **kwargs):
        pass

    def observe(self, *args, **kwargs):
        pass

    def labels(self, *args, **kwargs):
        return self


def test_integrated_route_returns_calendar_payload(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "route.db")
        monkeypatch.setenv("RUSTCHAIN_DB_PATH", db_path)
        monkeypatch.setenv("RC_ADMIN_KEY", "0" * 32)
        monkeypatch.setenv("RC_NODE_ID", "node2")
        monkeypatch.setenv(
            "RC_P2P_PEERS",
            "node1=https://node1.example,node3=https://node3.example",
        )

        prometheus_client = None
        previous_metrics = None
        try:
            import prometheus_client

            previous_metrics = (
                prometheus_client.Counter,
                prometheus_client.Gauge,
                prometheus_client.Histogram,
            )
            prometheus_client.Counter = _NoopMetric
            prometheus_client.Gauge = _NoopMetric
            prometheus_client.Histogram = _NoopMetric
        except ModuleNotFoundError:
            pass
        try:
            spec = importlib.util.spec_from_file_location(
                "rustchain_integrated_proposer_calendar_test",
                NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py",
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            if prometheus_client is not None and previous_metrics is not None:
                (
                    prometheus_client.Counter,
                    prometheus_client.Gauge,
                    prometheus_client.Histogram,
                ) = previous_metrics

        module.DB_PATH = db_path
        monkeypatch.setattr(module, "current_slot", lambda: 4 * module.EPOCH_SLOTS)

        response = module.app.test_client().get(
            "/epoch/proposer-duty-calendar?lookahead=2&history_limit=0"
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["node_id"] == "node2"
    assert payload["current_epoch"] == 4
    assert payload["current_proposer"] == "node2"
    assert payload["current_node_is_proposer"] is True
    assert [row["proposer"] for row in payload["schedule"]] == [
        "node2",
        "node3",
        "node1",
    ]
