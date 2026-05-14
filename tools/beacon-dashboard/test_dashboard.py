#!/usr/bin/env python3
"""
Unit tests for Beacon Dashboard helpers.

Run:
    python -m pytest tools/beacon-dashboard/test_dashboard.py -v
"""

import csv
import json
import os
import sys
import tempfile
import time
import unittest

# Ensure the package is importable
sys.path.insert(0, os.path.dirname(__file__))

from dashboard_helpers import (
    VALID_KINDS,
    HIGH_VALUE_TIP_THRESHOLD,
    TransportHealth,
    apply_filter,
    check_alerts,
    compute_top_agents,
    compute_transport_health,
    count_envelopes_by_kind,
    count_envelopes_by_transport,
    export_csv,
    export_json,
    format_age,
    format_timestamp,
    _extract_amount,
    _extract_transport,
    parse_filter,
    truncate,
)


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_envelope(
    agent_id="bcn_abc123",
    kind="heartbeat",
    transport="discord",
    received_at=None,
    amount=0.0,
    nonce="n1",
    payload_hash="ph1",
):
    return {
        "agent_id": agent_id,
        "kind": kind,
        "transport": transport,
        "received_at": received_at or int(time.time()),
        "amount": amount,
        "nonce": nonce,
        "payload_hash": payload_hash,
    }


def _sample_envelopes():
    """Return a mixed set of envelopes for testing."""
    now = int(time.time())
    return [
        _make_envelope("bcn_alice", "hello", "discord", now - 10),
        _make_envelope("bcn_alice", "heartbeat", "discord", now - 8),
        _make_envelope("bcn_bob", "want", "telegram", now - 6),
        _make_envelope("bcn_bob", "bounty", "telegram", now - 4, amount=30.0),
        _make_envelope("bcn_charlie", "mayday", "irc", now - 2),
        _make_envelope("bcn_charlie", "heartbeat", "irc", now - 1),
        _make_envelope("bcn_dave", "accord", "websocket", now),
        _make_envelope("bcn_eve", "pushback", "discord", now, amount=75.0),
    ]


# ── envelope extraction tests ────────────────────────────────────────

class TestEnvelopeExtraction(unittest.TestCase):
    def test_extract_transport_normalizes_unknown_explicit_transport(self):
        envelope = {"transport": "matrix", "agent_id": "discord_agent_1"}

        self.assertEqual(_extract_transport(envelope), "other")

    def test_extract_transport_falls_back_to_agent_id_heuristics(self):
        self.assertEqual(_extract_transport({"agent_id": "TG_bridge"}), "telegram")
        self.assertEqual(_extract_transport({"agent_id": "unknown_agent"}), "beacon")

    def test_extract_amount_skips_invalid_aliases_until_valid_value(self):
        envelope = {"amount": "bad", "reward_rtc": "12.5"}

        self.assertEqual(_extract_amount(envelope), 12.5)

    def test_extract_amount_returns_zero_for_missing_or_invalid_values(self):
        self.assertEqual(_extract_amount({}), 0.0)
        self.assertEqual(
            _extract_amount(
                {"amount": "bad", "reward_rtc": None, "rtc_amount": object()}
            ),
            0.0,
        )


# ── parse_filter tests ───────────────────────────────────────────────

class TestParseFilter(unittest.TestCase):
    def test_empty_string(self):
        result = parse_filter("")
        self.assertIsNone(result["kind"])
        self.assertIsNone(result["agent"])
        self.assertIsNone(result["transport"])
        self.assertIsNone(result["text"])

    def test_none_input(self):
        result = parse_filter(None)
        self.assertIsNone(result["kind"])

    def test_kind_filter(self):
        result = parse_filter("kind:mayday")
        self.assertEqual(result["kind"], "mayday")
        self.assertIsNone(result["agent"])

    def test_kind_filter_case_insensitive(self):
        result = parse_filter("kind:HEARTBEAT")
        self.assertEqual(result["kind"], "heartbeat")

    def test_agent_filter(self):
        result = parse_filter("agent:bcn_abc123")
        self.assertEqual(result["agent"], "bcn_abc123")

    def test_transport_filter(self):
        result = parse_filter("transport:discord")
        self.assertEqual(result["transport"], "discord")

    def test_free_text(self):
        result = parse_filter("some random query")
        self.assertEqual(result["text"], "some random query")
        self.assertIsNone(result["kind"])

    def test_combined_filters(self):
        result = parse_filter("kind:hello agent:bcn_x transport:irc extra")
        self.assertEqual(result["kind"], "hello")
        self.assertEqual(result["agent"], "bcn_x")
        self.assertEqual(result["transport"], "irc")
        self.assertEqual(result["text"], "extra")

    def test_invalid_kind_becomes_free_text(self):
        result = parse_filter("kind:invalid_kind")
        self.assertIsNone(result["kind"])
        self.assertEqual(result["text"], "kind:invalid_kind")

    def test_whitespace_only(self):
        result = parse_filter("   ")
        self.assertIsNone(result["kind"])
        self.assertIsNone(result["text"])


