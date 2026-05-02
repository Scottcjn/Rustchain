import os
import shutil
import tempfile
import unittest
from pathlib import Path

from node.p2p_identity import LocalKeypair, get_default_privkey_path


class TestNonRootKeyPath(unittest.TestCase):
    def setUp(self):
        self.tmp_home = tempfile.mkdtemp()
        self.old_home = os.environ.get("HOME")
        os.environ["HOME"] = self.tmp_home

        # Ensure /etc/rustchain is "unwritable" (doesn't exist in our environment usually,
        # or we can mock it if needed. For now let's assume it fails and we hit HOME.)

    def tearDown(self):
        if self.old_home:
            os.environ["HOME"] = self.old_home
        shutil.rmtree(self.tmp_home)

    def test_fallback_to_user_home(self):
        """Assert that if /etc/rustchain is unwritable, we fall back to $HOME/.rustchain"""
        # We assume /etc/rustchain/p2p_identity.pem is unwritable for the current user (albega)
        # unless albega is root.

        path = get_default_privkey_path()

        # In a normal non-root environment, it should be the HOME one
        expected_home_path = Path(self.tmp_home) / ".rustchain" / "p2p_identity.pem"

        # Note: on some CI it might actually be writable. Let's check.
        if os.access("/etc", os.W_OK):
            # Skip or adjust if we are actually root
            self.skipTest("Running as root/sudo, /etc is writable.")

        self.assertEqual(path, expected_home_path)

    def test_local_keypair_uses_fallback(self):
        """Assert LocalKeypair uses the fallback path automatically."""
        if os.access("/etc", os.W_OK):
            self.skipTest("Running as root/sudo, /etc is writable.")

        kp = LocalKeypair()
        expected_home_path = Path(self.tmp_home) / ".rustchain" / "p2p_identity.pem"
        self.assertEqual(kp.path, expected_home_path)


if __name__ == "__main__":
    unittest.main()
