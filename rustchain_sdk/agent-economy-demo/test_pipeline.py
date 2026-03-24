"""
Tests for the autonomous agent pipeline.
Tests the Agent class and pipeline logic with mocked RustChain API.
"""
import json
import os
import unittest
from unittest.mock import patch, MagicMock

from autonomous_pipeline import Agent, get_marketplace_stats, NODE_URL


def mock_response(data, ok=True, status_code=200):
    r = MagicMock()
    r.ok = ok
    r.status_code = status_code
    r.json.return_value = data
    r.text = json.dumps(data)
    return r


class TestAgent(unittest.TestCase):

    def setUp(self):
        self.agent = Agent(name="TestAgent", wallet="test-wallet", role="testing")

    @patch("autonomous_pipeline.requests.get")
    def test_get_balance(self, mock_get):
        mock_get.return_value = mock_response({"amount_rtc": 100.5, "miner_id": "test-wallet"})
        bal = self.agent.get_balance()
        self.assertEqual(bal, 100.5)
        mock_get.assert_called_once()

    @patch("autonomous_pipeline.requests.get")
    def test_get_balance_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        bal = self.agent.get_balance()
        self.assertEqual(bal, 0)

    @patch("autonomous_pipeline.requests.post")
    def test_post_job(self, mock_post):
        mock_post.return_value = mock_response({
            "ok": True,
            "job_id": "job_test123",
            "escrow_total_rtc": 5.25,
            "status": "open"
        })
        job_id = self.agent.post_job(
            title="Test job title here",
            description="A test job with enough description length for validation",
            category="code",
            reward_rtc=5.0
        )
        self.assertEqual(job_id, "job_test123")

    @patch("autonomous_pipeline.requests.post")
    def test_post_job_insufficient_balance(self, mock_post):
        mock_post.return_value = mock_response({
            "error": "Insufficient balance for escrow"
        }, ok=False, status_code=400)
        job_id = self.agent.post_job(
            title="Test job title here",
            description="A test job with enough description length",
            category="code",
            reward_rtc=5000.0
        )
        self.assertIsNone(job_id)

    @patch("autonomous_pipeline.requests.post")
    def test_claim_job(self, mock_post):
        mock_post.return_value = mock_response({
            "ok": True,
            "job_id": "job_abc",
            "status": "claimed",
            "reward_rtc": 10.0
        })
        result = self.agent.claim_job("job_abc")
        self.assertTrue(result)

    @patch("autonomous_pipeline.requests.post")
    def test_claim_already_claimed(self, mock_post):
        mock_post.return_value = mock_response({
            "error": "Job was claimed by another worker"
        }, ok=False, status_code=409)
        result = self.agent.claim_job("job_abc")
        self.assertFalse(result)

    @patch("autonomous_pipeline.requests.post")
    def test_deliver_job(self, mock_post):
        mock_post.return_value = mock_response({
            "ok": True,
            "job_id": "job_abc",
            "status": "delivered"
        })
        result = self.agent.deliver_job(
            "job_abc",
            deliverable_url="https://example.com/result",
            summary="Completed the task"
        )
        self.assertTrue(result)

    @patch("autonomous_pipeline.requests.post")
    def test_accept_delivery(self, mock_post):
        mock_post.return_value = mock_response({
            "ok": True,
            "job_id": "job_abc",
            "status": "completed",
            "reward_paid_rtc": 10.0,
            "platform_fee_rtc": 0.5
        })
        result = self.agent.accept_delivery("job_abc", rating=5)
        self.assertTrue(result)

    @patch("autonomous_pipeline.requests.get")
    def test_get_reputation(self, mock_get):
        mock_get.return_value = mock_response({
            "ok": True,
            "reputation": {
                "trust_score": 85,
                "trust_level": "trusted",
                "total_rtc_earned": 50.0,
                "avg_rating": 4.8
            }
        })
        rep = self.agent.get_reputation()
        self.assertEqual(rep["trust_score"], 85)
        self.assertEqual(rep["trust_level"], "trusted")

    @patch("autonomous_pipeline.requests.get")
    def test_get_job_detail(self, mock_get):
        mock_get.return_value = mock_response({
            "ok": True,
            "job": {
                "job_id": "job_abc",
                "title": "Test",
                "status": "completed",
                "activity_log": [
                    {"action": "posted", "actor_wallet": "poster1", "created_at": 1000}
                ]
            }
        })
        job = self.agent.get_job_detail("job_abc")
        self.assertEqual(job["job_id"], "job_abc")
        self.assertEqual(len(job["activity_log"]), 1)