# ── apply_filter tests ───────────────────────────────────────────────

class TestApplyFilter(unittest.TestCase):
    def setUp(self):
        self.envelopes = _sample_envelopes()

    def test_no_filter_returns_all(self):
        result = apply_filter(self.envelopes, "")
        self.assertEqual(len(result), len(self.envelopes))

    def test_none_filter_returns_all(self):
        result = apply_filter(self.envelopes, None)
        self.assertEqual(len(result), len(self.envelopes))

    def test_filter_by_kind(self):
        result = apply_filter(self.envelopes, "kind:heartbeat")
        self.assertTrue(all(e["kind"] == "heartbeat" for e in result))
        self.assertEqual(len(result), 2)

    def test_filter_by_agent(self):
        result = apply_filter(self.envelopes, "agent:alice")
        self.assertTrue(all("alice" in e["agent_id"] for e in result))
        self.assertEqual(len(result), 2)

    def test_filter_by_transport(self):
        result = apply_filter(self.envelopes, "transport:telegram")
        self.assertTrue(all(e["transport"] == "telegram" for e in result))
        self.assertEqual(len(result), 2)

    def test_filter_by_free_text(self):
        result = apply_filter(self.envelopes, "mayday")
        self.assertTrue(len(result) >= 1)
        self.assertTrue(any(e["kind"] == "mayday" for e in result))

    def test_combined_filter(self):
        result = apply_filter(self.envelopes, "kind:heartbeat transport:discord")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["agent_id"], "bcn_alice")

    def test_filter_no_match(self):
        result = apply_filter(self.envelopes, "agent:nonexistent")
        self.assertEqual(len(result), 0)


# ── count functions ──────────────────────────────────────────────────

class TestCountFunctions(unittest.TestCase):
    def setUp(self):
        self.envelopes = _sample_envelopes()

    def test_count_by_kind(self):
        counts = count_envelopes_by_kind(self.envelopes)
        self.assertEqual(counts["heartbeat"], 2)
        self.assertEqual(counts["hello"], 1)
        self.assertEqual(counts["mayday"], 1)

    def test_count_by_transport(self):
        counts = count_envelopes_by_transport(self.envelopes)
        self.assertEqual(counts["discord"], 3)
        self.assertEqual(counts["telegram"], 2)
        self.assertEqual(counts["irc"], 2)
        self.assertEqual(counts["websocket"], 1)

    def test_empty_list(self):
        self.assertEqual(count_envelopes_by_kind([]), {})
        self.assertEqual(count_envelopes_by_transport([]), {})


# ── compute_transport_health tests ───────────────────────────────────

