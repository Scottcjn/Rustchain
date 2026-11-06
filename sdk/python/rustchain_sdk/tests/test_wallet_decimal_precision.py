# SPDX-License-Identifier: MIT
"""Unit test for Decimal precision in wallet send."""
import pytest
from decimal import Decimal
import click
from rustchain_sdk.cli import parse_decimal_amount

def test_parse_decimal_amount_valid():
    assert parse_decimal_amount("0.29") == Decimal("0.29")
    assert parse_decimal_amount("10.5") == Decimal("10.5")
    assert parse_decimal_amount("0.00000001") == Decimal("0.00000001")
    assert parse_decimal_amount("100") == Decimal("100")

def test_parse_decimal_amount_over_precision():
    with pytest.raises(click.BadParameter, match="exceeds maximum precision"):
        parse_decimal_amount("0.123456789")

def test_parse_decimal_amount_negative():
    with pytest.raises(click.BadParameter, match="cannot be negative"):
        parse_decimal_amount("-5.0")
