# SPDX-License-Identifier: MIT
"""EIP-1559-compatible fee market helpers for RustChain."""

from dataclasses import dataclass
from typing import Optional

DEFAULT_BASE_FEE_NRTC = 1_000
DEFAULT_TARGET_GAS = 15_000_000
DEFAULT_ELASTICITY_MULTIPLIER = 2
DEFAULT_BASE_FEE_MAX_CHANGE_DENOMINATOR = 8


@dataclass(frozen=True)
class FeeBreakdown:
    """Effective fee split for one transaction."""

    gas_limit: int
    base_fee_per_gas_nrtc: int
    priority_fee_per_gas_nrtc: int
    burned_fee_nrtc: int
    priority_tip_nrtc: int
    total_fee_nrtc: int


def calculate_next_base_fee(
    parent_base_fee_nrtc: int,
    parent_gas_used: int,
    target_gas: int = DEFAULT_TARGET_GAS,
    max_change_denominator: int = DEFAULT_BASE_FEE_MAX_CHANGE_DENOMINATOR,
) -> int:
    """Calculate the next block base fee using EIP-1559 bounded adjustment."""

    _require_nonnegative_int(parent_base_fee_nrtc, "parent_base_fee_nrtc")
    _require_nonnegative_int(parent_gas_used, "parent_gas_used")
    _require_positive_int(target_gas, "target_gas")
    _require_positive_int(max_change_denominator, "max_change_denominator")

    if parent_gas_used == target_gas:
        return parent_base_fee_nrtc

    gas_delta = abs(parent_gas_used - target_gas)
    fee_delta = (
        parent_base_fee_nrtc * gas_delta // target_gas // max_change_denominator
    )

    if parent_gas_used > target_gas:
        return parent_base_fee_nrtc + max(fee_delta, 1)

    return max(parent_base_fee_nrtc - fee_delta, 0)


def calculate_effective_priority_fee(
    max_fee_per_gas_nrtc: int,
    max_priority_fee_per_gas_nrtc: int,
    base_fee_per_gas_nrtc: int,
) -> int:
    """Return the miner/validator tip per gas after the base fee is reserved."""

    _require_nonnegative_int(max_fee_per_gas_nrtc, "max_fee_per_gas_nrtc")
    _require_nonnegative_int(
        max_priority_fee_per_gas_nrtc, "max_priority_fee_per_gas_nrtc"
    )
    _require_nonnegative_int(base_fee_per_gas_nrtc, "base_fee_per_gas_nrtc")

    available_for_tip = max_fee_per_gas_nrtc - base_fee_per_gas_nrtc
    if available_for_tip < 0:
        raise ValueError("max_fee_per_gas_nrtc is below base_fee_per_gas_nrtc")

    return min(max_priority_fee_per_gas_nrtc, available_for_tip)


def calculate_eip1559_fee_breakdown(
    gas_limit: int,
    max_fee_per_gas_nrtc: int,
    max_priority_fee_per_gas_nrtc: int,
    base_fee_per_gas_nrtc: int,
) -> FeeBreakdown:
    """Split an EIP-1559 transaction fee into burned base fee and priority tip."""

    _require_positive_int(gas_limit, "gas_limit")
    priority_fee_per_gas = calculate_effective_priority_fee(
        max_fee_per_gas_nrtc,
        max_priority_fee_per_gas_nrtc,
        base_fee_per_gas_nrtc,
    )
    burned_fee = gas_limit * base_fee_per_gas_nrtc
    priority_tip = gas_limit * priority_fee_per_gas

    return FeeBreakdown(
        gas_limit=gas_limit,
        base_fee_per_gas_nrtc=base_fee_per_gas_nrtc,
        priority_fee_per_gas_nrtc=priority_fee_per_gas,
        burned_fee_nrtc=burned_fee,
        priority_tip_nrtc=priority_tip,
        total_fee_nrtc=burned_fee + priority_tip,
    )


def legacy_fee_breakdown(
    fee_nrtc: int,
    *,
    gas_limit: int = 1,
    base_fee_per_gas_nrtc: Optional[int] = None,
) -> FeeBreakdown:
    """Represent a legacy fixed fee as a backward-compatible priority tip."""

    _require_nonnegative_int(fee_nrtc, "fee_nrtc")
    _require_positive_int(gas_limit, "gas_limit")
    if base_fee_per_gas_nrtc is not None:
        _require_nonnegative_int(base_fee_per_gas_nrtc, "base_fee_per_gas_nrtc")
        burned_fee = gas_limit * base_fee_per_gas_nrtc
        if fee_nrtc < burned_fee:
            raise ValueError("fee_nrtc is below required base fee")
        priority_tip = fee_nrtc - burned_fee
        priority_fee_per_gas = priority_tip // gas_limit
        return FeeBreakdown(
            gas_limit=gas_limit,
            base_fee_per_gas_nrtc=base_fee_per_gas_nrtc,
            priority_fee_per_gas_nrtc=priority_fee_per_gas,
            burned_fee_nrtc=burned_fee,
            priority_tip_nrtc=priority_tip,
            total_fee_nrtc=fee_nrtc,
        )

    return FeeBreakdown(
        gas_limit=gas_limit,
        base_fee_per_gas_nrtc=0,
        priority_fee_per_gas_nrtc=fee_nrtc // gas_limit,
        burned_fee_nrtc=0,
        priority_tip_nrtc=fee_nrtc,
        total_fee_nrtc=fee_nrtc,
    )


def _require_nonnegative_int(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _require_positive_int(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
