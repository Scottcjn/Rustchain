"""Tests for GPU Render Protocol (Bounty #30)."""
import os
import sys
import tempfile
import unittest
from unittest import mock

from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import node.gpu_render_protocol as gpu_render_protocol
from node.gpu_render_protocol import GPURenderProtocol


class TestGPURenderProtocol(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "test_gpu.db")
        self.proto = GPURenderProtocol(db_path=self.db)

    def test_attest_gpu(self):
        result = self.proto.attest_gpu("miner-1", {
            "gpu_model": "RTX 4090",
            "vram_gb": 24.0,
            "device_arch": "nvidia_gpu",
            "cuda_version": "12.4",
            "benchmark_score": 95.0,
            "price_render_minute": 0.5,
            "price_llm_1k_tokens": 0.1,
            "supports_llm": 1,
            "llm_models": ["llama-70b", "mistral-7b"],
        })
        self.assertEqual(result["status"], "attested")
        self.assertEqual(result["device_arch"], "nvidia_gpu")
        self.assertIn("fingerprint", result)

    def test_attest_invalid_arch(self):
        result = self.proto.attest_gpu("miner-2", {
            "gpu_model": "GTX 1080",
            "vram_gb": 8.0,
            "device_arch": "invalid",
        })
        self.assertIn("error", result)

    def test_list_nodes(self):
        self.proto.attest_gpu("miner-1", {
            "gpu_model": "RTX 4090", "vram_gb": 24, "device_arch": "nvidia_gpu",
            "supports_llm": 1, "benchmark_score": 95,
        })
        self.proto.attest_gpu("miner-2", {
            "gpu_model": "M2 Ultra", "vram_gb": 192, "device_arch": "apple_gpu",
            "supports_llm": 1, "benchmark_score": 80,
        })
        all_nodes = self.proto.list_gpu_nodes()
        self.assertEqual(len(all_nodes), 2)

        nvidia = self.proto.list_gpu_nodes(device_arch="nvidia_gpu")
        self.assertEqual(len(nvidia), 1)
        self.assertEqual(nvidia[0]["gpu_model"], "RTX 4090")

    def test_escrow_lifecycle(self):
        # Create
        result = self.proto.create_escrow("render", "wallet-a", "wallet-b", 10.0)
        self.assertEqual(result["status"], "locked")
        job_id = result["job_id"]
        escrow_secret = result["escrow_secret"]

        # Check
        status = self.proto.get_escrow(job_id)
        self.assertEqual(status["status"], "locked")
        self.assertEqual(status["amount_rtc"], 10.0)

        # Bare job_id should not be enough to release funds
        bare_release = self.proto.release_escrow(job_id)
        self.assertIn("error", bare_release)
        self.assertEqual(self.proto.get_escrow(job_id)["status"], "locked")

        # Provider cannot release payer escrow
        wrong_actor = self.proto.release_escrow(
            job_id, actor_wallet="wallet-b", escrow_secret=escrow_secret
        )
        self.assertIn("error", wrong_actor)
        self.assertEqual(self.proto.get_escrow(job_id)["status"], "locked")

        # Payer can release with the escrow secret
        release = self.proto.release_escrow(
            job_id, actor_wallet="wallet-a", escrow_secret=escrow_secret
        )
        self.assertEqual(release["status"], "released")
        self.assertEqual(release["amount_rtc"], 10.0)

        # Double release fails
        double = self.proto.release_escrow(
            job_id, actor_wallet="wallet-a", escrow_secret=escrow_secret
        )
        self.assertIn("error", double)

    def test_escrow_refund(self):
        result = self.proto.create_escrow("tts", "wallet-a", "wallet-b", 5.0)
        job_id = result["job_id"]
        escrow_secret = result["escrow_secret"]

        bare_refund = self.proto.refund_escrow(job_id)
        self.assertIn("error", bare_refund)
        self.assertEqual(self.proto.get_escrow(job_id)["status"], "locked")

        wrong_actor = self.proto.refund_escrow(
            job_id, actor_wallet="wallet-a", escrow_secret=escrow_secret
        )
        self.assertIn("error", wrong_actor)
        self.assertEqual(self.proto.get_escrow(job_id)["status"], "locked")

        refund = self.proto.refund_escrow(
            job_id, actor_wallet="wallet-b", escrow_secret=escrow_secret
        )
        self.assertEqual(refund["status"], "refunded")

    def test_escrow_invalid_type(self):
        result = self.proto.create_escrow("invalid", "a", "b", 1.0)
        self.assertIn("error", result)

    def test_escrow_negative_amount(self):
        result = self.proto.create_escrow("llm", "a", "b", -1.0)
        self.assertIn("error", result)

    def test_escrow_same_wallet(self):
        result = self.proto.create_escrow("render", "same", "same", 1.0)
        self.assertIn("error", result)

    def test_pricing_oracle(self):
        for i, price in enumerate([0.5, 0.3, 0.7]):
            self.proto.attest_gpu(f"miner-{i}", {
                "gpu_model": f"GPU-{i}", "vram_gb": 24, "device_arch": "nvidia_gpu",
                "price_render_minute": price,
            })
        rates = self.proto.get_fair_market_rates("render")
        self.assertIn("render", rates["rates"])
        r = rates["rates"]["render"]
        self.assertEqual(r["providers"], 3)
        self.assertAlmostEqual(r["avg"], 0.5, places=2)
        self.assertAlmostEqual(r["min"], 0.3)
        self.assertAlmostEqual(r["max"], 0.7)

    def test_price_manipulation_detection(self):
        self.proto.attest_gpu("miner-1", {
            "gpu_model": "RTX 4090", "vram_gb": 24, "device_arch": "nvidia_gpu",
            "price_render_minute": 0.5,
        })
        # Normal price
        check = self.proto.detect_price_manipulation("render", 0.6)
        self.assertFalse(check["manipulated"])

        # Too high
        check = self.proto.detect_price_manipulation("render", 10.0)
        self.assertTrue(check["manipulated"])
        self.assertEqual(check["reason"], "price_too_high")

    def test_voice_escrow_types(self):
        for jt in ("tts", "stt"):
            result = self.proto.create_escrow(jt, "a", "b", 2.0)
            self.assertEqual(result["status"], "locked")
            self.assertEqual(result["job_type"], jt)

    def test_llm_escrow(self):
        result = self.proto.create_escrow("llm", "a", "b", 3.0,
                                          metadata={"model": "llama-70b", "tokens": 5000})
        self.assertEqual(result["status"], "locked")
        status = self.proto.get_escrow(result["job_id"])
        self.assertEqual(status["metadata"]["model"], "llama-70b")


