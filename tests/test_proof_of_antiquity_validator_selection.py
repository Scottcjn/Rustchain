# SPDX-License-Identifier: MIT

from rustchain.core_types import HardwareInfo, WalletAddress
from rustchain import proof_of_antiquity


def _proof(wallet_suffix, antiquity_score):
    return proof_of_antiquity.ValidatedProof(
        wallet=WalletAddress(f"RTC{wallet_suffix}"),
        hardware=HardwareInfo(cpu_model="PowerMac G4", release_year=2002),
        antiquity_score=antiquity_score,
        anti_emulation_hash=f"hash-{wallet_suffix}",
        validated_at=1,
    )


class TrackingSecureRandom:
    def __init__(self, weighted_pick):
        self.weighted_pick = weighted_pick
        self.choice_calls = []
        self.uniform_calls = []

    def choice(self, values):
        self.choice_calls.append(list(values))
        return values[-1]

    def uniform(self, start, end):
        self.uniform_calls.append((start, end))
        return self.weighted_pick


def test_select_block_validator_uses_secure_choice_for_zero_scores(monkeypatch):
    rng = TrackingSecureRandom(weighted_pick=0)
    monkeypatch.setattr(proof_of_antiquity, "_SECURE_RANDOM", rng)
    proofs = [_proof("zeroA", 0), _proof("zeroB", 0)]

    selected = proof_of_antiquity.select_block_validator(proofs)

    assert selected is proofs[-1]
    assert rng.choice_calls == [proofs]
    assert rng.uniform_calls == []


def test_select_block_validator_uses_secure_weighted_pick(monkeypatch):
    rng = TrackingSecureRandom(weighted_pick=6.0)
    monkeypatch.setattr(proof_of_antiquity, "_SECURE_RANDOM", rng)
    proofs = [_proof("low", 5.0), _proof("high", 10.0)]

    selected = proof_of_antiquity.select_block_validator(proofs)

    assert selected is proofs[1]
    assert rng.choice_calls == []
    assert rng.uniform_calls == [(0, 15.0)]
