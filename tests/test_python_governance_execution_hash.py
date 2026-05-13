# SPDX-License-Identifier: MIT

import hashlib
import sys
from pathlib import Path


PYTHON_RIPS = Path(__file__).resolve().parents[1] / "rips" / "python"
sys.path.insert(0, str(PYTHON_RIPS))

from rustchain.core_types import WalletAddress  # noqa: E402
from rustchain.governance import GovernanceEngine, ProposalStatus, ProposalType  # noqa: E402


def test_python_governance_execution_hash_uses_nonce(monkeypatch):
    engine = GovernanceEngine(total_supply=1_000_000)
    proposal = engine.create_proposal(
        title="Upgrade treasury policy",
        description="Execute a deterministic-time governance action",
        proposal_type=ProposalType.PARAMETER_CHANGE,
        proposer=WalletAddress("RTC1234567890abcdef1234567890abcdef12345678"),
    )
    proposal.status = ProposalStatus.PASSED

    nonce_one = b"a" * 32
    nonce_two = b"b" * 32
    monkeypatch.setattr("rustchain.governance.time.time", lambda: 1_768_000_000)
    nonces = iter([nonce_one, nonce_two])
    monkeypatch.setattr("rustchain.governance.secrets.token_bytes", lambda size: next(nonces))

    assert engine.execute_proposal(proposal.id) is True
    first_hash = proposal.execution_tx_hash

    proposal.status = ProposalStatus.PASSED
    proposal.executed_at = None
    proposal.execution_tx_hash = None

    assert engine.execute_proposal(proposal.id) is True
    second_hash = proposal.execution_tx_hash

    assert first_hash == hashlib.sha256(
        f"{proposal.id}:1768000000".encode() + nonce_one
    ).hexdigest()
    assert second_hash == hashlib.sha256(
        f"{proposal.id}:1768000000".encode() + nonce_two
    ).hexdigest()
    assert first_hash != second_hash
