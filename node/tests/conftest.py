"""Test configuration — adds node/ to Python path for sibling module imports.

Also sets RC_ADMIN_KEY to a test value so the _require_admin() gate in
hall_of_rust (and any sibling admin-gated routes) is reachable from tests
that pass X-Admin-Key. Tests that exercise the fail-closed / unauthenticated
path can monkeypatch.delenv("RC_ADMIN_KEY") to remove the key entirely.
"""
import os
import sys
from pathlib import Path

# Add parent directory (node/) to sys.path so tests can import sibling modules
# like bottube_feed from bottube_feed_routes
tests_dir = Path(__file__).parent
node_dir = tests_dir.parent
if str(node_dir) not in sys.path:
    sys.path.insert(0, str(node_dir))


# Provide a stable admin key for the test session. Individual tests that want
# to exercise the fail-closed branch (no key configured) should call
# `monkeypatch.delenv("RC_ADMIN_KEY", raising=False)` inside the test.
os.environ.setdefault("RC_ADMIN_KEY", "test-admin-key")
