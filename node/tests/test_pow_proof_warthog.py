import unittest
from unittest.mock import patch

import pow_proof


class TestPowProofWarthog(unittest.TestCase):
    @patch('pow_proof.verify_warthog_node_rpc')
    def test_warthog_node_rpc_success(self, mock_verify):
        mock_verify.return_value = (True, {"height": 9999, "hash": "abc"}, "")
        ok, res, err = pow_proof.validate_pow_proof({
            "coin": "warthog",
            "proof_type": "node_rpc",
            "evidence": {"endpoint": "http://127.0.0.1:3000/chain/head"}
        }, miner_id="m1")
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertTrue(res.get("verified"))

    @patch('pow_proof.verify_warthog_pool')
    def test_warthog_pool_failure(self, mock_verify):
        mock_verify.return_value = (False, {}, "warthog_pool_no_hashrate")
        ok, _, err = pow_proof.validate_pow_proof({
            "coin": "warthog",
            "proof_type": "pool",
            "evidence": {"pool_api_url": "https://example.invalid"}
        }, miner_id="m2")
        self.assertFalse(ok)
        self.assertEqual(err, "warthog_pool_no_hashrate")


if __name__ == '__main__':
    unittest.main()
