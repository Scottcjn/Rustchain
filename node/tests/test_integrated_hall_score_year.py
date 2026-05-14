# SPDX-License-Identifier: MIT

import importlib.util
import os
import sys
import tempfile
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"


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


def _load_node_module():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "import.db")
        old_env = {
            name: os.environ.get(name)
            for name in ("RUSTCHAIN_DB_PATH", "DB_PATH", "RC_ADMIN_KEY")
        }
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        os.environ["DB_PATH"] = db_path
        os.environ["RC_ADMIN_KEY"] = "test-admin-key-for-hall-score-32-bytes"
        sys.path.insert(0, str(NODE_DIR))
        try:
            import prometheus_client
        except ImportError:
            prometheus_client = None
            old_metrics = None
        else:
            old_metrics = (
                prometheus_client.Counter,
                prometheus_client.Gauge,
                prometheus_client.Histogram,
            )
            prometheus_client.Counter = _NoopMetric
            prometheus_client.Gauge = _NoopMetric
            prometheus_client.Histogram = _NoopMetric
        try:
            spec = importlib.util.spec_from_file_location(
                "rustchain_integrated_hall_score_test_module",
                MODULE_PATH,
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules["rustchain_integrated_hall_score_test_module"] = module
            spec.loader.exec_module(module)
            return module
        finally:
            if prometheus_client is not None:
                (
                    prometheus_client.Counter,
                    prometheus_client.Gauge,
                    prometheus_client.Histogram,
                ) = old_metrics
            for name, value in old_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            try:
                sys.path.remove(str(NODE_DIR))
            except ValueError:
                pass


def test_calculate_rust_score_inline_uses_current_year_for_age_bonus():
    node = _load_node_module()

    score = node.calculate_rust_score_inline(
        2001,
        "modern",
        0,
        999,
        current_year=2026,
    )

    assert score == 250
