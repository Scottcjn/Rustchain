# SPDX-License-Identifier: MIT

from pathlib import Path


NODE_PATH = Path(__file__).resolve().parents[1] / "rustchain_v2_integrated_v2.2.1_rip200.py"


def test_openapi_balance_path_is_not_shadowed_by_duplicate_schema():
    """The OpenAPI balance path should expose the balance_rtc schema."""
    source = NODE_PATH.read_text(encoding="utf-8")
    assert source.count('"/balance/{miner_pk}"') == 1

    balance_path = source[source.index('"/balance/{miner_pk}"'):]
    wallet_path = balance_path.index('"/wallet/balance"')
    balance_entry = balance_path[:wallet_path]

    assert '"balance_rtc": {"type": "number"}' in balance_entry
    assert '"pending_rewards": {"type": "number"}' not in balance_entry
