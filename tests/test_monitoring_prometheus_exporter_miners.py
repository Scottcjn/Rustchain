# SPDX-License-Identifier: MIT
import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "monitoring" / "prometheus_exporter.py"


class FakeMetric:
    def __init__(self, *args, **kwargs):
        self.samples = []
        self.observations = []

    def labels(self, **labels):
        self.last_labels = labels
        return self

    def set(self, value):
        self.samples.append((self.last_labels, value))

    def inc(self):
        self.samples.append((self.last_labels, "inc"))

    def info(self, value):
        self.samples.append((self.last_labels, value))

    def observe(self, value):
        self.observations.append((self.last_labels, value))


def load_exporter_module():
    prometheus_stub = types.ModuleType("prometheus_client")
    prometheus_stub.start_http_server = lambda *args, **kwargs: None
    prometheus_stub.Gauge = FakeMetric
    prometheus_stub.Counter = FakeMetric
    prometheus_stub.Info = FakeMetric
    prometheus_stub.Histogram = FakeMetric
    sys.modules["prometheus_client"] = prometheus_stub

    spec = importlib.util.spec_from_file_location("monitoring_prometheus_exporter", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_scrape_miners_accepts_paginated_api_envelope(monkeypatch):
    module = load_exporter_module()
    exporter = module.RustChainPrometheusExporter("https://node.example")
    monkeypatch.setattr(
        exporter,
        "_make_request",
        lambda endpoint: {
            "miners": [
                {"miner_id": "alice-id", "antiquity_score": 2.5},
                {"miner": "bob", "antiquity_score": 0.5},
            ],
            "pagination": {"total": 12, "limit": 2, "offset": 0, "count": 2},
        },
    )

    exporter._scrape_miners()

    assert module.rustchain_active_miners.samples[-1] == ({"node_url": "https://node.example"}, 2)
    assert module.rustchain_total_miners.samples[-1] == ({"node_url": "https://node.example"}, 12)
    assert module.rustchain_miner_antiquity_distribution.observations == [
        ({"node_url": "https://node.example"}, 2.5),
        ({"node_url": "https://node.example"}, 0.5),
    ]
