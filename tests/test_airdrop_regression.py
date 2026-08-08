import unittest
import tempfile
import os
from unittest.mock import patch, Mock
import sys

# Add node directory to path so we can import airdrop_v2
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../node')))

from airdrop_v2 import AirdropV2

class TestAirdropClaimRegression(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.airdrop = AirdropV2(db_path=self.temp_db.name)

    def tearDown(self):
        os.unlink(self.temp_db.name)

    def test_claim_invalid_username(self):
        success, msg, claim = self.airdrop.claim_airdrop(
            github_username="!invalid!",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            skip_antisybil=True
        )
        self.assertFalse(success)
        self.assertIn("Invalid GitHub username", msg)

    def test_claim_invalid_chain(self):
        success, msg, claim = self.airdrop.claim_airdrop(
            github_username="validuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="invalidchain",
            tier="contributor",
            skip_antisybil=True
        )
        self.assertFalse(success)
        self.assertIn("exhausted", msg)

    def test_claim_valid_solana(self):
        success, msg, claim = self.airdrop.claim_airdrop(
            github_username="validuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="solana",
            tier="contributor",
            skip_antisybil=True
        )
        self.assertTrue(success)

    def test_claim_valid_base(self):
        success, msg, claim = self.airdrop.claim_airdrop(
            github_username="validuser2",
            wallet_address="RTC1234567890123456789012345678901234567891",
            chain="base",
            tier="builder",
            skip_antisybil=True
        )
        self.assertTrue(success)

    def test_claim_duplicate_github(self):
        self.airdrop.claim_airdrop(
            github_username="dupuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            skip_antisybil=True
        )
        success, msg, claim = self.airdrop.claim_airdrop(
            github_username="dupuser",
            wallet_address="RTC0987654321098765432109876543210987654321",
            chain="base",
            tier="contributor",
            skip_antisybil=True
        )
        self.assertFalse(success)
        self.assertIn("exists for this GitHub account or wallet", msg)

    def test_claim_duplicate_wallet(self):
        self.airdrop.claim_airdrop(
            github_username="user1",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            skip_antisybil=True
        )
        success, msg, claim = self.airdrop.claim_airdrop(
            github_username="user2",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            skip_antisybil=True
        )
        self.assertFalse(success)
        self.assertIn("exists for this GitHub account or wallet", msg)

    def test_claim_invalid_tier(self):
        success, msg, claim = self.airdrop.claim_airdrop(
            github_username="validuser3",
            wallet_address="RTC1234567890123456789012345678901234567892",
            chain="base",
            tier="superhacker",
            skip_antisybil=True
        )
        self.assertFalse(success)
        self.assertIn("Invalid tier", msg)

    @patch("requests.get")
    def test_claim_with_valid_github_token(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "tokenuser"}
        mock_get.return_value = mock_resp

        success, msg, claim = self.airdrop.claim_airdrop(
            github_username="tokenuser",
            wallet_address="RTC1234567890123456789012345678901234567893",
            chain="base",
            tier="contributor",
            skip_antisybil=True,
            github_token="valid_token"
        )
        self.assertTrue(success)

    @patch("requests.get")
    def test_claim_with_mismatched_github_token(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "otheruser"}
        mock_get.return_value = mock_resp

        success, msg, claim = self.airdrop.claim_airdrop(
            github_username="tokenuser",
            wallet_address="RTC1234567890123456789012345678901234567893",
            chain="base",
            tier="contributor",
            skip_antisybil=True,
            github_token="valid_token"
        )
        self.assertFalse(success)
        self.assertIn("does not match", msg)

    @patch("requests.get")
    def test_claim_with_invalid_github_token_api_error(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        success, msg, claim = self.airdrop.claim_airdrop(
            github_username="tokenuser",
            wallet_address="RTC1234567890123456789012345678901234567893",
            chain="base",
            tier="contributor",
            skip_antisybil=True,
            github_token="invalid_token"
        )
        self.assertFalse(success)
        self.assertIn("Failed to verify", msg)

if __name__ == "__main__":
    unittest.main()