class TestGPURenderProtocolRoutes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "test_gpu_routes.db")
        self.proto = GPURenderProtocol(db_path=self.db)
        app = Flask(__name__)
        with mock.patch.object(gpu_render_protocol, "GPURenderProtocol", return_value=self.proto):
            gpu_render_protocol.register_routes(app)
        self.client = app.test_client()

    def test_release_route_requires_participant_and_secret(self):
        create = self.client.post(
            "/render/escrow",
            json={
                "from_wallet": "wallet-a",
                "to_wallet": "wallet-b",
                "amount_rtc": 7.5,
            },
        )
        self.assertEqual(create.status_code, 201)
        payload = create.get_json()
        job_id = payload["job_id"]
        escrow_secret = payload["escrow_secret"]

        bare_release = self.client.post("/render/release", json={"job_id": job_id})
        self.assertEqual(bare_release.status_code, 400)
        self.assertEqual(self.proto.get_escrow(job_id)["status"], "locked")

        release = self.client.post(
            "/render/release",
            json={
                "job_id": job_id,
                "actor_wallet": "wallet-a",
                "escrow_secret": escrow_secret,
            },
        )
        self.assertEqual(release.status_code, 200)
        self.assertEqual(release.get_json()["status"], "released")


if __name__ == "__main__":
    unittest.main()
