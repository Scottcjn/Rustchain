# SPDX-License-Identifier: MIT
"""Shared helpers for suites that exec the integrated node module.

Loading ``rustchain_v2_integrated_*.py`` registers gauges on the global
prometheus registry; a second load in the same pytest session raises
DuplicateTimeseries (strict since prometheus_client 0.24). Suites that load the
node under an ``rcnode*`` module name must release it before their own load and
again in tearDownClass so every execution order — per-file CI invocations or one
combined session — stays green. The metric list mirrors the unregister set in
test_enroll_weight_device_spoof._release.
"""

import sys

_NODE_PROMETHEUS_METRICS = (
    "withdrawal_requests",
    "withdrawal_completed",
    "withdrawal_failed",
    "balance_gauge",
    "epoch_gauge",
    "withdrawal_queue_size",
)


def release_node_modules():
    """Unregister prometheus metrics of ``rcnode*`` modules and unload them."""
    try:
        from prometheus_client import REGISTRY
    except ImportError:
        return
    for name, mod in list(sys.modules.items()):
        if not name.startswith("rcnode") or mod is None:
            continue
        for metric_name in _NODE_PROMETHEUS_METRICS:
            metric = getattr(mod, metric_name, None)
            if metric is None:
                continue
            try:
                REGISTRY.unregister(metric)
            except (KeyError, ValueError):
                pass
        del sys.modules[name]
