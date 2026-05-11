"""
test_sophia_core.py -- Tests for SophiaCore Attestation Inspector.
All Ollama calls are mocked -- NO real network calls.

Covers:
  - All 4 verdict levels (rule-based)
  - Ollama prompt construction
  - Ollama response parsing
  - Fallback to rule-based analysis
  - Failover chain
  - Database CRUD
  - API endpoints (Flask test client)
  - Batch scheduler logic
  - Explorer emoji mapping
"""

import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

# Add parent dir to path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sophia_db import (
    init_db, get_connection, store_inspection, enqueue_review,
    get_latest_inspection, get_miner_history, get_inspection_history,
    get_pending_reviews, mark_reviewed, get_dashboard_stats,
    fingerprint_hash, get_low_confidence_miners, get_verdict_changed_miners,
    get_all_miner_ids,
)
from sophia_core import (
    SophiaCoreInspector, VERDICTS, _build_analysis_prompt,
    _rule_based_fallback, _parse_ollama_response, MODEL,
)


# -- Fingerprint fixtures -------------------------------------------------

def _good_fingerprint():
    """Fingerprint that should get APPROVED."""
    return {
        "claimed_cpu": "AMD EPYC 7763",
        "clock_drift_cv": 0.005,
        "cache_hierarchy": {
            "l1_latency_ns": 1.2,
            "l2_latency_ns": 4.5,
            "l3_latency_ns": 12.8,
        },
        "simd_identity": {"avx2": True, "avx512": True, "sse4_2": True},
        "thermal": {"cpu_temp_c": 62},
        "stability_score": 0.92,
        "epoch": 1042,
    }


def _cautious_fingerprint():
    """Fingerprint that should get CAUTIOUS (score 1-2)."""
    return {
        "claimed_cpu": "Intel Xeon E5-2680",
        "clock_drift_cv": 0.005,  # +1
        "cache_hierarchy": {
            "l1_latency_ns": 1.0,
            "l2_latency_ns": 3.5,
            "l3_latency_ns": 11.0,
        },  # +1
        "simd_identity": {"avx2": True},  # +1
        "thermal": {"cpu_temp_c": 18},  # no bonus (between 15 and 25)
        "stability_score": 0.40,  # -2 (below 0.5)
        "epoch": 1042,
    }


def _suspicious_fingerprint():
    """Fingerprint that should get SUSPICIOUS (score 0 to -2)."""
    return {
        "claimed_cpu": "AMD EPYC 7763",
        "clock_drift_cv": 0.0005,  # -3 (suspiciously low)
        "cache_hierarchy": {
            "l1_latency_ns": 1.2,
            "l2_latency_ns": 4.5,
            "l3_latency_ns": 12.8,
        },  # +1
        "simd_identity": {"avx2": True},  # +1
        "thermal": {"cpu_temp_c": 62},  # +1
        "stability_score": 0.70,  # no bonus (between 0.5 and 0.85)
        "epoch": 1042,
    }


def _rejected_fingerprint():
    """Fingerprint that should get REJECTED."""
    return {
        "claimed_cpu": "FakeChip 9000",
        "clock_drift_cv": 0.0001,  # emulation
        "cache_hierarchy": {
            "l1_latency_ns": 5.0,
            "l2_latency_ns": 5.0,
            "l3_latency_ns": 5.0,  # uniform = emulation
        },
        "simd_identity": {},  # no SIMD reported
        "thermal": {"cpu_temp_c": 10},  # impossibly low
        "stability_score": 1.0,  # too perfect
        "epoch": 1042,
    }


# -- Database tests --------------------------------------------------------

class TestSophiaDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        init_db(self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    def _conn(self):
        return get_connection(self.db_path)

    def test_init_db_idempotent(self):
        init_db(self.db_path)
        init_db(self.db_path)
        conn = self._conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        names = {r["name"] for r in tables}
        self.assertIn("sophia_inspections", names)
        self.assertIn("sophia_review_queue", names)

    def test_store_and_get_inspection(self):
        conn = self._conn()
        fp = _good_fingerprint()
        row_id = store_inspection(
            conn, "miner_abc", "APPROVED", 0.85, "Looks good",
            "rule-based-v1", fp
        )
        self.assertIsInstance(row_id, int)

        row = get_latest_inspection(conn, "miner_abc")
        self.assertEqual(row["verdict"], "APPROVED")
        self.assertAlmostEqual(row["confidence"], 0.85)
        self.assertEqual(row["inspection_type"], "on-demand")
        conn.close()

    def test_store_with_inspection_type(self):
        conn = self._conn()
        store_inspection(
            conn, "miner_x", "CAUTIOUS", 0.6, "hmm",
            "rule-based-v1", {}, inspection_type="batch"
        )
        row = get_latest_inspection(conn, "miner_x")
        self.assertEqual(row["inspection_type"], "batch")
        conn.close()

    def test_miner_history(self):
        conn = self._conn()
        for i in range(5):
            store_inspection(
                conn, "miner_h", "APPROVED", 0.8 + i * 0.01,
                f"run {i}", "rule-based-v1", {"i": i}
            )
        history = get_miner_history(conn, "miner_h", limit=3)
        self.assertEqual(len(history), 3)
        # Most recent first
        self.assertGreater(history[0]["confidence"], history[2]["confidence"])
        conn.close()

    def test_inspection_history_pagination(self):
        conn = self._conn()
        for i in range(10):
            store_inspection(
                conn, f"m{i}", "APPROVED", 0.8,
                "ok", "rb", {"i": i}
            )
        page = get_inspection_history(conn, page=1, per_page=3)
        self.assertEqual(len(page["inspections"]), 3)
        self.assertEqual(page["total"], 10)
        self.assertEqual(page["pages"], 4)
        conn.close()

    def test_review_queue(self):
        conn = self._conn()
        iid = store_inspection(
            conn, "m_sus", "SUSPICIOUS", 0.55,
            "fishy", "rb", {}
        )
        enqueue_review(conn, iid, "m_sus", verdict="SUSPICIOUS")

        pending = get_pending_reviews(conn)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["miner_id"], "m_sus")
        self.assertEqual(pending[0]["verdict"], "SUSPICIOUS")

        mark_reviewed(conn, pending[0]["id"], "admin_alice")
        self.assertEqual(len(get_pending_reviews(conn)), 0)
        conn.close()

    def test_dashboard_stats(self):
        conn = self._conn()
        store_inspection(conn, "m1", "APPROVED", 0.9, "", "rb", {})
        store_inspection(conn, "m2", "REJECTED", 0.8, "", "rb", {})
        enqueue_review(conn, 1, "m1", verdict="APPROVED")

        stats = get_dashboard_stats(conn)
        self.assertEqual(stats["total_inspections"], 2)
        self.assertEqual(stats["by_verdict"]["APPROVED"], 1)
        self.assertEqual(stats["pending_reviews"], 1)
        conn.close()

    def test_fingerprint_hash_deterministic(self):
        fp = {"b": 2, "a": 1}
        h1 = fingerprint_hash(fp)
        h2 = fingerprint_hash({"a": 1, "b": 2})
        self.assertEqual(h1, h2)

    def test_get_latest_inspection_missing(self):
        conn = self._conn()
        self.assertIsNone(get_latest_inspection(conn, "nobody"))
        conn.close()

    def test_low_confidence_miners(self):
        conn = self._conn()
        store_inspection(conn, "m_low", "SUSPICIOUS", 0.3, "", "rb", {})
        store_inspection(conn, "m_ok", "APPROVED", 0.9, "", "rb", {})
        low = get_low_confidence_miners(conn, threshold=0.5)
        ids = [r["miner_id"] for r in low]
        self.assertIn("m_low", ids)
        self.assertNotIn("m_ok", ids)
        conn.close()

    def test_verdict_changed_miners(self):
        conn = self._conn()
        store_inspection(conn, "m_flip", "APPROVED", 0.9, "", "rb", {"v": 1})
        time.sleep(0.01)
        store_inspection(conn, "m_flip", "REJECTED", 0.8, "", "rb", {"v": 2})
        changed = get_verdict_changed_miners(conn)
        ids = [r["miner_id"] for r in changed]
        self.assertIn("m_flip", ids)
        conn.close()

    def test_get_all_miner_ids(self):
        conn = self._conn()
        store_inspection(conn, "alpha", "APPROVED", 0.9, "", "rb", {})
        store_inspection(conn, "beta", "APPROVED", 0.9, "", "rb", {})
        store_inspection(conn, "alpha", "CAUTIOUS", 0.6, "", "rb", {})
        ids = get_all_miner_ids(conn)
        self.assertEqual(sorted(ids), ["alpha", "beta"])
        conn.close()


