"""
High-level governance helpers for RustChain.

The low-level client exposes governance endpoints, while RustChainWallet owns
the signing key. GovernanceManager ties the two together without requiring
callers to hand-build or remember the canonical vote payload.
"""

import json
from typing import Any, Dict, Optional

from .exceptions import GovernanceError, ValidationError


class GovernanceManager:
    """Sign and submit governance actions with a RustChain wallet."""

    VOTE_DOMAIN = "rustchain.governance.vote.v1"
    VALID_VOTES = frozenset({"yes", "no", "abstain"})

    def __init__(self, client: Any, wallet: Any):
        if client is None:
            raise ValidationError("client is required")
        if wallet is None:
            raise ValidationError("wallet is required")
        if not getattr(wallet, "address", None):
            raise ValidationError("wallet.address is required")
        if not callable(getattr(wallet, "sign", None)):
            raise ValidationError("wallet.sign(message) is required")

        self.client = client
        self.wallet = wallet

    @classmethod
    def vote_message(
        cls,
        voter: str,
        proposal_id: int,
        vote: str,
        nonce: Optional[int] = None,
    ) -> bytes:
        """Build the canonical byte payload signed for a governance vote."""
        cls._validate_voter(voter)
        cls._validate_proposal_id(proposal_id)
        vote_value = cls._normalize_vote(vote)

        payload: Dict[str, Any] = {
            "domain": cls.VOTE_DOMAIN,
            "proposal_id": int(proposal_id),
            "vote": vote_value,
            "voter": voter,
        }
        if nonce is not None:
            if not isinstance(nonce, int) or nonce < 0:
                raise ValidationError("nonce must be a non-negative integer")
            payload["nonce"] = nonce

        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign_vote(
        self,
        proposal_id: int,
        vote: str,
        nonce: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Return a signed governance vote payload without submitting it.

        This is useful for dry-runs, audit logs, and tests. The public key is
        included for callers that need to show which wallet key produced the
        signature, even though the current low-level endpoint only requires the
        signature string.
        """
        vote_value = self._normalize_vote(vote)
        message = self.vote_message(self.wallet.address, proposal_id, vote_value, nonce=nonce)
        try:
            signature = self.wallet.sign(message)
        except Exception as exc:
            raise GovernanceError(f"Failed to sign governance vote: {exc}") from exc

        payload: Dict[str, Any] = {
            "voter": self.wallet.address,
            "proposal_id": int(proposal_id),
            "vote": vote_value,
            "signature": signature.hex(),
        }
        public_key = getattr(self.wallet, "public_key_hex", None)
        if public_key:
            payload["public_key"] = public_key
        if nonce is not None:
            payload["nonce"] = nonce
        return payload

    async def vote(
        self,
        proposal_id: int,
        vote: str,
        nonce: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Sign and submit a governance vote through the wrapped client."""
        payload = self.sign_vote(proposal_id, vote, nonce=nonce)
        try:
            return await self.client.governance_vote(
                voter=payload["voter"],
                proposal_id=payload["proposal_id"],
                vote=payload["vote"],
                signature=payload["signature"],
            )
        except Exception as exc:
            raise GovernanceError(f"Failed to submit governance vote: {exc}") from exc

    async def propose(
        self,
        proposal_type: str,
        description: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Submit a governance proposal using the wallet address as proposer."""
        if not proposal_type or not isinstance(proposal_type, str):
            raise ValidationError("proposal_type must be a non-empty string")
        if not description or not isinstance(description, str):
            raise ValidationError("description must be a non-empty string")
        if not isinstance(payload, dict):
            raise ValidationError("payload must be a dict")

        try:
            return await self.client.governance_propose(
                proposer=self.wallet.address,
                proposal_type=proposal_type,
                description=description,
                payload=payload,
            )
        except Exception as exc:
            raise GovernanceError(f"Failed to submit governance proposal: {exc}") from exc

    @classmethod
    def _validate_voter(cls, voter: str) -> None:
        if not voter or not isinstance(voter, str):
            raise ValidationError("voter must be a non-empty string")

    @classmethod
    def _validate_proposal_id(cls, proposal_id: int) -> None:
        if not isinstance(proposal_id, int) or proposal_id <= 0:
            raise ValidationError("proposal_id must be a positive integer")

    @classmethod
    def _normalize_vote(cls, vote: str) -> str:
        if not isinstance(vote, str):
            raise ValidationError("vote must be a string")
        vote_value = vote.strip().lower()
        if vote_value not in cls.VALID_VOTES:
            choices = ", ".join(sorted(cls.VALID_VOTES))
            raise ValidationError(f"vote must be one of: {choices}")
        return vote_value
