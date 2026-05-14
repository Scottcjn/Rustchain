import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "pse" / "numa_topology.py"


def _load_numa_topology_module():
    spec = importlib.util.spec_from_file_location("pse_numa_topology", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_numastat_extracts_node_metrics(tmp_path):
    module = _load_numa_topology_module()
    numastat = tmp_path / "stock_numastat.txt"
    numastat.write_text(
        """
                           Node 0          Node 1
MemTotal               32768.00        32768.00
MemFree                1024.50         2048.25
FilePages              300.00          not-a-number
"""
    )

    parsed = module.parse_numastat(numastat)

    assert parsed == {
        "MemTotal": {"node0": 32768.0, "node1": 32768.0},
        "MemFree": {"node0": 1024.5, "node1": 2048.25},
        "FilePages": {"node0": 300.0, "node1": 0.0},
    }


def test_parse_numastat_handles_missing_empty_and_headerless_files(tmp_path):
    module = _load_numa_topology_module()
    missing = tmp_path / "missing.txt"
    empty = tmp_path / "empty.txt"
    headerless = tmp_path / "headerless.txt"
    empty.write_text("")
    headerless.write_text("MemTotal 1 2\nMemFree 3 4\n")

    assert module.parse_numastat(missing) is None
    assert module.parse_numastat(empty) is None
    assert module.parse_numastat(headerless) is None


def test_load_coffer_activity_ignores_charts_and_empty_numastat(tmp_path):
    module = _load_numa_topology_module()
    model_dir = tmp_path / "TinyLlama"
    charts_dir = tmp_path / "charts"
    model_dir.mkdir()
    charts_dir.mkdir()
    (model_dir / "stock_numastat.txt").write_text(
        """
              Node 0 Node 1
MemTotal      100    200
MemFree       25     50
"""
    )
    (model_dir / "empty_numastat.txt").write_text("")
    (charts_dir / "ignored_numastat.txt").write_text("Node 0\nMemTotal 1\n")

    activity = module.load_coffer_activity(tmp_path)

    assert activity == {
        "TinyLlama": [
            {
                "mode": "stock",
                "numa": {
                    "MemTotal": {"node0": 100.0, "node1": 200.0},
                    "MemFree": {"node0": 25.0, "node1": 50.0},
                },
            }
        ]
    }
