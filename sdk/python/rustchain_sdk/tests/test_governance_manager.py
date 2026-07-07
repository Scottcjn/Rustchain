"""
Tests for high-level governance signing helpers.
"""

import json

import pytest

from rustchain_sdk import GovernanceManager
from rustchain_sdk.exceptions import GovernanceError, ValidationError


class DummyWallet:
    address = "RTCvoter123"
    public_key_hex = "ab" * 32

    def __init__(self):
        self.messages = []

    def sign(self, message):
        self.messages.append(message)
        return b"\x11" * 64


class DummyClient:
    def __init__(self):
        self.vote_calls = []
        self.propose_calls = []

    async def governance_vote(self, voter, proposal_id, vote, signature):
        self.vote_calls.append(
            {
                "voter": voter,
                "proposal_id": proposal_id,
                "vote": vote,
                "signature": signature,
            }
        )
        return {"result": "accepted", "proposal_id": proposal_id, "vote": vote}

    async def governance_propose(self, proposer, proposal_type, description, payload):
        self.propose_calls.append(
            {
                "proposer": proposer,
                "proposal_type": proposal_type,
                "description": description,
                "payload": payload,
            }
        )
        return {"proposal_id": 7, "status": "submitted"}


def test_vote_message_is_canonical_and_domain_separated():
    message = GovernanceManager.vote_message(
        voter="RTCvoter123",
        proposal_id=42,
        vote="YES",
        nonce=1700000000,
    )

    assert json.loads(message) == {
        "domain": "rustchain.governance.vote.v1",
        "nonce": 1700000000,
        "proposal_id": 42,
        "vote": "yes",
        "voter": "RTCvoter123",
    }
    assert message == (
        b'{"domain":"rustchain.governance.vote.v1","nonce":1700000000,'
        b'"proposal_id":42,"vote":"yes","voter":"RTCvoter123"}'
    )


def test_sign_vote_returns_payload_with_signature_and_public_key():
    wallet = DummyWallet()
    manager = GovernanceManager(DummyClient(), wallet)

    payload = manager.sign_vote(42, "No", nonce=123)

    assert payload == {
        "voter": "RTCvoter123",
        "proposal_id": 42,
        "vote": "no",
        "signature": (b"\x11" * 64).hex(),
        "public_key": "ab" * 32,
        "nonce": 123,
    }
    assert json.loads(wallet.messages[0])["vote"] == "no"


@pytest.mark.asyncio
async def test_vote_signs_and_submits_to_client():
    wallet = DummyWallet()
    client = DummyClient()
    manager = GovernanceManager(client, wallet)

    result = await manager.vote(9, "abstain")

    assert result == {"result": "accepted", "proposal_id": 9, "vote": "abstain"}
    assert client.vote_calls == [
        {
            "voter": "RTCvoter123",
            "proposal_id": 9,
            "vote": "abstain",
            "signature": (b"\x11" * 64).hex(),
        }
    ]


@pytest.mark.asyncio
async def test_propose_uses_wallet_address_as_proposer():
    client = DummyClient()
    manager = GovernanceManager(client, DummyWallet())

    result = await manager.propose(
        proposal_type="param_change",
        description="Lower test quorum",
        payload={"key": "quorum", "value": 0.4},
    )

    assert result == {"proposal_id": 7, "status": "submitted"}
    assert client.propose_calls == [
        {
            "proposer": "RTCvoter123",
            "proposal_type": "param_change",
            "description": "Lower test quorum",
            "payload": {"key": "quorum", "value": 0.4},
        }
    ]


@pytest.mark.parametrize("proposal_id", [0, -1, "1"])
def test_vote_rejects_invalid_proposal_id(proposal_id):
    manager = GovernanceManager(DummyClient(), DummyWallet())

    with pytest.raises(ValidationError, match="proposal_id"):
        manager.sign_vote(proposal_id, "yes")


@pytest.mark.parametrize("vote", ["", "maybe", 1])
def test_vote_rejects_invalid_choice(vote):
    manager = GovernanceManager(DummyClient(), DummyWallet())

    with pytest.raises(ValidationError, match="vote"):
        manager.sign_vote(1, vote)


def test_init_requires_wallet_sign_method():
    class NoSignWallet:
        address = "RTCvoter123"

    with pytest.raises(ValidationError, match="wallet.sign"):
        GovernanceManager(DummyClient(), NoSignWallet())


@pytest.mark.asyncio
async def test_vote_wraps_client_errors_as_governance_error():
    class FailingClient(DummyClient):
        async def governance_vote(self, voter, proposal_id, vote, signature):
            raise RuntimeError("node rejected")

    manager = GovernanceManager(FailingClient(), DummyWallet())

    with pytest.raises(GovernanceError, match="node rejected"):
        await manager.vote(1, "yes")
