from __future__ import annotations

import importlib.util
import math
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("compare_results.py")
SPEC = importlib.util.spec_from_file_location("compare_results", MODULE_PATH)
compare_results = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(compare_results)


def test_extract_metrics_returns_zeroes_without_runs():
    metrics = compare_results.extract_metrics({})

    assert metrics.pp512 == 0.0
    assert metrics.tg128 == 0.0
    assert metrics.pp512_std == 0.0
    assert metrics.tg128_std == 0.0
    assert metrics.memory_bandwidth == 0.0
    assert metrics.cross_numa_pct == 0.0


def test_extract_metrics_ignores_missing_metric_keys():
    metrics = compare_results.extract_metrics(
        {
            "runs": [
                {"pp512": 10.0},
                {"tg128": 20.0},
                {"pp512": 14.0, "tg128": 30.0},
                {"unrelated": 99.0},
            ],
        }
    )

    assert metrics.pp512 == 12.0
    assert metrics.tg128 == 25.0
    assert math.isclose(metrics.pp512_std, math.sqrt(8.0))
    assert math.isclose(metrics.tg128_std, math.sqrt(50.0))


def test_extract_metrics_uses_zero_stddev_for_singleton_metrics():
    metrics = compare_results.extract_metrics(
        {
            "runs": [
                {"pp512": 42.0},
                {"unrelated": 12.0},
            ],
        }
    )

    assert metrics.pp512 == 42.0
    assert metrics.tg128 == 0.0
    assert metrics.pp512_std == 0.0
    assert metrics.tg128_std == 0.0
