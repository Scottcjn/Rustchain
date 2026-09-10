# SPDX-License-Identifier: MIT

import hashlib
import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).with_name("rustchain_termux_miner.py")
spec = importlib.util.spec_from_file_location("termux_miner_wrapper", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TermuxMinerSafetyTests(unittest.TestCase):
    def test_production_node_is_rejected_for_test_only(self):
        for url in ("https://rustchain.org", "https://www.rustchain.org/", "https://rustchain.org."):
            with self.subTest(url=url), self.assertRaises(ValueError):
                mod.validate_test_node_url(url)

    def test_local_test_node_is_allowed(self):
        self.assertEqual(
            mod.validate_test_node_url("http://127.0.0.1:58333/"),
            "http://127.0.0.1:58333",
        )

    def test_termux_detection_requires_android_and_termux_marker(self):
        with mock.patch.object(mod.platform, "system", return_value="Android"), mock.patch.dict(
            os.environ,
            {"PREFIX": "/data/data/com.termux/files/usr", "TERMUX_VERSION": "0.118.3"},
            clear=False,
        ):
            self.assertTrue(mod.is_termux_android())
        with mock.patch.object(mod.platform, "system", return_value="Linux"):
            self.assertFalse(mod.is_termux_android())

    def test_verification_modes_are_mutually_exclusive(self):
        parser = mod.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--dry-run", "--test-only"])

    def test_checksum_manifest_pins_termux_wrapper(self):
        root = Path(__file__).resolve().parents[2]
        wrapper = root / "miners" / "termux" / "rustchain_termux_miner.py"
        manifest = root / "miners" / "checksums.sha256"
        entries = {}
        for line in manifest.read_text(encoding="utf-8").splitlines():
            digest, artifact = line.split(maxsplit=1)
            entries[artifact] = digest
        self.assertEqual(
            entries.get("termux/rustchain_termux_miner.py"),
            hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        )

    def test_installer_places_down_marker_before_run_script(self):
        installer = Path(__file__).with_name("install.sh").read_text(encoding="utf-8")
        down = installer.index('touch "$SERVICE_DIR/down"')
        run = installer.index('> "$SERVICE_DIR/run"')
        self.assertLess(down, run)

    def test_installer_verifies_termux_wrapper(self):
        installer = Path(__file__).with_name("install.sh").read_text(encoding="utf-8")
        self.assertIn(
            "verify_sha rustchain_termux_miner.py termux/rustchain_termux_miner.py",
            installer,
        )


if __name__ == "__main__":
    unittest.main()
