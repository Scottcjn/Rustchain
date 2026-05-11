import importlib.machinery
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


class WsgiMockSignatureGuardTests(unittest.TestCase):
    def test_wsgi_invokes_mock_signature_guard_before_db_init(self):
        calls = []

        class FakeRustChainLoader:
            def create_module(self, spec):
                return types.ModuleType(spec.name)

            def exec_module(self, module):
                module.app = object()
                module.DB_PATH = ":memory:"
                module.enforce_mock_signature_runtime_guard = lambda: calls.append("guard")
                module.init_db = lambda: calls.append("init_db")

        node_dir = Path(__file__).resolve().parents[1]
        wsgi_path = node_dir / "wsgi.py"
        wsgi_spec = importlib.util.spec_from_file_location(
            "rustchain_wsgi_guard_test", str(wsgi_path)
        )
        wsgi_module = importlib.util.module_from_spec(wsgi_spec)
        main_spec = importlib.machinery.ModuleSpec(
            "rustchain_main", FakeRustChainLoader()
        )

        with mock.patch(
            "importlib.util.spec_from_file_location", return_value=main_spec
        ), mock.patch.dict(
            sys.modules,
            {"rustchain_p2p_init": None, "sophia_attestation_inspector": None},
        ):
            wsgi_spec.loader.exec_module(wsgi_module)

        self.assertIn("guard", calls)
        self.assertIn("init_db", calls)
        self.assertLess(calls.index("guard"), calls.index("init_db"))


if __name__ == "__main__":
    unittest.main()
