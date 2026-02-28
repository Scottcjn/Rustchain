import unittest
from unittest.mock import patch

import pow_proof


class TestPowProofMonero(unittest.TestCase):
    @patch('pow_proof.verify_monero_node_rpc')
    def test_monero_node_rpc_success(self, mock_verify):
        mock_verify.return_value = (True, {"synchronized": True, "height": 12345}, "")
        ok, res, err = pow_proof.validate_pow_proof({
            "coin": "monero",
            "proof_type": "node_rpc",
            "evidence": {"endpoint": "http://127.0.0.1:18081/json_rpc"}
        }, miner_id="xmr1")
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertTrue(res.get("verified"))

    @patch('pow_proof.verify_monero_pool')
    def test_monero_pool_failure(self, mock_verify):
        mock_verify.return_value = (False, {}, "monero_pool_no_hashrate")
        ok, _, err = pow_proof.validate_pow_proof({
            "coin": "monero",
            "proof_type": "pool",
            "evidence": {"pool_api_url": "https://example.invalid"}
        }, miner_id="xmr2")
        self.assertFalse(ok)
        self.assertEqual(err, "monero_pool_no_hashrate")


if __name__ == '__main__':
    unittest.main()
