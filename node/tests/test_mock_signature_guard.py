import importlib.util
import os
import sys
import unittest
from pathlib import Path


def _load_integrated_node():
    module_name = "integrated_node_guard_tests"
    if module_name in sys.modules:
        return sys.modules[module_name]

    project_root = Path(__file__).resolve().parents[2]
    node_dir = project_root / "node"
    module_path = node_dir / "rustchain_v2_integrated_v2.2.1_rip200.py"

    os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
    os.environ.setdefault("DB_PATH", ":memory:")

    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


integrated_node = _load_integrated_node()


class MockSignatureGuardTests(unittest.TestCase):
    def setUp(self):
        self._orig_mock_sig = integrated_node.TESTNET_ALLOW_MOCK_SIG
        self._orig_runtime_env = os.environ.get("RC_RUNTIME_ENV")
        self._orig_rustchain_env = os.environ.get("RUSTCHAIN_ENV")

    def tearDown(self):
        integrated_node.TESTNET_ALLOW_MOCK_SIG = self._orig_mock_sig
        if self._orig_runtime_env is None:
            os.environ.pop("RC_RUNTIME_ENV", None)
        else:
            os.environ["RC_RUNTIME_ENV"] = self._orig_runtime_env
        if self._orig_rustchain_env is None:
            os.environ.pop("RUSTCHAIN_ENV", None)
        else:
            os.environ["RUSTCHAIN_ENV"] = self._orig_rustchain_env

    def test_fails_closed_when_mock_signatures_enabled_in_production(self):
        integrated_node.TESTNET_ALLOW_MOCK_SIG = True
        os.environ["RC_RUNTIME_ENV"] = "production"
        os.environ.pop("RUSTCHAIN_ENV", None)

        with self.assertRaisesRegex(RuntimeError, "TESTNET_ALLOW_MOCK_SIG"):
            integrated_node.enforce_mock_signature_runtime_guard()

    def test_allows_mock_signatures_in_test_runtime(self):
        integrated_node.TESTNET_ALLOW_MOCK_SIG = True
        os.environ["RC_RUNTIME_ENV"] = "test"
        os.environ.pop("RUSTCHAIN_ENV", None)

        integrated_node.enforce_mock_signature_runtime_guard()


if __name__ == "__main__":
    unittest.main()
