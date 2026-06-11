import importlib.util
import os
import sys
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class BeaconGovernanceRateEnvDefaults(unittest.TestCase):
    def test_malformed_rate_limit_env_uses_defaults(self):
        old_env = dict(os.environ)
        module_name = "rcnode_rate_env_defaults_test"
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            os.environ.update({
                "RUSTCHAIN_DB_PATH": tmp.name,
                "RC_ADMIN_KEY": "0123456789abcdef0123456789abcdef",
                "RUSTCHAIN_DISABLE_P2P_AUTO_START": "1",
                "RC_ADMIN_RATE_LIMIT_MAX": "oops",
                "RC_ADMIN_RATE_LIMIT_WINDOW_SECONDS": "nope",
                "ATTEST_CHALLENGE_IP_LIMIT": "ten",
                "ATTEST_CHALLENGE_IP_WINDOW": "",
                "RC_BEACON_IP_RATE_LIMIT_MAX": "not-an-int",
                "RC_BEACON_IP_RATE_LIMIT_WINDOW_SECONDS": "",
                "RC_BEACON_IP_RATE_LIMIT_MAX_KEYS": "many",
                "RC_GOVERNANCE_VOTE_RATE_LIMIT_MAX": "NaN",
                "RC_GOVERNANCE_VOTE_RATE_LIMIT_WINDOW_SECONDS": "later",
            })

            sys.modules.pop(module_name, None)
            spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            self.assertEqual(mod.ADMIN_RATE_LIMIT_MAX, 12)
            self.assertEqual(mod.ADMIN_RATE_LIMIT_WINDOW, 60)
            self.assertEqual(mod.ATTEST_CHALLENGE_IP_LIMIT, 10)
            self.assertEqual(mod.ATTEST_CHALLENGE_IP_WINDOW, 60)
            self.assertEqual(mod.BEACON_IP_RATE_LIMIT_MAX, 120)
            self.assertEqual(mod.BEACON_IP_RATE_LIMIT_WINDOW, 60)
            self.assertEqual(mod._BEACON_IP_RATE_LIMIT_MAX_KEYS, 8192)
            self.assertEqual(mod.GOVERNANCE_VOTE_RATE_LIMIT_MAX, 20)
            self.assertEqual(mod.GOVERNANCE_VOTE_RATE_LIMIT_WINDOW, 60)
        finally:
            sys.modules.pop(module_name, None)
            os.environ.clear()
            os.environ.update(old_env)
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