class TestComputeTransportHealth(unittest.TestCase):
    def setUp(self):
        self.envelopes = _sample_envelopes()

    def test_returns_all_transports(self):
        health = compute_transport_health(self.envelopes)
        self.assertIn("discord", health)
        self.assertIn("telegram", health)
        self.assertIn("irc", health)
        self.assertIn("websocket", health)

    def test_total_counts(self):
        health = compute_transport_health(self.envelopes)
        self.assertEqual(health["discord"].total, 3)
        self.assertEqual(health["telegram"].total, 2)

    def test_kind_breakdown(self):
        health = compute_transport_health(self.envelopes)
        self.assertIn("hello", health["discord"].kinds)
        self.assertIn("heartbeat", health["discord"].kinds)

    def test_top_agents(self):
        health = compute_transport_health(self.envelopes)
        discord_agents = [a[0] for a in health["discord"].top_agents]
        self.assertIn("bcn_alice", discord_agents)

    def test_mayday_count(self):
        health = compute_transport_health(self.envelopes)
        self.assertEqual(health["irc"].mayday_count, 1)
        self.assertEqual(health["discord"].mayday_count, 0)

    def test_status_healthy(self):
        health = compute_transport_health(self.envelopes)
        # All envelopes are recent (within last few seconds)
        for h in health.values():
            self.assertIn(h.status, ("healthy", "degraded"))

    def test_status_icon(self):
        h = TransportHealth("test")
        h.last_seen = int(time.time())
        self.assertEqual(h.status_icon, "●")
        h.last_seen = int(time.time()) - 300
        self.assertEqual(h.status_icon, "◐")
        h.last_seen = int(time.time()) - 700
        self.assertEqual(h.status_icon, "○")

    def test_to_dict(self):
        health = compute_transport_health(self.envelopes)
        d = health["discord"].to_dict()
        self.assertIn("name", d)
        self.assertIn("status", d)
        self.assertIn("total", d)
        self.assertIn("throughput_per_min", d)

    def test_empty_envelopes(self):
        health = compute_transport_health([])
        self.assertEqual(len(health), 0)


# ── compute_top_agents tests ─────────────────────────────────────────

class TestComputeTopAgents(unittest.TestCase):
    def setUp(self):
        self.envelopes = _sample_envelopes()

    def test_returns_ranked_list(self):
        agents = compute_top_agents(self.envelopes)
        self.assertTrue(len(agents) > 0)
        # First agent should have highest total
        totals = [a["total"] for a in agents]
        self.assertEqual(totals, sorted(totals, reverse=True))

    def test_limit(self):
        agents = compute_top_agents(self.envelopes, limit=2)
        self.assertEqual(len(agents), 2)

    def test_agent_has_kinds(self):
        agents = compute_top_agents(self.envelopes)
        for agent in agents:
            self.assertIn("agent_id", agent)
            self.assertIn("total", agent)
            self.assertIn("kinds", agent)
            self.assertIn("last_seen", agent)

    def test_top_agent_is_alice_or_bob(self):
        agents = compute_top_agents(self.envelopes)
        top_ids = [a["agent_id"] for a in agents[:2]]
        # alice and bob each have 2 envelopes, charlie also has 2
        self.assertTrue(
            any(aid in top_ids for aid in ["bcn_alice", "bcn_bob", "bcn_charlie"])
        )

    def test_empty_envelopes(self):
        agents = compute_top_agents([])
        self.assertEqual(len(agents), 0)


# ── check_alerts tests ───────────────────────────────────────────────

class TestCheckAlerts(unittest.TestCase):
    def test_mayday_alert(self):
        envs = [_make_envelope(kind="mayday", received_at=100)]
        alerts = check_alerts(envs, last_alert_ts=0)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["type"], "mayday")

    def test_high_value_alert(self):
        envs = [_make_envelope(amount=100.0, received_at=100)]
        alerts = check_alerts(envs, last_alert_ts=0)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["type"], "high_value")

    def test_both_alerts(self):
        envs = [
            _make_envelope(kind="mayday", amount=100.0, received_at=100)
        ]
        alerts = check_alerts(envs, last_alert_ts=0)
        self.assertEqual(len(alerts), 2)
        types = {a["type"] for a in alerts}
        self.assertEqual(types, {"mayday", "high_value"})

    def test_no_alert_below_threshold(self):
        envs = [_make_envelope(amount=10.0, received_at=100)]
        alerts = check_alerts(envs, last_alert_ts=0)
        self.assertEqual(len(alerts), 0)

    def test_respects_last_alert_ts(self):
        envs = [_make_envelope(kind="mayday", received_at=50)]
        alerts = check_alerts(envs, last_alert_ts=100)
        self.assertEqual(len(alerts), 0)

    def test_empty_envelopes(self):
        alerts = check_alerts([], last_alert_ts=0)
        self.assertEqual(len(alerts), 0)


# ── export tests ─────────────────────────────────────────────────────

