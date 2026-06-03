# SPDX-License-Identifier: MIT

import importlib
import sys
import types
from pathlib import Path

import pytest


RUSTCHAIN_CORE = Path(__file__).resolve().parents[1] / "rips" / "rustchain-core"
PACKAGE_NAME = "rustchain_core_testpkg"


def load_governance_module():
    package = sys.modules.get(PACKAGE_NAME)
    if package is None:
        package = types.ModuleType(PACKAGE_NAME)
        package.__path__ = [str(RUSTCHAIN_CORE)]
        sys.modules[PACKAGE_NAME] = package
    return importlib.import_module(f"{PACKAGE_NAME}.governance.proposals")


def test_delegate_voting_power_rejects_legacy_unauthenticated_call():
    proposals = load_governance_module()
    engine = proposals.GovernanceEngine()

    with pytest.raises(TypeError):
        engine.delegate_voting_power("RTC1Victim", "RTC1Attacker", 1.0)

    assert engine.delegations == {}


def test_delegate_voting_power_rejects_mismatched_authenticated_wallet():
    proposals = load_governance_module()
    engine = proposals.GovernanceEngine()

    with pytest.raises(ValueError, match="authenticated_wallet must match from_wallet"):
        engine.delegate_voting_power(
            "RTC1Victim",
            "RTC1Attacker",
            1.0,
            authenticated_wallet="RTC1Attacker",
        )

    assert engine.delegations == {}


def test_delegate_voting_power_rejects_self_supplied_caller_wallet_keyword():
    proposals = load_governance_module()
    engine = proposals.GovernanceEngine()

    with pytest.raises(TypeError):
        engine.delegate_voting_power(
            "RTC1Victim",
            "RTC1Attacker",
            1.0,
            caller_wallet="RTC1Victim",
        )

    assert engine.delegations == {}


def test_delegate_voting_power_accepts_owner_authenticated_wallet():
    proposals = load_governance_module()
    engine = proposals.GovernanceEngine()

    delegation = engine.delegate_voting_power(
        "RTC1Owner",
        "RTC1Delegate",
        0.5,
        authenticated_wallet="RTC1Owner",
        duration_days=7,
    )

    assert delegation.from_wallet == "RTC1Owner"
    assert delegation.to_wallet == "RTC1Delegate"
    assert delegation.weight == 0.5
    assert engine.delegations["RTC1Delegate"] == [delegation]
