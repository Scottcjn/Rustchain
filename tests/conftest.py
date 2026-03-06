"""
Pytest configuration for RustChain tests.
"""

import sys
import sqlite3
import pytest
import os
import importlib.util
from pathlib import Path

# Add project root and node directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "node"))

# Mock environment variables required by the module at import time
os.environ["RC_ADMIN_KEY"] = "0" * 32
os.environ["DB_PATH"] = ":memory:"

# Helper to load modules with non-standard names (containing dots)
def load_node_module(module_name, file_name):
    if module_name in sys.modules:
        return sys.modules[module_name]

    node_dir = project_root / "node"
    spec = importlib.util.spec_from_file_location(module_name, str(node_dir / file_name))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Mock rustchain_crypto before loading other modules
from tests import mock_crypto
sys.modules["rustchain_crypto"] = mock_crypto

# Pre-load the modules to be shared across tests
load_node_module("integrated_node", "rustchain_v2_integrated_v2.2.1_rip200.py")
load_node_module("rewards_mod", "rewards_implementation_rip200.py")
load_node_module("rr_mod", "rip_200_round_robin_1cpu1vote.py")
load_node_module("tx_handler", "rustchain_tx_handler.py")

@pytest.fixture
def db_conn():
    """Provides an in-memory SQLite database connection."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()
