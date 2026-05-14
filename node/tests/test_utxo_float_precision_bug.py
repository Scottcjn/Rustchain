# SPDX-License-Identifier: MIT
"""Regression coverage for exact RTC-to-nanoRTC conversion.

Issue #4671 identified that the old endpoint conversion path effectively did
``int(float(amount_rtc) * UNIT)``. Very small valid amounts such as 3 nanoRTC
could then truncate to 2 nanoRTC. The production parser/converter must preserve
the exact integer nanoRTC value.
"""

import pytest

from utxo_db import UNIT
from utxo_endpoints import _decimal_to_nrtc, _parse_rtc_amount


def old_float_conversion(amount_rtc):
    """Replica of the historical bug for documentation."""
    amount = float(amount_rtc)
    return int(amount * UNIT)


@pytest.mark.parametrize(
    ("amount_rtc", "expected_nrtc"),
    [
        ("0.1", 10_000_000),
        ("0.3", 30_000_000),
        ("0.00000003", 3),
        ("0.00000006", 6),
        ("0.00000012", 12),
        ("0.00000029", 29),
        ("0.00000058", 58),
        ("0.00000105", 105),
        (0.00000003, 3),
    ],
)
def test_decimal_conversion_preserves_nanortc(amount_rtc, expected_nrtc):
    amount = _parse_rtc_amount(amount_rtc)

    assert _decimal_to_nrtc(amount, "amount_rtc") == expected_nrtc


def test_old_float_conversion_would_undercount_three_nanortc():
    assert old_float_conversion(0.00000003) == 2
    assert _decimal_to_nrtc(_parse_rtc_amount("0.00000003"), "amount_rtc") == 3
