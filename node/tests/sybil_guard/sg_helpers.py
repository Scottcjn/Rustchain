# SPDX-License-Identifier: MIT
"""Shared helpers for the sybil_guard test suite.

NODE_DIR is the repo's node/ directory (the patched code under test).
BASELINE_DIR, when available, holds the PRE-PATCH versions of the four
settlement/attestation files, materialised from git at BASELINE_REF. Tests
that compare "before vs after" use it and are skipped when it cannot be
built (e.g. a shallow CI checkout); every other assertion still runs.
"""
import functools
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NODE_DIR = HERE.parents[1]
REPO = NODE_DIR.parent
FIXTURES = HERE / "fixtures"
NODE_FILE = "rustchain_v2_integrated_v2.2.1_rip200.py"
BASELINE_FILES = (NODE_FILE, "rip_200_round_robin_1cpu1vote.py",
                  "anti_double_mining.py", "rewards_implementation_rip200.py")
# main immediately before the sybil_guard change
BASELINE_REF = os.environ.get("SYBIL_GUARD_BASELINE_REF", "217ba85ef9cab3daac0da7b822c79437693444df")

for p in (str(NODE_DIR), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)


def load_json(name):
    return json.loads((FIXTURES / name).read_text())


@functools.lru_cache(maxsize=1)
def baseline_dir():
    """Directory with the pre-patch files, or None if git cannot provide them."""
    out = Path(tempfile.mkdtemp(prefix="sybil_guard_baseline_"))
    try:
        for name in BASELINE_FILES:
            blob = subprocess.run(
                ["git", "-C", str(REPO), "show", f"{BASELINE_REF}:node/{name}"],
                capture_output=True, check=True, timeout=60,
            ).stdout
            (out / name).write_bytes(blob)
    except (OSError, subprocess.SubprocessError):
        return None
    return out


def load_node(db_path, tag, source_dir=NODE_DIR):
    try:
        from tests import mock_crypto  # repo-root tests/mock_crypto.py
        sys.modules["rustchain_crypto"] = mock_crypto
    except Exception:
        pass
    os.environ["DB_PATH"] = str(db_path)
    os.environ["RUSTCHAIN_DB_PATH"] = str(db_path)
    os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
    spec = importlib.util.spec_from_file_location(f"node_under_test_{tag}", Path(source_dir) / NODE_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # Never start background peer sync from a test: make the node's optional
    # P2P import fail for the duration of this load only (a permanent stub
    # would break other suites that import the real module).
    _p2p = "rustchain_p2p_sync_secure"
    _had, _prev = _p2p in sys.modules, sys.modules.get(_p2p)
    sys.modules[_p2p] = None
    try:
        spec.loader.exec_module(module)
    finally:
        if _had:
            sys.modules[_p2p] = _prev
        else:
            sys.modules.pop(_p2p, None)
    module.DB_PATH = str(db_path)
    module.app.config["TESTING"] = True
    return module
