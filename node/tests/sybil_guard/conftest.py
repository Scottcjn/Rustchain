# SPDX-License-Identifier: MIT
"""Fixtures for the sybil_guard suite. Helpers live in sg_helpers.py (importing
from `conftest` is ambiguous with node/tests/conftest.py). No network: P2P sync
is stubbed while the node is imported (sg_helpers.load_node)."""
import pytest

from sg_helpers import load_json  # noqa: F401  (also puts node/ on sys.path)


@pytest.fixture(scope="session")
def sybil_rows():
    return load_json("sybil_profiles.json")


@pytest.fixture(scope="session")
def honest_rows():
    return load_json("honest_profiles.json")


@pytest.fixture(autouse=True)
def _standard_settlement_path_allowed(monkeypatch):
    """main defaults RC_REQUIRE_ADM to ON in production runtimes (#8352), which
    refuses the standard (non-ADM) settlement path outright. These tests
    exercise the hold on BOTH paths, so allow the standard path explicitly;
    tests that need ADM to be mandatory set RC_REQUIRE_ADM=1 themselves."""
    monkeypatch.setenv("RC_REQUIRE_ADM", "0")
