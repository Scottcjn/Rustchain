"""Reference invariant tests. Each one pins exactly one stated invariant.

Copy any of these as the template for a new attractor submission.
"""

from __future__ import annotations

from .harness import Ctx, invariant
from .models import ConsensusError, EmissionSchedule, MinerRegistry, RewardLedger, Settlement


@invariant(
    id="INV-EMISSION-001",
    statement="rewards minted per epoch == declared emission for that epoch",
    scope="consensus/emission",
    adversarial=True,
)
def test_emission_conserved(ctx: Ctx) -> None:
    """Adversary: skewed share distributions that maximise rounding loss."""
    schedule = EmissionSchedule()
    adv = ctx.adversary("rounding-skew")
    for epoch in (0, 1, 99, 100, 250):
        ledger = RewardLedger(schedule)
        miners = [f"m{i}" for i in range(7)]
        shares = {m: adv.rng.choice([1, 1, 1, 2, 9973]) for m in miners}
        payouts = ledger.mint_epoch(epoch, shares)
        declared = schedule.declared_for_epoch(epoch)
        ctx.check(
            sum(payouts.values()) == declared,
            f"epoch {epoch}: minted {sum(payouts.values())} must equal declared {declared}",
        )
        ctx.check(
            all(v >= 0 for v in payouts.values()),
            f"epoch {epoch}: no payout may be negative",
        )
    # Hostile: double-minting the same epoch must be rejected, not silently doubled.
    ledger = RewardLedger(schedule)
    ledger.mint_epoch(3, {"a": 1})
    try:
        ledger.mint_epoch(3, {"a": 1})
        doubled = True
    except ConsensusError:
        doubled = False
    ctx.check(not doubled, "re-minting an already minted epoch must raise, not inflate supply")


@invariant(
    id="INV-ENROLL-002",
    statement="no miner can be enrolled twice, regardless of address casing or order",
    scope="consensus/enrollment",
    adversarial=True,
)
def test_no_double_enrollment(ctx: Ctx) -> None:
    """Adversary: replayed, reordered and case-mutated enrollment requests."""
    base = [f"0x{i:040x}" for i in range(1, 13)]
    adv = ctx.adversary("replay-case")
    hostile = adv.shuffle(adv.replay(base, times=3))
    hostile += [a.upper().replace("0X", "0x") for a in base]
    hostile = adv.shuffle(hostile)

    reg = MinerRegistry()
    accepted = reg.enroll_many(hostile)
    ctx.check(
        len(reg) == len(base),
        f"registry holds {len(reg)} miners; exactly {len(base)} unique miners were offered",
    )
    ctx.check(
        sum(accepted) == len(base),
        "exactly one enrollment per unique miner may be accepted",
    )
    try:
        reg.enroll("0xdeadbeef")
        rejected = False
    except ConsensusError:
        rejected = True
    ctx.check(rejected, "malformed addresses must be rejected instead of enrolled")


@invariant(
    id="INV-SETTLE-003",
    statement="settlement is idempotent: replaying a payout id never moves balance twice",
    scope="consensus/settlement",
    adversarial=True,
)
def test_settlement_idempotent(ctx: Ctx) -> None:
    """Adversary: replay storm interleaved with unrelated payouts."""
    adv = ctx.adversary("replay-storm")
    payouts = [(f"p{i}", f"0x{i:040x}", 10 + i) for i in range(1, 9)]
    stream = adv.shuffle(adv.replay(payouts, times=4))

    s = Settlement()
    for pid, addr, amt in stream:
        s.settle(pid, addr, amt)

    expected_total = sum(amt for _, _, amt in payouts)
    ctx.check(
        sum(s.balances.values()) == expected_total,
        f"total settled {sum(s.balances.values())} must equal {expected_total} despite 4x replay",
    )
    for pid, addr, amt in payouts:
        ctx.check(
            s.balances[addr] == amt,
            f"{addr} credited exactly once for {pid}",
        )
    ctx.check(
        s.settle("p1", "0x" + "1" * 40, 999) is False,
        "a re-settled payout id must report False and leave balances untouched",
    )
