# SPDX-License-Identifier: MIT
"""
Exact RTC amount handling (#8618).

The node keeps account balances as integer micro-RTC (``balances.amount_i64``,
``ACCOUNT_UNIT = 1_000_000``) and quantizes incoming ``amount_rtc`` /
``fee_rtc`` with ``Decimal(str(value))`` rounded *down* to 6 decimal places
(``node/payout_preflight.py``). Anything finer than 1 micro-RTC is therefore
silently dropped by the node *after* the user has signed for it.

This module turns user input into an exact integer number of micro-RTC and
refuses anything the chain cannot represent, so the amount a user signs is
the amount the ledger moves.
"""

from decimal import Decimal, InvalidOperation
from typing import Union

from .exceptions import ValidationError

#: Micro-RTC per RTC; matches the node's ``ACCOUNT_UNIT``.
MICRO_RTC_PER_RTC = 1_000_000
#: Decimal places the ledger can represent.
RTC_DECIMALS = 6

# The signed-transfer wire format carries amounts as JSON floats (the node
# rebuilds the signed message from ``float(Decimal(str(amount_rtc)))``), so
# the SDK must still put a float on the wire. Any decimal with at most 15
# significant digits survives a round trip through an IEEE-754 double
# exactly (DBL_DIG == 15). With 6 decimal places that allows up to 9 integer
# digits, i.e. amounts below 1e9 RTC -- far above the 8,388,608 RTC supply.
MAX_MICRO_RTC = 10**15 - 1

AmountInput = Union[str, int, Decimal, float]


def to_micro_rtc(value: AmountInput, field: str = "amount", allow_zero: bool = False) -> int:
    """Convert an RTC amount to an exact integer number of micro-RTC.

    Accepts ``str`` (preferred for user input), ``int``, ``Decimal`` or
    ``float``. Floats are read through ``str()`` -- their shortest round-trip
    form -- so ``0.29`` means 0.29, but a float carrying binary noise such as
    ``0.1 + 0.2`` (``0.30000000000000004``) is rejected as over-precise
    rather than silently rounded.

    Raises:
        ValidationError: not a finite number, negative, zero when
            ``allow_zero`` is False, more than 6 decimal places, or too large.
    """
    if isinstance(value, bool) or value is None:
        raise ValidationError(f"{field} must be a number, got {value!r}")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, (int, float, str)):
        text = value.strip() if isinstance(value, str) else str(value)
        if not text:
            raise ValidationError(f"{field} must be a number, got an empty string")
        try:
            d = Decimal(text)
        except (InvalidOperation, ValueError):
            raise ValidationError(f"{field} must be a number, got {value!r}") from None
    else:
        raise ValidationError(f"{field} must be a number, got {type(value).__name__}")

    if not d.is_finite():
        raise ValidationError(f"{field} must be finite, got {value!r}")
    if d < 0 or (d == 0 and not allow_zero):
        bound = "zero or more" if allow_zero else "greater than zero"
        raise ValidationError(f"{field} must be {bound}, got {value!r}")

    micro = d * MICRO_RTC_PER_RTC
    if micro != micro.to_integral_value():
        raise ValidationError(
            f"{field} {value!r} has more than {RTC_DECIMALS} decimal places; "
            f"the smallest RTC unit is 0.000001"
        )
    micro_int = int(micro)
    if micro_int > MAX_MICRO_RTC:
        raise ValidationError(f"{field} {value!r} is too large")
    return micro_int


def micro_rtc_to_float(micro: int) -> float:
    """Wire value for an exact micro-RTC amount.

    ``int / int`` true division is correctly rounded, so this is the double
    nearest to ``micro / 1e6`` -- the same float the node gets from
    ``float(Decimal(str(...)))`` -- and, under ``MAX_MICRO_RTC``, its
    ``repr`` is the exact 6-decimal amount.
    """
    return micro / MICRO_RTC_PER_RTC


def micro_rtc_to_str(micro: int) -> str:
    """Human-readable exact amount, e.g. ``290000 -> '0.29'``."""
    d = Decimal(micro) / MICRO_RTC_PER_RTC
    text = f"{d:.{RTC_DECIMALS}f}".rstrip("0").rstrip(".")
    return text or "0"
