# SPDX-License-Identifier: MIT
import importlib.util
import os
import sys
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class _NoopMetric:
    def __init__(self, *args, **kwargs):
        pass

    def inc(self, *args, **kwargs):
        pass

    def dec(self, *args, **kwargs):
        pass

    def set(self, *args, **kwargs):
        pass

    def observe(self, *args, **kwargs):
        pass

    def labels(self, *args, **kwargs):
        return self


class TestIntegratedMetricsRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._import_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._import_tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = "0" * 32

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        prometheus_client = None
        prev_metrics = None
        try:
            import prometheus_client

            prev_metrics = (
                prometheus_client.Counter,
                prometheus_client.Gauge,
                prometheus_client.Histogram,
            )
            prometheus_client.Counter = _NoopMetric
            prometheus_client.Gauge = _NoopMetric
            prometheus_client.Histogram = _NoopMetric
        except ModuleNotFoundError:
            pass
        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_metrics_route_test",
            MODULE_PATH,
        )
        cls.mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(cls.mod)
        finally:
            if prometheus_client is not None and prev_metrics is not None:
                (
                    prometheus_client.Counter,
                    prometheus_client.Gauge,
                    prometheus_client.Histogram,
                ) = prev_metrics

    @classmethod
    def tearDownClass(cls):
        if cls._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db_path
        if cls._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin_key
        cls._import_tmp.cleanup()

    def test_api_metrics_alias_returns_prometheus_text(self):
        client = self.mod.app.test_client()

        legacy = client.get("/metrics")
        api = client.get("/api/metrics")

        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(api.status_code, 200)
        self.assertEqual(api.data, legacy.data)
        self.assertIn("text/plain", api.content_type)


if __name__ == "__main__":
    unittest.main()
