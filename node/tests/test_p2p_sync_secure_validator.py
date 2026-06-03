# SPDX-License-Identifier: MIT

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rustchain_p2p_sync_secure import BlockValidator


def _validator_with_hash_and_signature_bypassed():
    validator = BlockValidator()
    validator._validate_block_hash = lambda block: True
    validator._verify_block_signature = lambda block: True
    validator._verify_miner_pubkey_match = lambda block: True
    return validator


def _valid_block(**overrides):
    block = {
        "block_index": 1,
        "hash": "abc",
        "previous_hash": "0" * 64,
        "timestamp": 1,
        "miner": "RTC" + "a" * 40,
        "transactions": [],
        "signature": "00",
        "pubkey_hex": "11",
        "message_hex": "22",
    }
    block.update(overrides)
    return block


def test_validate_block_rejects_non_object_block():
    validator = _validator_with_hash_and_signature_bypassed()

    valid, reason = validator.validate_block(["not", "a", "block"])

    assert valid is False
    assert reason == "Block must be a JSON object"


def test_validate_block_rejects_non_list_transactions():
    validator = _validator_with_hash_and_signature_bypassed()

    valid, reason = validator.validate_block(_valid_block(transactions={"tx_hash": "tx1"}))

    assert valid is False
    assert reason == "Block transactions must be a list"


def test_validate_block_rejects_non_object_transaction_without_exception():
    validator = _validator_with_hash_and_signature_bypassed()

    valid, reason = validator.validate_block(_valid_block(transactions=["tx1"]))

    assert valid is False
    assert reason == "Invalid transaction: unknown"
