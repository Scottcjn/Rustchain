# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "ledger_invariants.py"
SPEC = importlib.util.spec_from_file_location("ledger_invariants", MODULE_PATH)
ledger_invariants = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger_invariants)


def test_settle_epoch_handles_zero_total_multiplier():
    ledger = ledger_invariants.SimulatedLedger()
    miners = [
        ledger_invariants.Miner("alice", 0.0, 100),
        ledger_invariants.Miner("bob", 0.0, 100),
    ]

    epoch = ledger.settle_epoch(1, miners, 100)

    assert epoch.settled is True
    assert epoch.rewards == {}
    assert ledger.total_minted_urtc == 0
