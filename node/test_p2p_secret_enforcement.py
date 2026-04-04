#!/usr/bin/env python3
"""
Tests for RC_P2P_SECRET enforcement in rustchain_p2p_gossip.py.

Verifies that the module refuses to start when:
  1. RC_P2P_SECRET is unset
  2. RC_P2P_SECRET is an empty string
  3. RC_P2P_SECRET is a known insecure placeholder
  4. RC_P2P_SECRET is set to a valid non-empty value (should import OK)
"""

import subprocess
import sys
import os
import unittest

GOSSIP_MODULE = os.path.join(os.path.dirname(__file__), "rustchain_p2p_gossip.py")


def _import_with_env(env_vars: dict) -> subprocess.CompletedProcess:
    """Attempt to import the gossip module under a given environment."""
    env = os.environ.copy()
    env.update(env_vars)
    # Remove any pre-existing RC_P2P_SECRET first
    env.pop("RC_P2P_SECRET", None)
    env.update(env_vars)

    code = (
        "import sys; sys.path.insert(0, '.');"
        "import importlib.util;"
        "spec = importlib.util.spec_from_file_location('gossip', 'rustchain_p2p_gossip.py');"
        "mod = importlib.util.module_from_spec(spec);"
        "spec.loader.exec_module(mod)"
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=os.path.dirname(__file__),
        env=env, timeout=15
    )


class TestP2PSecretEnforcement(unittest.TestCase):

    def test_unset_secret_causes_fatal_exit(self):
        """Module must raise SystemExit when RC_P2P_SECRET is not set."""
        result = _import_with_env({})
        self.assertNotEqual(result.returncode, 0,
                            f"Expected non-zero exit, got {result.returncode}")
        self.assertIn("RC_P2P_SECRET", result.stderr + result.stdout)

    def test_empty_string_secret_causes_fatal_exit(self):
        """Module must raise SystemExit when RC_P2P_SECRET is empty."""
        result = _import_with_env({"RC_P2P_SECRET": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RC_P2P_SECRET", result.stderr + result.stdout)

    def test_known_insecure_default_causes_fatal_exit(self):
        """Module must reject the old hardcoded value."""
        result = _import_with_env({
            "RC_P2P_SECRET": "rustchain_p2p_secret_2025_decentralized"
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("insecure", (result.stderr + result.stdout).lower())

    def test_valid_secret_allows_import(self):
        """Module must load successfully with a strong random secret."""
        result = _import_with_env({"RC_P2P_SECRET": "a" * 64})
        self.assertEqual(result.returncode, 0,
                         f"Import failed with valid secret: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
