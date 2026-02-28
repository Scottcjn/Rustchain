import unittest
from unittest.mock import patch

import pow_proof


class TestPowProofValidation(unittest.TestCase):
    @patch('pow_proof.verify_ergo_node_rpc')
    def test_ergo_node_rpc_success(self, mock_verify):
        mock_verify.return_value = (True, {"height": 123, "isMining": True}, "")
        ok, res, err = pow_proof.validate_pow_proof({
            "coin": "ergo",
            "proof_type": "node_rpc",
            "evidence": {"endpoint": "http://127.0.0.1:9053/info"}
        }, miner_id="m1")
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertTrue(res.get("verified"))

    @patch('pow_proof.verify_ergo_pool')
    def test_ergo_pool_failure(self, mock_verify):
        mock_verify.return_value = (False, {}, "ergo_pool_no_hashrate")
        ok, res, err = pow_proof.validate_pow_proof({
            "coin": "ergo",
            "proof_type": "pool",
            "evidence": {"pool_api_url": "https://example.com/api"}
        }, miner_id="m2")
        self.assertFalse(ok)
        self.assertEqual(err, "ergo_pool_no_hashrate")

    def test_reject_unsupported_coin(self):
        ok, _, err = pow_proof.validate_pow_proof({"coin": "monero", "proof_type": "node_rpc"}, miner_id="m3")
        self.assertFalse(ok)
        self.assertIn("unsupported_coin", err)

    def test_reject_missing_fields(self):
        ok, _, err = pow_proof.validate_pow_proof({"coin": "ergo"}, miner_id="m4")
        self.assertFalse(ok)
        self.assertEqual(err, "missing_proof_type")


if __name__ == '__main__':
    unittest.main()
