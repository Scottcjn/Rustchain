# SPDX-License-Identifier: MIT
"""Known historical balance-vs-ledger differences, frozen at the exact unit.

/pending/integrity compares every wallet's balance to the sum of its ledger
rows. Twenty-four wallets have differed since before 2026-09-26, all from
writers that moved balances without writing ledger rows (or wrote one side of
a correction). Left in the report, those 24 made the check fail on every run,
so a *new* discrepancy would be one more line in a list nobody reads.

Each entry below is the wallet's exact difference ``balance - ledger_sum`` in
micro-RTC, as measured on node 1 on 2026-09-26 and confirmed unchanged against
the 15:54Z off-box backup nine hours earlier (several payouts ran in between).

This is a baseline, not an exemption: a listed wallet whose difference moves by
even one unit is reported again, and any wallet not listed is reported as
before. Nothing here edits balances or the ledger.
"""

GHOST_ZEROING = ("2026-02-06 'zeroed: ghost balance, no audit trail': the debit "
                 "was logged, the balance it removed never had ledger credits")
NODE_REWARDS_100X = ("2026-08-20 correction of the node_rewards.py 100x overpay: "
                     "the overpaid credits hit balances with no ledger rows, the "
                     "correction debit did (node_rewards.py pays via "
                     "/wallet/transfer since)")
CREATEKR_DOUBLE_CONSOLIDATION = ("2026-02-25 createkr wallet consolidation was "
                                 "written to the ledger twice (03:21:55 and "
                                 "03:22:11); balances were moved once")
AGENT_JOBS = ("agent_jobs market settled escrow and payouts directly in balances "
              "without ledger rows (last completed job 2026-07-03)")
NOT_TRACED = ("not yet traced to a writer; frozen so it cannot grow unseen "
              "(the wallet has ledger activity through 2026-09-26)")

# miner_id -> (balance - ledger_sum in micro-RTC, reason)
KNOWN_LEGACY_DRIFT = {
    "38c9cd9971971d71b1f920faba42d3fa9610cbeeRTC": (2180555555, GHOST_ZEROING),
    "55ccb35c07c306e7b5c5e029f75db281b07a0f0599f6b3cfa133d1f6320ad8d4": (225000000, GHOST_ZEROING),
    "g4-powerbook-01": (75000000, GHOST_ZEROING),
    "gurgguda": (185000000, GHOST_ZEROING + "; the bounty #6 40 RTC lost with the "
                 "balance row was re-sent 2026-09-26 as pending 5157"),
    "9fd582ec147e58c241de383b20bff8ca4650be6bRTC": (5516666666, GHOST_ZEROING + "; and " + NODE_REWARDS_100X),
    "b4c7aee57c1cf06b925cbea6d6d5ec632e2a26c9RTC": (24599984827, GHOST_ZEROING + "; and " + NODE_REWARDS_100X),
    "2599ea4477fcb08e92215da5c5c92035867cf7RTC": (10727006021, NODE_REWARDS_100X),
    "frozen-factorio-ryan": (10463342705, NODE_REWARDS_100X),
    "RTCe1c4d2cae51372cd416fc42a84b00a7830e5ffec": (1500000000, "2025-12-06 pre-launch "
                                                    "'Test signed transfer' from an address with no ledger credits"),
    "createker": (25000000, CREATEKR_DOUBLE_CONSOLIDATION),
    "createker-rtc-1771000911": (75000000, CREATEKR_DOUBLE_CONSOLIDATION),
    "createker02140054RTC": (374070381, CREATEKR_DOUBLE_CONSOLIDATION),
    "createkr-wallet": (314000000, CREATEKR_DOUBLE_CONSOLIDATION),
    "RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35": (6000000, CREATEKR_DOUBLE_CONSOLIDATION
                                                    + " (this is the destination)"),
    "agent_escrow": (-49339500, AGENT_JOBS),
    "hermes-agent": (87975000, AGENT_JOBS),
    "BenItBuhner": (73000000, AGENT_JOBS),
    "0x840412fB7A02146d6B5478F82029c20E29EAB9a4": (122000000, AGENT_JOBS),
    "RTC66fdcfa23de859105a6065398d11bfe6b4eceab9": (10000000, AGENT_JOBS),
    "founder_community": (-266465500, "net of historical writers that debited the "
                          "pool balance without ledger rows; agent_jobs payouts are "
                          "one confirmed source, the full split is not yet traced"),
    "hermes-agent-2": (500000, "welcome bonus credited to balances without a ledger row"),
    "RTC14f06ee294f327f5685d3de5e1ed501cffab33e7": (8000000, NOT_TRACED),
    "victus-x86-scott": (8330000, NOT_TRACED),
    "modern-sophiacore-3a168058": (-2000, NOT_TRACED),
}


def classify(miner_id, diff_i64):
    """Return (reason, baseline_i64) when this exact difference is known, else None."""
    known = KNOWN_LEGACY_DRIFT.get(miner_id)
    if known is not None and known[0] == diff_i64:
        return known[1], known[0]
    return None
