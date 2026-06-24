import importlib.util
import sys
import types
from pathlib import Path


def load_exporter(monkeypatch, **env):
    for name in ("EXPORTER_PORT", "SCRAPE_INTERVAL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    prometheus = types.ModuleType("prometheus_client")

    class Metric:
        def __init__(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

        def info(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

    prometheus.Gauge = Metric
    prometheus.Counter = Metric
    prometheus.Info = Metric
    prometheus.start_http_server = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "prometheus_client", prometheus)

    module_path = Path(__file__).with_name("rustchain-exporter.py")
    spec = importlib.util.spec_from_file_location("rustchain_exporter_test_subject", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_malformed_numeric_env_falls_back_to_defaults(monkeypatch):
    module = load_exporter(
        monkeypatch,
        EXPORTER_PORT="not-an-int",
        SCRAPE_INTERVAL="",
    )

    assert module.EXPORTER_PORT == 9100
    assert module.SCRAPE_INTERVAL == 30


def test_valid_numeric_env_is_used(monkeypatch):
    module = load_exporter(
        monkeypatch,
        EXPORTER_PORT="9200",
        SCRAPE_INTERVAL="45",
    )

    assert module.EXPORTER_PORT == 9200
    assert module.SCRAPE_INTERVAL == 45