class TestExport(unittest.TestCase):
    def setUp(self):
        self.envelopes = _sample_envelopes()
        self.health = compute_transport_health(self.envelopes)
        self.agents = compute_top_agents(self.envelopes)
        self.tmpdir = tempfile.mkdtemp()

    def test_export_csv_creates_file(self):
        filepath = export_csv(self.envelopes, self.health, self.tmpdir)
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith(".csv"))

    def test_export_csv_content(self):
        filepath = export_csv(self.envelopes, self.health, self.tmpdir)
        with open(filepath) as f:
            content = f.read()
        self.assertIn("Transport Health Summary", content)
        self.assertIn("agent_id", content)
        self.assertIn("bcn_alice", content)

    def test_export_json_creates_file(self):
        filepath = export_json(
            self.envelopes, self.health, self.agents, self.tmpdir
        )
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith(".json"))

    def test_export_json_valid(self):
        filepath = export_json(
            self.envelopes, self.health, self.agents, self.tmpdir
        )
        with open(filepath) as f:
            data = json.load(f)
        self.assertIn("exported_at", data)
        self.assertIn("transport_health", data)
        self.assertIn("top_agents", data)
        self.assertIn("envelopes", data)
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["total_envelopes"], len(self.envelopes))

    def test_export_json_health_data(self):
        filepath = export_json(
            self.envelopes, self.health, self.agents, self.tmpdir
        )
        with open(filepath) as f:
            data = json.load(f)
        self.assertIn("discord", data["transport_health"])
        discord_h = data["transport_health"]["discord"]
        self.assertEqual(discord_h["total"], 3)

    def test_export_empty_envelopes(self):
        filepath = export_csv([], {}, self.tmpdir)
        self.assertTrue(os.path.exists(filepath))
        filepath2 = export_json([], {}, [], self.tmpdir)
        self.assertTrue(os.path.exists(filepath2))


# ── format helpers tests ─────────────────────────────────────────────

class TestFormatHelpers(unittest.TestCase):
    def test_format_timestamp_valid(self):
        ts = int(time.time())
        result = format_timestamp(ts)
        self.assertNotEqual(result, "never")
        self.assertRegex(result, r"\d{2}:\d{2}:\d{2}")

    def test_format_timestamp_none(self):
        self.assertEqual(format_timestamp(None), "never")

    def test_format_timestamp_zero(self):
        self.assertEqual(format_timestamp(0), "never")

    def test_format_age_recent(self):
        ts = int(time.time()) - 30
        result = format_age(ts)
        self.assertIn("s ago", result)

    def test_format_age_minutes(self):
        ts = int(time.time()) - 300
        result = format_age(ts)
        self.assertIn("m ago", result)

    def test_format_age_hours(self):
        ts = int(time.time()) - 7200
        result = format_age(ts)
        self.assertIn("h ago", result)

    def test_format_age_days(self):
        ts = int(time.time()) - 172800
        result = format_age(ts)
        self.assertIn("d ago", result)

    def test_format_age_none(self):
        self.assertEqual(format_age(None), "—")

    def test_format_age_zero(self):
        self.assertEqual(format_age(0), "—")

    def test_truncate_short(self):
        self.assertEqual(truncate("hello", 10), "hello")

    def test_truncate_exact(self):
        self.assertEqual(truncate("hello", 5), "hello")

    def test_truncate_long(self):
        result = truncate("hello world", 8)
        self.assertEqual(len(result), 8)
        self.assertTrue(result.endswith("…"))

    def test_truncate_one(self):
        result = truncate("abc", 1)
        self.assertEqual(result, "…")


# ── TransportHealth edge cases ───────────────────────────────────────

class TestTransportHealthEdge(unittest.TestCase):
    def test_unknown_status(self):
        h = TransportHealth("test")
        self.assertEqual(h.status, "unknown")
        self.assertEqual(h.status_icon, "?")

    def test_offline_status(self):
        h = TransportHealth("test")
        h.last_seen = int(time.time()) - 1000
        self.assertEqual(h.status, "offline")

    def test_degraded_status(self):
        h = TransportHealth("test")
        h.last_seen = int(time.time()) - 300
        self.assertEqual(h.status, "degraded")


if __name__ == "__main__":
    unittest.main()
