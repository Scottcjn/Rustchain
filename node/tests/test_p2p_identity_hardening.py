import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from node.p2p_identity import LocalKeypair, PeerRegistry, pack_signature, unpack_signature


class TestP2PIdentityHardening(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.key_path = Path(self.tmp_dir) / "p2p_identity.pem"
        self.reg_path = Path(self.tmp_dir) / "peer_registry.json"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_item_a_key_rotation(self):
        """Item A: Key versioning and rotation"""
        # 1. Initial generation (v1)
        kp = LocalKeypair(path=self.key_path)
        _ = kp.pubkey_hex  # trigger load/generate
        self.assertEqual(kp.key_version, 1)
        pub1 = kp.pubkey_hex

        # 2. Force rotation (v2)
        os.environ["RC_P2P_KEYGEN"] = "1"
        kp2 = LocalKeypair(path=self.key_path)
        _ = kp2.pubkey_hex  # trigger rotation
        self.assertEqual(kp2.key_version, 2)
        pub2 = kp2.pubkey_hex
        self.assertNotEqual(pub1, pub2)

        # Check archive exists
        archive_path = self.key_path.parent / "p2p_identity.v1.pem"
        self.assertTrue(archive_path.exists())

        # 3. Load v2 back
        os.environ["RC_P2P_KEYGEN"] = "0"
        kp3 = LocalKeypair(path=self.key_path)
        _ = kp3.pubkey_hex
        self.assertEqual(kp3.key_version, 2)
        self.assertEqual(kp3.pubkey_hex, pub2)

    def test_item_b_registry_expiry(self):
        """Item B: Registry not_before / not_after validation"""
        registry_data = {
            "version": 1,
            "peers": [
                {"node_id": "expired_peer", "pubkey_hex": "01" * 32, "not_after": "2020-01-01T00:00:00Z"},
                {"node_id": "future_peer", "pubkey_hex": "02" * 32, "not_before": "2030-01-01T00:00:00Z"},
                {
                    "node_id": "valid_peer",
                    "pubkey_hex": "03" * 32,
                    "not_before": "2026-01-01T00:00:00Z",
                    "not_after": "2027-01-01T00:00:00Z",
                },
            ],
        }
        with open(self.reg_path, "w") as f:
            json.dump(registry_data, f)

        reg = PeerRegistry(path=self.reg_path)

        # expired_peer should return None
        self.assertIsNone(reg.get_pubkey("expired_peer"))
        # future_peer should return None
        self.assertIsNone(reg.get_pubkey("future_peer"))
        # valid_peer should return pubkey (assuming current date is 2026-04-18)
        self.assertEqual(reg.get_pubkey("valid_peer"), "03" * 32)

    def test_signature_pack_unpack_version(self):
        """Verify pack/unpack handles version field"""
        packed = pack_signature("h1", "e1", 2)
        self.assertIn('"v":2', packed)

        h, e, v = unpack_signature(packed)
        self.assertEqual(h, "h1")
        self.assertEqual(e, "e1")
        self.assertEqual(v, 2)

        # Legacy fallback
        h, e, v = unpack_signature("legacy_hex")
        self.assertEqual(h, "legacy_hex")
        self.assertIsNone(e)
        self.assertEqual(v, 1)


if __name__ == "__main__":
    unittest.main()
