"""Regression tests for Issues #7321, #7323, #7325, #7327, #7329.

Module-level `int(os.getenv(...))` / `float(os.getenv(...))` casts crash the
RustChain node + supporting tools at import time when the env value is set
but malformed (e.g. ``EXPORTER_PORT=fast``). These tests verify that each
fixed module now degrades safely to its documented default instead of
crashing the process.

Run with:
    PYTHONPATH=node:. python3 -m pytest node/test_safe_numeric_env.py -v
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any, Dict, Iterable, Tuple

import pytest


# Reset prometheus_client's default registry between re-imports so the
# Gauge(...) calls in rustchain_exporter don't blow up on the second import
# with "Duplicated timeseries" errors. This is prometheus_client's documented
# pattern for tests that re-import modules that register metrics.
def _reset_prometheus_registry() -> None:
    try:
        from prometheus_client import REGISTRY
    except ImportError:
        return
    collectors = list(REGISTRY._names_to_collectors.keys())  # type: ignore[attr-defined]
    for name in collectors:
        try:
            REGISTRY.unregister(REGISTRY._names_to_collectors[name])  # type: ignore[attr-defined]
        except (KeyError, AttributeError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Test matrix: (module path, env name, attr name, malformed-value, expected
# default, type)
# ---------------------------------------------------------------------------
CASES: Tuple[Tuple[str, str, str, str, Any, type], ...] = (
    # node/auto_epoch_settler.py — Issue #7327
    ("node.auto_epoch_settler", "RUSTCHAIN_SETTLE_INTERVAL", "CHECK_INTERVAL", "fast", 300, int),
    ("node.auto_epoch_settler", "RUSTCHAIN_SLOTS_PER_EPOCH", "SLOTS_PER_EPOCH", "huge", 144, int),
    # tools/prometheus/rustchain_exporter.py — Issue #7321
    ("tools.prometheus.rustchain_exporter", "EXPORTER_PORT", "EXPORTER_PORT", "fast", 9100, int),
    ("tools.prometheus.rustchain_exporter", "SCRAPE_INTERVAL", "SCRAPE_INTERVAL", "huge", 60, int),
    ("tools.prometheus.rustchain_exporter", "REQUEST_TIMEOUT", "REQUEST_TIMEOUT", "huge", 15, int),
    # tools/miner_alerts/miner_alerts.py — Issue #7323
    ("tools.miner_alerts.miner_alerts", "POLL_INTERVAL", "POLL_INTERVAL", "fast", 120, int),
    ("tools.miner_alerts.miner_alerts", "OFFLINE_THRESHOLD", "OFFLINE_THRESHOLD", "foo", 600, int),
    ("tools.miner_alerts.miner_alerts", "LARGE_TRANSFER_THRESHOLD", "LARGE_TRANSFER_THRESHOLD", "huge", 10.0, float),
    ("tools.miner_alerts.miner_alerts", "SMTP_PORT", "SMTP_PORT", "bar", 587, int),
    # tools/webhooks/webhook_server.py — Issue #7325
    ("tools.webhooks.webhook_server", "WEBHOOK_POLL_INTERVAL", "DEFAULT_POLL_INTERVAL", "fast", 10, int),
    ("tools.webhooks.webhook_server", "LARGE_TX_THRESHOLD", "DEFAULT_LARGE_TX_THRESHOLD", "huge", 100.0, float),
    # node/bridge_api.py — Issue #7329
    ("node.bridge_api", "RC_BRIDGE_DEFAULT_CONFIRMATIONS", "BRIDGE_DEFAULT_CONFIRMATIONS", "fast", 12, int),
    ("node.bridge_api", "RC_BRIDGE_MAX_CONFIRMATIONS", "BRIDGE_MAX_CONFIRMATIONS", "foo", 1000, int),
    ("node.bridge_api", "RC_BRIDGE_LOCK_EXPIRY_SECONDS", "BRIDGE_LOCK_EXPIRY_SECONDS", "huge", 604800, int),
    ("node.bridge_api", "RC_BRIDGE_MIN_AMOUNT_RTC", "BRIDGE_MIN_AMOUNT_RTC", "bar", 1.0, float),
)


def _import_with_env(module_name: str, env_overrides: Dict[str, str]):
    """Import (or re-import) a module with the given env vars set.

    `importlib.import_module` returns the already-cached module on a second
    call; we have to evict it from `sys.modules` first so the module-level
    constants are re-evaluated under the new env.
    """
    saved_env = {k: os.environ.get(k) for k in env_overrides}
    try:
        # Evict module + any sub-modules from cache so re-import runs the
        # module body again with the new env.
        for mod in list(sys.modules.keys()):
            if mod == module_name or mod.startswith(module_name + "."):
                sys.modules.pop(mod, None)
        # Wipe prometheus_client's metric registry so re-imports of the
        # exporter don't trip on duplicate-timeseries registration errors.
        _reset_prometheus_registry()
        for k, v in env_overrides.items():
            os.environ[k] = v
        return importlib.import_module(module_name)
    finally:
        # Restore original env
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.mark.parametrize("module_name, env_name, attr_name, bad_value, default, kind", CASES)
def test_malformed_env_falls_back_to_default(module_name, env_name, attr_name, bad_value, default, kind):
    """A malformed env value must NOT crash the module — it must fall back
    to the documented default. Regression for Issue #7321 / #7323 / #7325 /
    #7327 / #7329 (Bounty #71)."""
    mod = _import_with_env(module_name, {env_name: bad_value})
    value = getattr(mod, attr_name)
    if kind is float:
        assert abs(value - default) < 1e-9, f"{module_name}.{attr_name} = {value!r}, expected {default}"
    else:
        assert value == default, f"{module_name}.{attr_name} = {value!r}, expected {default}"


@pytest.mark.parametrize("module_name, env_name, attr_name, bad_value, default, kind", CASES)
def test_empty_string_env_falls_back_to_default(module_name, env_name, attr_name, bad_value, default, kind):
    """An empty env value must fall back to the documented default."""
    mod = _import_with_env(module_name, {env_name: ""})
    value = getattr(mod, attr_name)
    if kind is float:
        assert abs(value - default) < 1e-9
    else:
        assert value == default


@pytest.mark.parametrize("module_name, env_name, attr_name, bad_value, default, kind", CASES[:4])
def test_valid_env_value_is_respected(module_name, env_name, attr_name, bad_value, default, kind):
    """A valid env value must still override the default (regression guard)."""
    valid = "42" if kind is int else "42.5"
    mod = _import_with_env(module_name, {env_name: valid})
    value = getattr(mod, attr_name)
    if kind is float:
        assert abs(value - 42.5) < 1e-9
    else:
        assert value == 42
