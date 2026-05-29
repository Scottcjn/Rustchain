# SPDX-License-Identifier: MIT
"""
PoC: GET /governance/proposal/<id> unbounded votes fetchall() — OOM DoS

Without a LIMIT on the governance_votes query, any caller can trigger the node
to load all votes for a proposal into RAM. On a chain with thousands of active
miners all voting on a single proposal the response inflates proportionally and
will OOM-kill the node process.

Fix: add votes_limit / votes_offset pagination (cap 500) with a total_votes
count so callers can page through the full vote set.
"""
import importlib.util as _ilu
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

_module_db_fd, _MODULE_DB = tempfile.mkstemp(suffix=".db")
os.close(_module_db_fd)

os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
os.environ["RUSTCHAIN_DB_PATH"] = _MODULE_DB

_spec = _ilu.spec_from_file_location(
    "rustchain_node_votes",
    os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_app = _mod.app


def _insert_proposal_and_votes(n_votes: int) -> int:
    now = int(time.time())
    with sqlite3.connect(_MODULE_DB) as conn:
        _mod._ensure_governance_tables(conn.cursor())
        conn.execute(
            """
            INSERT INTO governance_proposals
                (proposer_wallet, title, description, status, yes_weight, no_weight,
                 created_at, activated_at, ends_at)
            VALUES (?, ?, ?, 'active', 0, 0, ?, ?, ?)
            """,
            (
                "RTCtest000000000000000000000000000000000000",
                "Test proposal",
                "Test description",
                now,
                now,
                now + 86400,
            ),
        )
        pid = conn.execute(
            "SELECT id FROM governance_proposals ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        for i in range(n_votes):
            wallet = "RTC" + str(i).zfill(40)
            conn.execute(
                """
                INSERT OR IGNORE INTO governance_votes
                    (proposal_id, voter_wallet, vote, weight, multiplier,
                     base_balance_rtc, signature, public_key, nonce, created_at)
                VALUES (?, ?, 'yes', 1.0, 1.0, 1.0, 'sig', 'pk', ?, ?)
                """,
                (pid, wallet, str(i), now + i),
            )
        conn.commit()
    return pid


class TestGovernanceVotesLimit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _app.config["TESTING"] = True
        cls.client = _app.test_client()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(_MODULE_DB)
        except OSError:
            pass

    def test_default_limit_caps_votes(self):
        """Without votes_limit param, response must not return more than 200 votes."""
        pid = _insert_proposal_and_votes(300)
        resp = self.client.get(f"/governance/proposal/{pid}")
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertTrue(body["ok"])
        self.assertLessEqual(len(body["votes"]), 200)
        self.assertEqual(body["votes_total"], 300)

    def test_custom_limit_respected(self):
        """votes_limit=50 must return at most 50 votes."""
        pid = _insert_proposal_and_votes(100)
        resp = self.client.get(f"/governance/proposal/{pid}?votes_limit=50")
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertLessEqual(len(body["votes"]), 50)
        self.assertEqual(body["votes_limit"], 50)

    def test_max_limit_capped_at_500(self):
        """votes_limit=9999 must be silently capped at 500."""
        pid = _insert_proposal_and_votes(10)
        resp = self.client.get(f"/governance/proposal/{pid}?votes_limit=9999")
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertEqual(body["votes_limit"], 500)

    def test_offset_pagination_no_overlap(self):
        """votes_offset allows paging and pages must not overlap."""
        pid = _insert_proposal_and_votes(30)
        r1 = json.loads(self.client.get(f"/governance/proposal/{pid}?votes_limit=10&votes_offset=0").data)
        r2 = json.loads(self.client.get(f"/governance/proposal/{pid}?votes_limit=10&votes_offset=10").data)
        self.assertEqual(len(r1["votes"]), 10)
        self.assertEqual(len(r2["votes"]), 10)
        wallets_p1 = {v["voter_wallet"] for v in r1["votes"]}
        wallets_p2 = {v["voter_wallet"] for v in r2["votes"]}
        self.assertTrue(wallets_p1.isdisjoint(wallets_p2), "Pages must not overlap")

    def test_invalid_votes_limit_returns_400(self):
        """Non-integer votes_limit must return 400."""
        pid = _insert_proposal_and_votes(1)
        resp = self.client.get(f"/governance/proposal/{pid}?votes_limit=banana")
        self.assertEqual(resp.status_code, 400)

    def test_invalid_votes_offset_returns_400(self):
        """Non-integer votes_offset must return 400."""
        pid = _insert_proposal_and_votes(1)
        resp = self.client.get(f"/governance/proposal/{pid}?votes_offset=banana")
        self.assertEqual(resp.status_code, 400)

    def test_total_votes_count_always_present(self):
        """Response must include votes_total regardless of limit."""
        pid = _insert_proposal_and_votes(5)
        resp = self.client.get(f"/governance/proposal/{pid}?votes_limit=2")
        body = json.loads(resp.data)
        self.assertIn("votes_total", body)
        self.assertEqual(body["votes_total"], 5)
        self.assertEqual(len(body["votes"]), 2)

    def test_proposal_not_found_returns_404(self):
        """Non-existent proposal must return 404."""
        resp = self.client.get("/governance/proposal/999999")
        self.assertEqual(resp.status_code, 404)

    def test_votes_offset_and_limit_response_fields(self):
        """Response must echo back votes_limit and votes_offset."""
        pid = _insert_proposal_and_votes(5)
        resp = self.client.get(f"/governance/proposal/{pid}?votes_limit=3&votes_offset=1")
        body = json.loads(resp.data)
        self.assertEqual(body["votes_limit"], 3)
        self.assertEqual(body["votes_offset"], 1)


if __name__ == "__main__":
    unittest.main()
