"""Minimal reference models of the RustChain consensus rules under test.

These are *pins*: deliberately small, readable re-implementations of the rules
that the real node must obey. An example invariant test exercises the model
adversarially; when the production code diverges from a rule, the rule is
ported here and the corresponding invariant starts failing loudly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set


class ConsensusError(Exception):
    pass


# --- emission -------------------------------------------------------------

@dataclass(frozen=True)
class EmissionSchedule:
    """Declared emission: `base` RTC per epoch, halving every `halving` epochs."""

    base: int = 50
    halving: int = 100

    def declared_for_epoch(self, epoch: int) -> int:
        if epoch < 0:
            raise ConsensusError("epoch must be non-negative")
        return self.base >> (epoch // self.halving)


@dataclass
class RewardLedger:
    schedule: EmissionSchedule = field(default_factory=EmissionSchedule)
    minted: Dict[int, int] = field(default_factory=dict)

    def mint_epoch(self, epoch: int, shares: Dict[str, int]) -> Dict[str, int]:
        """Split the declared emission across miners by share weight.

        Remainder from integer division is assigned deterministically (sorted
        miner order) so the sum always equals the declared emission exactly.
        """
        if epoch in self.minted:
            raise ConsensusError(f"epoch {epoch} already minted")
        total = self.schedule.declared_for_epoch(epoch)
        weight = sum(shares.values())
        if weight <= 0:
            raise ConsensusError("no positive shares for epoch")
        payouts: Dict[str, int] = {}
        for miner in sorted(shares):
            payouts[miner] = total * shares[miner] // weight
        remainder = total - sum(payouts.values())
        for miner in sorted(shares):
            if remainder == 0:
                break
            payouts[miner] += 1
            remainder -= 1
        self.minted[epoch] = sum(payouts.values())
        return payouts


# --- enrollment -----------------------------------------------------------

@dataclass
class MinerRegistry:
    """Enrollment set keyed by canonical (lowercased) wallet address."""

    _enrolled: Set[str] = field(default_factory=set)

    @staticmethod
    def canonical(address: str) -> str:
        addr = address.strip().lower()
        if not addr.startswith("0x") or len(addr) != 42:
            raise ConsensusError(f"malformed address: {address!r}")
        return addr

    def enroll(self, address: str) -> bool:
        addr = self.canonical(address)
        if addr in self._enrolled:
            return False
        self._enrolled.add(addr)
        return True

    def enroll_many(self, addresses: Iterable[str]) -> List[bool]:
        return [self.enroll(a) for a in addresses]

    def __len__(self) -> int:
        return len(self._enrolled)


# --- settlement -----------------------------------------------------------

@dataclass
class Settlement:
    """Idempotent settlement: each payout id may only move balance once."""

    balances: Dict[str, int] = field(default_factory=dict)
    applied: Set[str] = field(default_factory=set)

    def settle(self, payout_id: str, address: str, amount: int) -> bool:
        if amount < 0:
            raise ConsensusError("negative settlement amount")
        if payout_id in self.applied:
            return False
        self.applied.add(payout_id)
        self.balances[address] = self.balances.get(address, 0) + amount
        return True
