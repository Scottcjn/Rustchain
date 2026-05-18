"""Tests for GPU Render Protocol (Bounty #30)."""
import os
import sys
import tempfile
import unittest

import pytest
from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from node import gpu_render_protocol
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

        # Release
        release = self.proto.release_escrow(job_id, "wallet-a", escrow_secret)
        self.assertEqual(release["status"], "released")
        self.assertEqual(release["amount_rtc"], 10.0)

        # Double release fails
        double = self.proto.release_escrow(job_id, "wallet-a", escrow_secret)
        self.assertIn("error", double)

    def test_escrow_refund(self):
        result = self.proto.create_escrow("tts", "wallet-a", "wallet-b", 5.0)
        job_id = result["job_id"]

        refund = self.proto.refund_escrow(job_id, "wallet-b", result["escrow_secret"])
        self.assertEqual(refund["status"], "refunded")

    def test_release_requires_payer_and_secret(self):
        result = self.proto.create_escrow("render", "wallet-a", "wallet-b", 10.0)
        job_id = result["job_id"]

        missing = self.proto.release_escrow(job_id)
        self.assertIn("error", missing)

        wrong_actor = self.proto.release_escrow(job_id, "wallet-b", result["escrow_secret"])
        self.assertIn("error", wrong_actor)

        wrong_secret = self.proto.release_escrow(job_id, "wallet-a", "wrong-secret")
        self.assertIn("error", wrong_secret)

        status = self.proto.get_escrow(job_id)
        self.assertEqual(status["status"], "locked")

    def test_refund_requires_provider_and_secret(self):
        result = self.proto.create_escrow("tts", "wallet-a", "wallet-b", 5.0)
        job_id = result["job_id"]

        wrong_actor = self.proto.refund_escrow(job_id, "wallet-a", result["escrow_secret"])
        self.assertIn("error", wrong_actor)

        outsider = self.proto.refund_escrow(job_id, "wallet-c", result["escrow_secret"])
        self.assertIn("error", outsider)

        wrong_secret = self.proto.refund_escrow(job_id, "wallet-b", "wrong-secret")
        self.assertIn("error", wrong_secret)

        status = self.proto.get_escrow(job_id)
        self.assertEqual(status["status"], "locked")

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


def _route_client(tmp_path, monkeypatch):
    proto = GPURenderProtocol(db_path=str(tmp_path / "gpu_routes.db"))
    monkeypatch.setattr(gpu_render_protocol, "GPURenderProtocol", lambda: proto)
    app = Flask(__name__)
    app.config["TESTING"] = True
    gpu_render_protocol.register_routes(app)
    return app.test_client()


@pytest.mark.parametrize(
    "path",
    [
        "/gpu/attest",
        "/render/escrow",
        "/voice/escrow",
        "/llm/escrow",
        "/render/release",
        "/voice/release",
        "/llm/release",
        "/render/refund",
        "/render/pricing/check",
    ],
)
def test_gpu_protocol_routes_reject_non_object_json(tmp_path, monkeypatch, path):
    client = _route_client(tmp_path, monkeypatch)

    response = client.post(path, json=[{"unexpected": "array"}])

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


def test_gpu_protocol_escrow_rejects_structured_wallet(tmp_path, monkeypatch):
    client = _route_client(tmp_path, monkeypatch)

    response = client.post(
        "/render/escrow",
        json={
            "job_type": "render",
            "from_wallet": {"wallet": "payer"},
            "to_wallet": "provider",
            "amount_rtc": 1,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "from_wallet must be a string"}


def test_gpu_protocol_pricing_check_rejects_structured_price(tmp_path, monkeypatch):
    client = _route_client(tmp_path, monkeypatch)

    response = client.post(
        "/render/pricing/check",
        json={"job_type": "render", "price": ["not", "numeric"]},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "price must be a finite number"}


if __name__ == "__main__":
    unittest.main()
