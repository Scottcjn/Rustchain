import unittest
from unittest.mock import patch

import pow_proof


class TestPowProofKaspa(unittest.TestCase):
    @patch('pow_proof.verify_kaspa_node_rpc')
    def test_kaspa_node_rpc_success(self, mock_verify):
        mock_verify.return_value = (True, {"isSynced": True, "peers": 8}, "")
        ok, res, err = pow_proof.validate_pow_proof({
            "coin": "kaspa",
            "proof_type": "node_rpc",
            "evidence": {"endpoint": "http://127.0.0.1:16110"}
        }, miner_id="k1")
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertTrue(res.get("verified"))

    @patch('pow_proof.verify_kaspa_pool')
    def test_kaspa_pool_failure(self, mock_verify):
        mock_verify.return_value = (False, {}, "kaspa_pool_no_hashrate")
        ok, _, err = pow_proof.validate_pow_proof({
            "coin": "kaspa",
            "proof_type": "pool",
            "evidence": {"pool_api_url": "https://example.invalid"}
        }, miner_id="k2")
        self.assertFalse(ok)
        self.assertEqual(err, "kaspa_pool_no_hashrate")


if __name__ == '__main__':
    unittest.main()
