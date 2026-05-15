# SPDX-License-Identifier: MIT

import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = REPO_ROOT / "rips" / "rustchain-core"


def load_governance_module():
    package = types.ModuleType("rustchain_core")
    package.__path__ = [str(CORE_ROOT)]
    governance_package = types.ModuleType("rustchain_core.governance")
    governance_package.__path__ = [str(CORE_ROOT / "governance")]
    config_package = types.ModuleType("rustchain_core.config")
    config_package.__path__ = [str(CORE_ROOT / "config")]

    sys.modules.setdefault("rustchain_core", package)
    sys.modules.setdefault("rustchain_core.governance", governance_package)
    sys.modules.setdefault("rustchain_core.config", config_package)

    spec = importlib.util.spec_from_file_location(
        "rustchain_core.governance.proposals",
        CORE_ROOT / "governance" / "proposals.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


governance = load_governance_module()


def create_voting_proposal(engine):
    proposal = engine.create_proposal(
        title="Add deterministic validation",
        description="Governance test proposal",
        proposal_type=governance.ProposalType.COMMUNITY,
        proposer="RTC-proposer",
    )
    proposal.status = governance.ProposalStatus.VOTING
    proposal.voting_starts_at = 1
    proposal.voting_ends_at = 2**63 - 1
    return proposal


def test_vote_requires_local_balance_verification():
    engine = governance.GovernanceEngine()
    proposal = create_voting_proposal(engine)

    with pytest.raises(ValueError, match="Token balance verification required"):
        engine.vote(proposal.id, "RTC-voter", True, token_balance=1_000_000_000)


def test_vote_rejects_caller_supplied_balance_mismatch():
    engine = governance.GovernanceEngine(token_balance_resolver=lambda voter: 100)
    proposal = create_voting_proposal(engine)

    with pytest.raises(ValueError, match="Token balance mismatch"):
        engine.vote(proposal.id, "RTC-voter", True, token_balance=1_000_000_000)


def test_vote_uses_verified_balance_for_weight():
    engine = governance.GovernanceEngine(token_balance_resolver=lambda voter: 100)
    proposal = create_voting_proposal(engine)

    vote = engine.vote(proposal.id, "RTC-voter", True, token_balance=100)

    assert vote.weight == 110


def test_sophia_evaluate_requires_authorized_actor():
    engine = governance.GovernanceEngine()
    proposal = engine.create_proposal(
        title="Review me",
        description="Needs Sophia review",
        proposal_type=governance.ProposalType.COMMUNITY,
        proposer="RTC-proposer",
    )

    with pytest.raises(ValueError, match="Sophia evaluation authorization required"):
        engine.sophia_evaluate(
            proposal.id,
            governance.SophiaDecision.VETO,
            "unauthorized veto attempt",
        )


def test_sophia_evaluator_supplies_authorized_actor():
    engine = governance.GovernanceEngine()
    proposal = engine.create_proposal(
        title="Low risk community update",
        description="Needs Sophia review",
        proposal_type=governance.ProposalType.COMMUNITY,
        proposer="RTC-proposer",
    )
    sophia = governance.SophiaEvaluator(engine)

    evaluation = sophia.evaluate(proposal.id)

    assert evaluation.decision is governance.SophiaDecision.ENDORSE
    assert proposal.status is governance.ProposalStatus.VOTING


def test_sophia_evaluator_cannot_override_engine_authorizer():
    engine = governance.GovernanceEngine(
        sophia_authorizer=lambda actor: actor == "sophia"
    )
    proposal = engine.create_proposal(
        title="Low risk community update",
        description="Needs Sophia review",
        proposal_type=governance.ProposalType.COMMUNITY,
        proposer="RTC-proposer",
    )
    sophia = governance.SophiaEvaluator(engine, actor_id="evil")

    with pytest.raises(ValueError, match="Sophia evaluation authorization required"):
        sophia.evaluate(proposal.id)