class TestMarketplaceStats(unittest.TestCase):

    @patch("autonomous_pipeline.requests.get")
    def test_get_stats(self, mock_get):
        mock_get.return_value = mock_response({
            "ok": True,
            "stats": {
                "total_jobs": 100,
                "completed_jobs": 80,
                "total_rtc_volume": 500.0
            }
        })
        stats = get_marketplace_stats()
        self.assertEqual(stats["total_jobs"], 100)
        self.assertEqual(stats["total_rtc_volume"], 500.0)


class TestPipelineFlow(unittest.TestCase):
    """Test the full pipeline with mocked API calls."""

    @patch("autonomous_pipeline.requests.post")
    @patch("autonomous_pipeline.requests.get")
    def test_full_pipeline_mock(self, mock_get, mock_post):
        """Verify the pipeline calls the right endpoints in order."""
        call_log = []

        def track_post(url, **kwargs):
            call_log.append(("POST", url))
            if "/agent/jobs/" in url and "/claim" in url:
                return mock_response({"ok": True, "reward_rtc": 2.0, "status": "claimed"})
            elif "/agent/jobs/" in url and "/deliver" in url:
                return mock_response({"ok": True, "status": "delivered"})
            elif "/agent/jobs/" in url and "/accept" in url:
                return mock_response({"ok": True, "reward_paid_rtc": 2.0,
                                      "platform_fee_rtc": 0.1, "status": "completed"})
            elif "/agent/jobs" in url:
                return mock_response({"ok": True, "job_id": f"job_mock_{len(call_log)}",
                                      "escrow_total_rtc": 2.1, "status": "open"})
            return mock_response({"error": "unknown"}, ok=False)

        def track_get(url, **kwargs):
            call_log.append(("GET", url))
            if "/balance" in url:
                return mock_response({"amount_rtc": 100.0})
            elif "/reputation" in url:
                return mock_response({"ok": True, "reputation": {
                    "trust_score": 80, "trust_level": "trusted",
                    "total_rtc_earned": 10.0, "avg_rating": 5.0
                }})
            elif "/agent/stats" in url:
                return mock_response({"ok": True, "stats": {
                    "total_jobs": 50, "completed_jobs": 40,
                    "total_rtc_volume": 300.0
                }})
            elif "/agent/jobs/" in url:
                return mock_response({"ok": True, "job": {
                    "job_id": "job_mock", "title": "Test",
                    "poster_wallet": "a", "worker_wallet": "b",
                    "reward_rtc": 2.0, "status": "completed",
                    "category": "research",
                    "activity_log": []
                }})
            return mock_response({})

        mock_post.side_effect = track_post
        mock_get.side_effect = track_get

        from autonomous_pipeline import run_pipeline
        result = run_pipeline()

        # Should have 3 completed jobs
        self.assertIsInstance(result, dict)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["jobs"]), 3)

        # Verify we called post -> claim -> deliver -> accept 3 times
        post_calls = [c for c in call_log if c[0] == "POST"]
        # 3 posts + 3 claims + 3 delivers + 3 accepts = 12 POST calls
        self.assertEqual(len(post_calls), 12)


if __name__ == "__main__":
    unittest.main()
