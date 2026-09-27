# SPDX-License-Identifier: MIT
"""Fail-closed guard: a production node must not start on legacy hardware binding.

hardware_binding_v2 is the layer that stops one physical machine being re-bound
to a second wallet. If the module fails to import, the node used to log a warning
and keep paying rewards under the weaker legacy binder. The guard turns that
silent degradation into a startup failure in production, while leaving test/dev
runtimes and an explicit operator override (RC_ALLOW_LEGACY_HW_BINDING=1) alone.
Suggested by @antoleod (Quest #398 Step 1, 2026-09-05).
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path


def _load_integrated_node():
    module_name = "integrated_node_hwguard_tests"
    if module_name in sys.modules:
        return sys.modules[module_name]
    project_root = Path(__file__).resolve().parents[2]
    module_path = project_root / "node" / "rustchain_v2_integrated_v2.2.1_rip200.py"
    os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
    os.environ.setdefault("DB_PATH", ":memory:")
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


integrated_node = _load_integrated_node()


class HardwareBindingGuardTests(unittest.TestCase):
    def setUp(self):
        self._orig_flag = integrated_node.HW_BINDING_V2
        self._saved = {k: os.environ.get(k) for k in ("RC_RUNTIME_ENV", "RUSTCHAIN_ENV", "RC_ALLOW_LEGACY_HW_BINDING")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        integrated_node.HW_BINDING_V2 = self._orig_flag
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_v2_present_passes_everywhere(self):
        integrated_node.HW_BINDING_V2 = True
        integrated_node.enforce_hardware_binding_runtime_guard()  # production default env

    def test_legacy_in_production_fails_closed(self):
        integrated_node.HW_BINDING_V2 = False
        with self.assertRaises(RuntimeError):
            integrated_node.enforce_hardware_binding_runtime_guard()

    def test_legacy_in_test_runtime_allowed(self):
        integrated_node.HW_BINDING_V2 = False
        os.environ["RC_RUNTIME_ENV"] = "test"
        integrated_node.enforce_hardware_binding_runtime_guard()

    def test_legacy_in_production_with_explicit_override(self):
        integrated_node.HW_BINDING_V2 = False
        os.environ["RC_ALLOW_LEGACY_HW_BINDING"] = "1"
        integrated_node.enforce_hardware_binding_runtime_guard()

    def test_wsgi_calls_guard_before_init_db(self):
        wsgi_src = (Path(__file__).resolve().parents[2] / "node" / "wsgi.py").read_text(encoding="utf-8")
        guard_idx = wsgi_src.find("enforce_hardware_binding_runtime_guard()")
        init_idx = wsgi_src.find("init_db()")
        self.assertNotEqual(guard_idx, -1, "wsgi.py must call enforce_hardware_binding_runtime_guard()")
        self.assertLess(guard_idx, init_idx, "guard must run before init_db()")


if __name__ == "__main__":
    unittest.main(verbosity=2)
