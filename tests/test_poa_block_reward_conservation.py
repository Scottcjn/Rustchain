# SPDX-License-Identifier: MIT
"""Regression tests for block-reward conservation in ProofOfAntiquity.process_block.

A block must mint exactly one BLOCK_REWARD, split proportionally among the
participating miners (per the reference formula `miner_reward = BLOCK_REWARD *
miner_share`, rips/src/proof_of_antiquity.rs). It must NOT scale the emission by
the number of miners: doing so over-mints the finite mining pool and inflates
total supply past the cap.
"""

from rustchain.core_types import HardwareInfo, WalletAddress
from rustchain import proof_of_antiquity as poa


def _proof(idx: int, score: float) -> poa.ValidatedProof:
    return poa.ValidatedProof(
        wallet=WalletAddress("RTC" + f"{idx:040x}"),
        hardware=HardwareInfo(cpu_model="PowerPC G4", release_year=2002),
        antiquity_score=score,
        anti_emulation_hash="hash",
        validated_at=1,
    )


def _run_block(scores):
    poa_engine = poa.ProofOfAntiquity()
    poa_engine.pending_proofs = [_proof(i, s) for i, s in enumerate(scores)]
    return poa_engine.process_block("00" * 32)


def test_block_reward_does_not_scale_with_miner_count():
    """N equal-AS miners must still mint one block reward, not N of them.

    On the buggy implementation each miner's reward is computed independently
    against the whole block reward and multiplied by the miner count, so a
    100-miner block mints ~80x the block reward. This asserts the invariant
    that the emission never exceeds a single block reward.
    """
    cap = poa.BLOCK_REWARD_AMOUNT.amount
    for n in (1, 2, 5, 100):
        block = _run_block([80.0] * n)
        assert block.total_reward.amount <= cap, (
            f"{n} miners over-minted: {block.total_reward.amount} > {cap}"
        )


def test_block_reward_split_is_proportional_and_conserved():
    """Rewards split by AS share and sum to (at most) one block reward."""
    cap = poa.BLOCK_REWARD_AMOUNT.amount
    block = _run_block([75.0, 25.0])  # shares 0.75 / 0.25

    total = sum(m.reward.amount for m in block.miners)
    assert total == block.total_reward.amount
    assert total <= cap
    # Higher AS earns the larger slice; ratio tracks the 3:1 AS split.
    high, low = block.miners[0].reward.amount, block.miners[1].reward.amount
    assert high > low
    assert high == 3 * low
