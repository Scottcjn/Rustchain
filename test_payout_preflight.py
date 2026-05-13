from payout_preflight import (
    validate_wallet_transfer_admin,
    validate_wallet_transfer_signed,
)


VALID_FROM = "RTC" + "a" * 40
VALID_TO = "RTC" + "b" * 40


def test_admin_transfer_quantizes_fractional_rtc_to_micro_units():
    result = validate_wallet_transfer_admin(
        {
            "from_miner": "miner-a",
            "to_miner": "miner-b",
            "amount_rtc": "1.23456789",
        }
    )

    assert result.ok is True
    assert result.error == ""
    assert result.details["amount_i64"] == 1_234_567
    assert result.details["from_miner"] == "miner-a"
    assert result.details["to_miner"] == "miner-b"


def test_admin_transfer_rejects_amount_below_smallest_unit():
    result = validate_wallet_transfer_admin(
        {
            "from_miner": "miner-a",
            "to_miner": "miner-b",
            "amount_rtc": "0.0000009",
        }
    )

    assert result.ok is False
    assert result.error == "amount_too_small_after_quantization"
    assert result.details["min_rtc"] == 0.000001


def test_signed_transfer_rejects_same_sender_and_recipient():
    result = validate_wallet_transfer_signed(
        {
            "from_address": VALID_FROM,
            "to_address": VALID_FROM,
            "amount_rtc": "2",
            "nonce": "7",
            "signature": "sig",
            "public_key": "pub",
        }
    )

    assert result.ok is False
    assert result.error == "from_to_must_differ"


def test_signed_transfer_rejects_bad_nonce_before_success_path():
    result = validate_wallet_transfer_signed(
        {
            "from_address": VALID_FROM,
            "to_address": VALID_TO,
            "amount_rtc": "2",
            "nonce": "not-an-int",
            "signature": "sig",
            "public_key": "pub",
        }
    )

    assert result.ok is False
    assert result.error == "nonce_not_int"


def test_signed_transfer_rejects_invalid_chain_id_characters():
    result = validate_wallet_transfer_signed(
        {
            "from_address": VALID_FROM,
            "to_address": VALID_TO,
            "amount_rtc": "2",
            "nonce": "7",
            "signature": "sig",
            "public_key": "pub",
            "chain_id": "mainnet;drop",
        }
    )

    assert result.ok is False
    assert result.error == "invalid_chain_id_format"


def test_signed_transfer_accepts_optional_chain_id_and_quantized_amount():
    result = validate_wallet_transfer_signed(
        {
            "from_address": VALID_FROM,
            "to_address": VALID_TO,
            "amount_rtc": "3.5000019",
            "nonce": "42",
            "signature": "sig",
            "public_key": "pub",
            "chain_id": "rustchain-mainnet_1",
        }
    )

    assert result.ok is True
    assert result.error == ""
    assert result.details["amount_i64"] == 3_500_001
    assert result.details["nonce"] == 42
    assert result.details["chain_id"] == "rustchain-mainnet_1"
