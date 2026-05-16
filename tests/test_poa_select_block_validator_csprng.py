# SPDX-License-Identifier: MIT

from rustchain.core_types import HardwareInfo, WalletAddress
from rustchain import proof_of_antiquity as poa


def _proof(wallet: str, score: float) -> poa.ValidatedProof:
    return poa.ValidatedProof(
        wallet=WalletAddress(wallet),
        hardware=HardwareInfo(cpu_model="PowerPC G4", release_year=2002),
        antiquity_score=score,
        anti_emulation_hash="hash",
        validated_at=1,
    )


def test_select_block_validator_zero_score_uses_csprng_randbelow(monkeypatch):
    calls = []

    def fake_randbelow(limit):
        calls.append(limit)
        return 1

    monkeypatch.setattr(poa.secrets, "randbelow", fake_randbelow)
    proofs = [
        _proof("RTC0000000000000000000000000000000000000000", 0),
        _proof("RTC1111111111111111111111111111111111111111", 0),
    ]

    selected = poa.select_block_validator(proofs)

    assert selected is proofs[1]
    assert calls == [2]


def test_select_block_validator_weighted_path_uses_csprng_randbits(monkeypatch):
    calls = []

    def fake_randbits(bits):
        calls.append(bits)
        return int(0.5 * (1 << bits))

    monkeypatch.setattr(poa.secrets, "randbits", fake_randbits)
    proofs = [
        _proof("RTC0000000000000000000000000000000000000000", 1.0),
        _proof("RTC2222222222222222222222222222222222222222", 2.0),
    ]

    selected = poa.select_block_validator(proofs)

    assert selected is proofs[1]
    assert calls == [53]


def test_select_block_validator_tiny_positive_weights_remain_probabilistic(monkeypatch):
    calls = []

    def fake_randbits(bits):
        calls.append(bits)
        return int(0.75 * (1 << bits))

    monkeypatch.setattr(poa.secrets, "randbits", fake_randbits)
    proofs = [
        _proof("RTC0000000000000000000000000000000000000000", 1e-12),
        _proof("RTC3333333333333333333333333333333333333333", 1e-12),
    ]

    selected = poa.select_block_validator(proofs)

    assert selected is proofs[1]
    assert calls == [53]
