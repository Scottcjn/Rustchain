# SPDX-License-Identifier: MIT
"""Load the monitor modules (several have hyphens or live in sibling dirs and
cannot be imported by name) exactly once per pytest process."""

import importlib.util
import os
import sys
import tempfile
import urllib.error
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load(name: str, relpath: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relpath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_exporter():
    """monitoring/rustchain-exporter.py (hyphenated filename)."""
    return _load("rustchain_exporter_under_test", "monitoring/rustchain-exporter.py")


def load_dashboard_server():
    """health-dashboard/server.py."""
    return _load("health_dashboard_server_under_test", "health-dashboard/server.py")


def load_node_health_monitor():
    """tools/node_health_monitor.py."""
    return _load("node_health_monitor_under_test", "tools/node_health_monitor.py")


def load_node_health_cli():
    """tools/node-health-cli/node_health.py."""
    return _load("node_health_cli_under_test", "tools/node-health-cli/node_health.py")


def load_status_server():
    """status/status_server.py.

    The module starts a background poller and polls once at import time, so
    the import happens with urlopen blocked and the poller is then pointed at
    a stub — no real network traffic from tests.
    """
    name = "status_server_under_test"
    if name in sys.modules:
        return sys.modules[name]
    os.environ.setdefault("STATUS_DATA_DIR", tempfile.mkdtemp(prefix="rtc-status-test-"))
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "status/status_server.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    with mock.patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("blocked by test loader"),
    ):
        spec.loader.exec_module(module)
    # Keep the daemon poller thread from ever hitting the network again; the
    # real implementation stays available as check_node_real for tests.
    module.check_node_real = module.check_node
    module.check_node = lambda node: {
        "up": False, "state": "unreachable", "error": "blocked by test loader",
        "response_ms": 0, "checked_at": "1970-01-01T00:00:00Z",
    }
    module.POLL_INTERVAL = 10 ** 9
    return module
