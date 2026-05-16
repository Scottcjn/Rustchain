# SPDX-License-Identifier: MIT

import hashlib
import importlib
import sys
import types
from pathlib import Path


RUSTCHAIN_CORE = Path(__file__).resolve().parents[1] / "rips" / "rustchain-core"
PACKAGE_NAME = "rustchain_core_exec_hash_testpkg"


def load_governance_module():
    package = sys.modules.get(PACKAGE_NAME)
    if package is None:
        package = types.ModuleType(PACKAGE_NAME)
        package.__path__ = [str(RUSTCHAIN_CORE)]
        sys.modules[PACKAGE_NAME] = package
    return importlib.import_module(f"{PACKAGE_NAME}.governance.proposals")


def test_execute_proposal_hash_includes_nonce(monkeypatch):
    proposals = load_governance_module()
    engine = proposals.GovernanceEngine()
    proposal = engine.create_proposal(
        title="Upgrade execution hash entropy",
        description="Ensure governance execution hashes are not predictable",
        proposal_type=proposals.ProposalType.PARAMETER_CHANGE,
        proposer="RTC1Proposer",
    )
    proposal.status = proposals.ProposalStatus.PASSED

    nonce_one = b"a" * 32
    nonce_two = b"b" * 32
    monkeypatch.setattr(proposals.time, "time", lambda: 1_768_000_000)
    nonces = iter([nonce_one, nonce_two])
    monkeypatch.setattr(
        proposals,
        "secrets",
        types.SimpleNamespace(token_bytes=lambda size: next(nonces)),
        raising=False,
    )

    first_hash = engine.execute_proposal(proposal.id)

    proposal.status = proposals.ProposalStatus.PASSED
    proposal.executed_at = None
    proposal.execution_tx_hash = None

    second_hash = engine.execute_proposal(proposal.id)

    assert first_hash == hashlib.sha256(
        f"{proposal.id}:1768000000".encode() + nonce_one
    ).hexdigest()
    assert second_hash == hashlib.sha256(
        f"{proposal.id}:1768000000".encode() + nonce_two
    ).hexdigest()
    assert first_hash != second_hash
