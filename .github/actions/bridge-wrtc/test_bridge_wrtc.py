import unittest
from unittest.mock import patch
import bridge_wrtc


class TestBridgeWrtc(unittest.TestCase):
    @patch("bridge_wrtc.run_cmd")
    def test_transfer(self, mock_run):
        mock_run.return_value = "Transfer successful"
        bridge_wrtc.transfer("from_wallet", "to_wallet", 10.0)
        mock_run.assert_called_once()
        called_cmd = mock_run.call_args[0][0]
        self.assertIn("transfer", called_cmd)
        self.assertIn("--from", called_cmd)
        self.assertIn("--to", called_cmd)
        self.assertIn("--amount", called_cmd)

    @patch("bridge_wrtc.run_cmd")
    def test_bridge_to_wrtc(self, mock_run):
        mock_run.return_value = "Bridge successful"
        bridge_wrtc.bridge_to_wrtc("wallet", 70.0, "solana_wallet")
        mock_run.assert_called_once()
        called_cmd = mock_run.call_args[0][0]
        self.assertIn("bridge", called_cmd)
        self.assertIn("--destination", called_cmd)


if __name__ == "__main__":
    unittest.main()
