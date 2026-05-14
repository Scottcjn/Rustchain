import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "pse" / "analyze_results.py"
SPEC = importlib.util.spec_from_file_location("pse_analyze_results", MODULE_PATH)
pse_analyze_results = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pse_analyze_results)


def test_load_results_filters_support_files_and_invalid_json(tmp_path, capsys):
    valid_result = {
        "model": "tinyllama",
        "results": [{"build_mode": "stock"}],
    }
    (tmp_path / "tinyllama.json").write_text(json.dumps(valid_result))
    (tmp_path / "metadata.json").write_text(json.dumps({"model": "metadata only"}))
    (tmp_path / "progress.json").write_text(json.dumps({"model": "ignored", "results": []}))
    (tmp_path / "numa_topology.json").write_text(json.dumps({"model": "ignored", "results": []}))
    (tmp_path / "broken.json").write_text("{not-json")

    results = pse_analyze_results.load_results(tmp_path)

    assert results == [valid_result]
    assert "Warning: skipping broken.json" in capsys.readouterr().err


def test_load_numa_topology_returns_snapshot_when_present(tmp_path):
    assert pse_analyze_results.load_numa_topology(tmp_path) is None

    topology = {
        "num_nodes": 2,
        "nodes": [{"id": 0, "cpus": [0, 1]}, {"id": 1, "cpus": [2, 3]}],
    }
    (tmp_path / "numa_topology.json").write_text(json.dumps(topology))

    assert pse_analyze_results.load_numa_topology(tmp_path) == topology


def test_generate_markdown_writes_tables_and_speedups(tmp_path):
    output_path = tmp_path / "REPORT.md"
    results = [
        {
            "model": "tinyllama",
            "model_file": "tinyllama.gguf",
            "timestamp": "2026-01-02T03:04:05Z",
            "config": {"pp_sizes": [128], "tg_sizes": [32]},
            "results": [
                {
                    "build_mode": "stock",
                    "prompt_processing": {"pp128": {"mean": 100.0, "cv_pct": 1.0}},
                    "token_generation": {"tg32": {"mean": 50.0, "cv_pct": 2.0}},
                    "cache_metrics": {"l1_hit_rate_pct": 92.25, "llc_hit_rate_pct": 88.5},
                    "pse_markers": {
                        "noi": 0,
                        "divergence_ratio": 0.0,
                        "altivec_cycle_share": 0.0,
                        "memory_coffer_index": 0,
                    },
                },
                {
                    "build_mode": "pse_mass",
                    "prompt_processing": {"pp128": {"mean": 150.0, "cv_pct": 1.5}},
                    "token_generation": {"tg32": {"mean": 60.0, "cv_pct": 2.5}},
                    "cache_metrics": {"l1_hit_rate_pct": 94.0, "llc_hit_rate_pct": 90.0},
                    "pse_markers": {
                        "noi": 12,
                        "divergence_ratio": 0.0001,
                        "altivec_cycle_share": 40.5,
                        "memory_coffer_index": 1,
                    },
                },
                {
                    "build_mode": "pse_coffers",
                    "prompt_processing": {"pp128": {"mean": 175.0, "cv_pct": 2.0}},
                    "token_generation": {"tg32": {"mean": 75.0, "cv_pct": 3.0}},
                    "cache_metrics": {"l1_hit_rate_pct": 95.5, "llc_hit_rate_pct": 91.75},
                    "pse_markers": {
                        "noi": 18,
                        "divergence_ratio": 0.0002,
                        "altivec_cycle_share": 55.5,
                        "memory_coffer_index": 2,
                    },
                },
            ],
        }
    ]

    report = pse_analyze_results.generate_markdown(results, output_path)

    assert output_path.read_text() == report
    assert "# POWER8 PSE Benchmark Results" in report
    assert "## tinyllama" in report
    assert "| Build Mode | pp128 |" in report
    assert "| Stock llama.cpp | 100.0 (1.0% CV) |" in report
    assert "| PSE+Coffers | 175.0 (2.0% CV) |" in report
    assert "| Build Mode | tg32 |" in report
    assert "| Stock llama.cpp | 92.25% | 88.50% |" in report
    assert "| PSE-MASS | 12 | 0.0001 | 40.5 | 1 |" in report
    assert "| pp128 | 1.50x | 1.75x |" in report
    assert "| tg32 | 1.20x | 1.50x |" in report
    assert "## PSE Marker Reference" in report
