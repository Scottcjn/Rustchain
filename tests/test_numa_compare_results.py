import json

import pytest

from numa_sharding.benchmarks.compare_results import (
    BenchmarkMetrics,
    calculate_gain,
    compare_metrics,
    extract_metrics,
    parse_llama_bench_json,
)


def test_parse_llama_bench_json_normalizes_single_run(tmp_path):
    result_file = tmp_path / "single.json"
    result_file.write_text(json.dumps({"pp512": 10.0, "tg128": 20.0}))

    parsed = parse_llama_bench_json(str(result_file))

    assert parsed == {
        "runs": [{"pp512": 10.0, "tg128": 20.0}],
        "file": str(result_file),
    }


def test_parse_llama_bench_json_preserves_multiple_runs(tmp_path):
    runs = [
        {"pp512": 10.0, "tg128": 20.0},
        {"pp512": 14.0, "tg128": 26.0},
    ]
    result_file = tmp_path / "many.json"
    result_file.write_text(json.dumps(runs))

    parsed = parse_llama_bench_json(str(result_file))

    assert parsed["runs"] == runs
    assert parsed["file"] == str(result_file)


def test_extract_metrics_averages_runs_and_ignores_missing_metrics():
    metrics = extract_metrics(
        {
            "runs": [
                {"pp512": 10.0, "tg128": 20.0},
                {"pp512": 14.0},
                {"tg128": 26.0},
            ]
        }
    )

    assert metrics.pp512 == 12.0
    assert metrics.tg128 == 23.0
    assert metrics.pp512_std == pytest.approx(2.8284271247)
    assert metrics.tg128_std == pytest.approx(4.2426406871)


def test_calculate_gain_handles_zero_baseline_and_regression():
    assert calculate_gain(0.0, 50.0) == (50.0, 0.0)
    assert calculate_gain(100.0, 75.0) == (-25.0, -25.0)


def test_compare_metrics_marks_each_target_independently():
    baseline = BenchmarkMetrics(pp512=100.0, tg128=100.0)
    numa = BenchmarkMetrics(pp512=140.0, tg128=140.0)

    results = {result.metric: result for result in compare_metrics(baseline, numa)}

    assert results["pp512"].absolute_gain == 40.0
    assert results["pp512"].relative_gain_pct == 40.0
    assert results["pp512"].target_pct == 40.0
    assert results["pp512"].meets_target is True

    assert results["tg128"].absolute_gain == 40.0
    assert results["tg128"].relative_gain_pct == 40.0
    assert results["tg128"].target_pct == 45.0
    assert results["tg128"].meets_target is False
