#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Epoch settlement logic for RustChain reward distribution.

Each epoch (runs every ~10 minutes) distributes exactly 1.5 RTC across all
eligible miners, weighted by their antiquity multiplier.  The antiquity
multiplier rewards owners of older / rarer hardware — values come from the
Rust reference implementation in rustchain-miner/src/hardware/arch.rs.

Precision guarantee
-------------------
All arithmetic is performed with Python's ``decimal.Decimal`` at 50
significant figures so that rounding errors never silently compound.  The
final step normalises the total to *exactly* EPOCH_REWARD_RTC using integer
satoshi arithmetic (1 RTC == 1_000_000 satoshis, matching the 6-decimal
precision of the wRTC ERC-20 on Base).

Public API
----------
``calculate_epoch_rewards_time_aged(miners)``
    Given a sequence of ``{"miner_id": str, "multiplier": float|Decimal}``
    dicts return a dict mapping miner_id → satoshis (int).
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_DOWN, localcontext
from typing import Any, Dict, List, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Total RTC emitted per epoch (1.5 RTC expressed as a Decimal).
EPOCH_REWARD_RTC: Decimal = Decimal("1.5")

#: Satoshis per RTC (6 decimal places, matching wRTC ERC-20 on Base).
SATOSHIS_PER_RTC: int = 1_000_000

#: Total satoshis available per epoch.
EPOCH_REWARD_SATOSHIS: int = int(EPOCH_REWARD_RTC * SATOSHIS_PER_RTC)  # 1_500_000

#: Valid antiquity multiplier range (inclusive).
MULTIPLIER_MIN: Decimal = Decimal("0")
MULTIPLIER_MAX: Decimal = Decimal("1000")

# ---------------------------------------------------------------------------
# Known hardware multipliers (mirrors rustchain-miner/src/hardware/arch.rs)
# ---------------------------------------------------------------------------

ARCH_MULTIPLIERS: Dict[str, float] = {
    "g4": 2.5,
    "g5": 2.0,
    "g3": 1.8,
    "apple_silicon": 1.2,
    "core2duo": 1.3,
    "modern": 1.0,
}


# ---------------------------------------------------------------------------
# Core settlement function
# ---------------------------------------------------------------------------


def calculate_epoch_rewards_time_aged(
    miners: Sequence[Dict[str, Any]],
) -> Dict[str, int]:
    """Distribute EPOCH_REWARD_SATOSHIS (1.5 RTC) across *miners* by weight.

    Each miner entry must have:
        ``miner_id`` (str) — unique identifier
        ``multiplier`` (float | int | Decimal | str) — antiquity weight ≥ 0

    Returns
    -------
    dict
        ``{miner_id: satoshis}`` mapping.  Every value is a non-negative int.
        The sum of all values is exactly ``EPOCH_REWARD_SATOSHIS`` (1 500 000),
        or 0 if *miners* is empty.

    Raises
    ------
    ValueError
        If a miner has a negative multiplier, or if ``miner_id`` is missing /
        not a string.
    """
    if not miners:
        return {}

    with localcontext() as ctx:
        ctx.prec = 50  # far more than enough for any realistic miner count

        # --- Validate and collect weights ------------------------------------
        weights: List[Decimal] = []
        ids: List[str] = []

        for i, m in enumerate(miners):
            mid = m.get("miner_id")
            if not isinstance(mid, str) or not mid:
                raise ValueError(
                    f"miners[{i}] has missing or non-string miner_id: {mid!r}"
                )

            raw = m.get("multiplier", 1.0)
            try:
                w = Decimal(str(raw))
            except Exception as exc:
                raise ValueError(
                    f"miners[{i}] ({mid!r}) has invalid multiplier {raw!r}: {exc}"
                ) from exc

            if w < 0:
                raise ValueError(
                    f"miners[{i}] ({mid!r}) has negative multiplier {w}"
                )

            ids.append(mid)
            weights.append(w)

        total_weight = sum(weights)

        # Edge case: all multipliers are zero → give nothing to anyone.
        if total_weight == 0:
            return {mid: 0 for mid in ids}

        # --- Proportional allocation in satoshis (floor) --------------------
        reward_pool = Decimal(EPOCH_REWARD_SATOSHIS)
        raw_shares: List[Decimal] = [
            (w / total_weight * reward_pool) for w in weights
        ]

        # Floor each share to get integer satoshis
        floored: List[int] = [int(s.to_integral_value(rounding=ROUND_DOWN)) for s in raw_shares]
        distributed = sum(floored)
        remainder = EPOCH_REWARD_SATOSHIS - distributed  # 0 ≤ remainder < len(miners)

        # --- Largest-remainder method to distribute leftover satoshis -------
        # Sort indices by fractional part descending so the biggest remainders
        # get the extra satoshi first.  Ties broken by original order (stable).
        fractional = [raw_shares[j] - floored[j] for j in range(len(ids))]
        order = sorted(range(len(ids)), key=lambda j: fractional[j], reverse=True)
        for k in range(remainder):
            floored[order[k]] += 1

    return {ids[j]: floored[j] for j in range(len(ids))}