# -- Core / Rule-based tests -----------------------------------------------

class TestRuleBasedFallback(unittest.TestCase):
    def test_approved_verdict(self):
        result = _rule_based_fallback(_good_fingerprint())
        self.assertEqual(result["verdict"], "APPROVED")
        self.assertGreaterEqual(result["confidence"], 0.6)

    def test_cautious_verdict(self):
        result = _rule_based_fallback(_cautious_fingerprint())
        self.assertEqual(result["verdict"], "CAUTIOUS")

    def test_suspicious_verdict(self):
        result = _rule_based_fallback(_suspicious_fingerprint())
        self.assertEqual(result["verdict"], "SUSPICIOUS")

    def test_rejected_verdict(self):
        result = _rule_based_fallback(_rejected_fingerprint())
        self.assertEqual(result["verdict"], "REJECTED")
        self.assertGreaterEqual(result["confidence"], 0.6)

    def test_empty_fingerprint(self):
        result = _rule_based_fallback({})
        # No data -> insufficient -> SUSPICIOUS range
        self.assertIn(result["verdict"], ("CAUTIOUS", "SUSPICIOUS"))

    def test_reasoning_populated(self):
        result = _rule_based_fallback(_good_fingerprint())
        self.assertTrue(len(result["reasoning"]) > 0)


# -- Prompt construction ---------------------------------------------------

class TestPromptConstruction(unittest.TestCase):
    def test_prompt_contains_fingerprint(self):
        fp = _good_fingerprint()
        prompt = _build_analysis_prompt(fp)
        self.assertIn("AMD EPYC 7763", prompt)
        self.assertIn("VERDICT:", prompt)
        self.assertIn("CONFIDENCE:", prompt)
        self.assertIn("REASONING:", prompt)

    def test_prompt_template_fields(self):
        fp = {"clock_drift_cv": 0.005, "claimed_cpu": "TestCPU"}
        prompt = _build_analysis_prompt(fp)
        self.assertIn("TestCPU", prompt)
        self.assertIn("Analyze this hardware fingerprint", prompt)


# -- Ollama response parsing -----------------------------------------------

class TestOllamaResponseParsing(unittest.TestCase):
    def test_parse_valid_response(self):
        raw = (
            "VERDICT: APPROVED\n"
            "CONFIDENCE: 0.92\n"
            "REASONING: All metrics check out"
        )
        result = _parse_ollama_response(raw)
        self.assertEqual(result["verdict"], "APPROVED")
        self.assertAlmostEqual(result["confidence"], 0.92)
        self.assertEqual(result["reasoning"], "All metrics check out")

    def test_parse_all_verdicts(self):
        for v in ("APPROVED", "CAUTIOUS", "SUSPICIOUS", "REJECTED"):
            raw = f"VERDICT: {v}\nCONFIDENCE: 0.5\nREASONING: test"
            result = _parse_ollama_response(raw)
            self.assertEqual(result["verdict"], v)

    def test_parse_invalid_verdict_raises(self):
        raw = "VERDICT: MAYBE\nCONFIDENCE: 0.5\nREASONING: test"
        with self.assertRaises(ValueError):
            _parse_ollama_response(raw)

    def test_parse_missing_confidence_raises(self):
        raw = "VERDICT: APPROVED\nREASONING: test"
        with self.assertRaises(ValueError):
            _parse_ollama_response(raw)

    def test_parse_out_of_range_confidence_raises(self):
        raw = "VERDICT: APPROVED\nCONFIDENCE: 1.5\nREASONING: test"
        with self.assertRaises(ValueError):
            _parse_ollama_response(raw)


