# SPDX-License-Identifier: MIT
"""
Regression test for INV-5 (antiquity weighting) order-dependence bug.

INV-5 states: a miner with a strictly higher antiquity multiplier must never
earn FEWER uRTC than a miner with a lower multiplier in the same epoch. This is
an order-independent mathematical property.

The implementation in check_antiquity_weighting() only inspects the pair when
the *earlier-listed* miner has the higher multiplier:

        if ma.antiquity_multiplier > mb.antiquity_multiplier:
            if epoch.rewards[a] < epoch.rewards[b]:
                violations.append(...)

There is no symmetric branch for the case where the *later-listed* miner has
the higher multiplier. Because epoch.rewards is an insertion-ordered dict whose
key order follows the (arbitrary) miner attestation order, a genuine violation
is silently missed whenever the higher-multiplier miner happens to appear later
in the list. The "mathematical proof of ledger correctness" therefore has a
50% blind spot.
"""

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "ledger_invariants.py"
SPEC = importlib.util.spec_from_file_location("ledger_invariants", MODULE_PATH)
ledger_invariants = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger_invariants)


def _make_epoch(rewards, mults):
    """Build a settled Epoch with explicit rewards and per-miner multipliers."""
    miners = [
        ledger_invariants.Miner(wallet_name=name, antiquity_multiplier=mults[name],
                                last_attest=100)
        for name in rewards
    ]
    return ledger_invariants.Epoch(epoch_num=1, miners=miners, rewards=dict(rewards),
                                   settled=True)


def test_inv5_detects_violation_regardless_of_listing_order():
    # Genuine INV-5 violation: "high" has DOUBLE the multiplier of "low"
    # but is paid strictly LESS. This must be flagged no matter the ordering.
    mults = {"low": 1.0, "high": 2.0}

    # Case A: higher-multiplier miner listed FIRST -> currently detected.
    ledger_a = ledger_invariants.SimulatedLedger()
    ledger_a.epochs.append(_make_epoch({"high": 600_000, "low": 900_000}, mults))
    assert ledger_a.check_antiquity_weighting(), \
        "sanity: violation with higher-mult miner first should be detected"

    # Case B: identical violation, but higher-multiplier miner listed SECOND.
    # On current main this returns [] -> the real violation is MISSED.
    ledger_b = ledger_invariants.SimulatedLedger()
    ledger_b.epochs.append(_make_epoch({"low": 900_000, "high": 600_000}, mults))
    viols = ledger_b.check_antiquity_weighting()
    assert viols, (
        "INV-5 must flag that 'high' (mult=2.0) earned 600000 uRTC < "
        "'low' (mult=1.0) 900000 uRTC, independent of miner listing order"
    )