# -- Ollama failover tests -------------------------------------------------

class TestOllamaFailover(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        init_db(self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    @patch("sophia_core.requests.post")
    def test_ollama_success(self, mock_post):
        """When first Ollama endpoint works, use it."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": "VERDICT: APPROVED\nCONFIDENCE: 0.95\nREASONING: All good"
        }
        mock_post.return_value = mock_resp

        inspector = SophiaCoreInspector(
            db_path=self.db_path,
            ollama_endpoints=["http://fake:11434"],
        )
        result = inspector.inspect("miner_ok", _good_fingerprint())
        self.assertEqual(result["verdict"], "APPROVED")
        self.assertIn("elyan-sophia", result["model_used"])
        mock_post.assert_called_once()

    @patch("sophia_core.requests.post")
    def test_ollama_failover_to_second(self, mock_post):
        """First endpoint fails, second works."""
        fail_resp = MagicMock()
        fail_resp.raise_for_status.side_effect = Exception("connection refused")

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "response": "VERDICT: CAUTIOUS\nCONFIDENCE: 0.6\nREASONING: hmm"
        }

        mock_post.side_effect = [Exception("refused"), ok_resp]

        inspector = SophiaCoreInspector(
            db_path=self.db_path,
            ollama_endpoints=["http://bad:11434", "http://good:11434"],
        )
        result = inspector.inspect("miner_f", _good_fingerprint())
        self.assertEqual(result["verdict"], "CAUTIOUS")
        self.assertEqual(mock_post.call_count, 2)

    @patch("sophia_core.requests.post")
    def test_ollama_all_fail_uses_fallback(self, mock_post):
        """All Ollama endpoints fail => rule-based fallback."""
        mock_post.side_effect = Exception("down")

        inspector = SophiaCoreInspector(
            db_path=self.db_path,
            ollama_endpoints=["http://a:11434", "http://b:11434"],
        )
        result = inspector.inspect("miner_fb", _good_fingerprint())
        self.assertEqual(result["model_used"], "rule-based-fallback-v1")
        self.assertIn(result["verdict"], VERDICTS)

    @patch("sophia_core.requests.post")
    def test_cautious_queued_for_review(self, mock_post):
        """CAUTIOUS verdicts are auto-queued for human review."""
        mock_post.side_effect = Exception("down")

        inspector = SophiaCoreInspector(
            db_path=self.db_path,
            ollama_endpoints=[],
        )
        result = inspector.inspect("miner_c", _cautious_fingerprint())
        self.assertEqual(result["verdict"], "CAUTIOUS")
        self.assertTrue(result.get("queued_for_review", False))

    @patch("sophia_core.requests.post")
    def test_suspicious_queued_for_review(self, mock_post):
        """SUSPICIOUS verdicts are auto-queued for human review."""
        mock_post.side_effect = Exception("down")

        inspector = SophiaCoreInspector(
            db_path=self.db_path,
            ollama_endpoints=[],
        )
        result = inspector.inspect("miner_s", _suspicious_fingerprint())
        self.assertEqual(result["verdict"], "SUSPICIOUS")
        self.assertTrue(result.get("queued_for_review", False))


# -- Explorer emoji mapping -------------------------------------------------

class TestEmojiMapping(unittest.TestCase):
    def test_all_verdicts_have_emoji(self):
        for verdict, emoji in VERDICTS.items():
            self.assertTrue(len(emoji) > 0)
            self.assertIn(verdict, ("APPROVED", "CAUTIOUS", "SUSPICIOUS", "REJECTED"))

    def test_approved_emoji(self):
        self.assertEqual(VERDICTS["APPROVED"], "\u2728")

    def test_cautious_emoji(self):
        self.assertEqual(VERDICTS["CAUTIOUS"], "\u26a0\ufe0f")

    def test_suspicious_emoji(self):
        self.assertEqual(VERDICTS["SUSPICIOUS"], "\U0001f50d")

    def test_rejected_emoji(self):
        self.assertEqual(VERDICTS["REJECTED"], "\u274c")


# -- Flask API tests -------------------------------------------------------

class TestSophiaAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        init_db(self.db_path)

        # Patch DB_PATH everywhere so get_connection() uses test DB
        import sophia_db
        import sophia_api
        self._orig_db_path = sophia_db.DB_PATH
        sophia_db.DB_PATH = self.db_path

        from sophia_api import app, inspector
        inspector.db_path = self.db_path
        inspector.ollama_endpoints = []  # force rule-based
        app._db_initialized = True
        self.client = app.test_client()

    def tearDown(self):
        import sophia_db
        sophia_db.DB_PATH = self._orig_db_path
        os.unlink(self.db_path)

    def test_inspect_endpoint(self):
        resp = self.client.post("/sophia/inspect", json={
            "miner_id": "test_miner",
            "fingerprint": _good_fingerprint(),
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn(data["verdict"], VERDICTS)
        self.assertIn("confidence", data)
        self.assertIn("emoji", data)

    def test_inspect_missing_miner_id(self):
        resp = self.client.post("/sophia/inspect", json={
            "fingerprint": _good_fingerprint(),
        })
        self.assertEqual(resp.status_code, 400)

    def test_inspect_missing_fingerprint(self):
        resp = self.client.post("/sophia/inspect", json={
            "miner_id": "test",
        })
        self.assertEqual(resp.status_code, 400)

    def test_status_endpoint(self):
        # First, create an inspection
        self.client.post("/sophia/inspect", json={
            "miner_id": "status_miner",
            "fingerprint": _good_fingerprint(),
        })
        resp = self.client.get("/sophia/status/status_miner")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("latest", data)
        self.assertIn("history", data)

    def test_status_not_found(self):
        resp = self.client.get("/sophia/status/nobody")
        self.assertEqual(resp.status_code, 404)

    def test_history_endpoint(self):
        self.client.post("/sophia/inspect", json={
            "miner_id": "hist_m",
            "fingerprint": _good_fingerprint(),
        })
        resp = self.client.get("/sophia/history?page=1&per_page=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("inspections", data)
        self.assertIn("total", data)

    def test_history_rejects_invalid_pagination(self):
        resp = self.client.get("/sophia/history?page=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "page must be an integer")

        resp = self.client.get("/sophia/history?per_page=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "per_page must be an integer")

    def test_history_rejects_non_positive_pagination(self):
        resp = self.client.get("/sophia/history?page=0")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "page must be positive")

        resp = self.client.get("/sophia/history?per_page=0")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "per_page must be positive")

    def test_history_caps_per_page(self):
        for idx in range(3):
            self.client.post("/sophia/inspect", json={
                "miner_id": f"hist_cap_{idx}",
                "fingerprint": _good_fingerprint(),
            })

        resp = self.client.get("/sophia/history?page=1&per_page=500")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["per_page"], 100)

    def test_dashboard_endpoint(self):
        self.client.post("/sophia/inspect", json={
            "miner_id": "dash_m",
            "fingerprint": _suspicious_fingerprint(),
        })
        resp = self.client.get("/sophia/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("total_inspections", data)
        self.assertIn("spot_check_queue", data)

    def test_explorer_endpoint_with_record(self):
        self.client.post("/sophia/inspect", json={
            "miner_id": "exp_m",
            "fingerprint": _good_fingerprint(),
        })
        resp = self.client.get("/sophia/explorer/exp_m")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("emoji", data)
        self.assertIn("verdict", data)

    def test_explorer_endpoint_unknown_miner(self):
        resp = self.client.get("/sophia/explorer/unknown_m")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["verdict"], "UNKNOWN")
        self.assertEqual(data["emoji"], "\u2753")


# -- Scheduler tests -------------------------------------------------------

class TestSophiaScheduler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        init_db(self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_batch_inspects_all_miners(self):
        from sophia_scheduler import SophiaScheduler

        # Seed some miners
        conn = get_connection(self.db_path)
        store_inspection(conn, "m1", "APPROVED", 0.9, "", "rb", {"a": 1})
        store_inspection(conn, "m2", "APPROVED", 0.8, "", "rb", {"b": 2})
        conn.close()

        fetcher = lambda mid: _good_fingerprint()

        sched = SophiaScheduler(
            db_path=self.db_path,
            ollama_endpoints=[],  # force rule-based
            fingerprint_fetcher=fetcher,
        )
        results = sched.run_batch()
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r["model_used"], "rule-based-fallback-v1")

    def test_anomaly_reinspection_low_confidence(self):
        from sophia_scheduler import SophiaScheduler

        conn = get_connection(self.db_path)
        store_inspection(conn, "m_bad", "SUSPICIOUS", 0.3, "", "rb", {})
        store_inspection(conn, "m_good", "APPROVED", 0.9, "", "rb", {})
        conn.close()

        fetcher = lambda mid: _good_fingerprint()

        sched = SophiaScheduler(
            db_path=self.db_path,
            ollama_endpoints=[],
            fingerprint_fetcher=fetcher,
        )
        results = sched.run_anomaly_reinspection()
        # Only m_bad should be re-inspected (confidence < 0.5)
        miner_ids = [r["miner_id"] for r in results]
        self.assertIn("m_bad", miner_ids)
        self.assertNotIn("m_good", miner_ids)

    def test_anomaly_reinspection_verdict_changed(self):
        from sophia_scheduler import SophiaScheduler

        conn = get_connection(self.db_path)
        store_inspection(conn, "m_flip", "APPROVED", 0.9, "", "rb", {"v": 1})
        time.sleep(0.01)
        store_inspection(conn, "m_flip", "REJECTED", 0.8, "", "rb", {"v": 2})
        conn.close()

        fetcher = lambda mid: _good_fingerprint()

        sched = SophiaScheduler(
            db_path=self.db_path,
            ollama_endpoints=[],
            fingerprint_fetcher=fetcher,
        )
        results = sched.run_anomaly_reinspection()
        miner_ids = [r["miner_id"] for r in results]
        self.assertIn("m_flip", miner_ids)

    def test_scheduler_start_stop(self):
        from sophia_scheduler import SophiaScheduler

        sched = SophiaScheduler(
            db_path=self.db_path,
            interval_hours=24,
            ollama_endpoints=[],
            fingerprint_fetcher=lambda mid: {},
        )
        # Don't actually start the loop -- just verify start/stop lifecycle
        self.assertFalse(sched.running)
        sched.start()
        self.assertTrue(sched.running)
        sched.stop()
        # Give thread time to finish
        time.sleep(0.1)
        self.assertFalse(sched.running)

    def test_batch_no_miners(self):
        from sophia_scheduler import SophiaScheduler

        sched = SophiaScheduler(
            db_path=self.db_path,
            ollama_endpoints=[],
            fingerprint_fetcher=lambda mid: {},
        )
        results = sched.run_batch()
        self.assertEqual(results, [])

    def test_failover_chain_default(self):
        from sophia_scheduler import SophiaScheduler
        from sophia_core import OLLAMA_FAILOVER_CHAIN

        sched = SophiaScheduler(db_path=self.db_path)
        self.assertEqual(
            sched.inspector.ollama_endpoints,
            OLLAMA_FAILOVER_CHAIN,
        )


if __name__ == "__main__":
    unittest.main()
