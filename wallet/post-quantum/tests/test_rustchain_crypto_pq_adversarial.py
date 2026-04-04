"""
RED TEAM adversarial test suite for RustChain post-quantum wallet (RIP-300).

Tests every known attack vector against the hybrid Ed25519 + ML-DSA-44 wallet:
replay attacks, signature malleability, key substitution, transaction mutation,
encoding attacks, edge-case amounts, address format attacks, keystore security,
deterministic restore guards, and cross-scheme attacks.

This is a security-focused complement to test_rustchain_crypto_pq.py.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import sys

import pytest

sys.path.insert(0, "/home/scott/Desktop/rustchain-wallet-pkg/src")

from rustchain_crypto_pq import (
    ED25519_PUBLIC_KEY_SIZE,
    ED25519_SIGNATURE_SIZE,
    MLDSA44_PUBLIC_KEY_SIZE,
    MLDSA44_SIGNATURE_SIZE,
    PREFIX_LEGACY,
    PREFIX_PQ,
    KEYSTORE_VERSION_PQ,
    RustChainPQWallet,
    _canonical_transaction_message,
    _validate_transaction_fields,
    _decode_hex_field,
    _pq_address_from_public_keys,
    verify_hybrid_signature,
    verify_hybrid_transaction,
    verify_legacy_or_hybrid,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def wallet_a():
    """A fresh PQ wallet for testing (module-scoped for speed)."""
    return RustChainPQWallet.create()


@pytest.fixture(scope="module")
def wallet_b():
    """A second distinct PQ wallet."""
    return RustChainPQWallet.create()


@pytest.fixture
def valid_tx(wallet_a):
    """A fully valid hybrid transaction from wallet_a."""
    return wallet_a.sign_transaction("RTCQtarget123", 42.0, memo="adversarial", nonce=100000)


@pytest.fixture
def valid_legacy_tx(wallet_a):
    """A legacy Ed25519-only transaction from wallet_a."""
    nonce = 200000
    message = _canonical_transaction_message(
        wallet_a.legacy_address, "RTCrecipient", 25.0, "", nonce,
    )
    sig = wallet_a.sign_ed25519_only(message)
    return {
        "from_address": wallet_a.legacy_address,
        "to_address": "RTCrecipient",
        "amount_rtc": 25.0,
        "memo": "",
        "nonce": nonce,
        "signature": sig,
        "public_key": wallet_a.ed_public_key,
    }


# ══════════════════════════════════════════════════════════════
# 1. Replay Attacks
# ══════════════════════════════════════════════════════════════


class TestReplayAttacks:
    """Server-side dedup is not the wallet's job, but the nonce must
    be part of the signed message so that different nonces produce
    different (invalid) signatures."""

    def test_same_nonce_both_verify(self, valid_tx):
        """Exact replay (same nonce) still verifies at the crypto layer.
        Server-side dedup must reject duplicates."""
        tx_copy = copy.deepcopy(valid_tx)
        assert verify_hybrid_transaction(tx_copy)["fully_valid"] is True

    def test_nonce_is_part_of_signed_message(self, wallet_a, valid_tx):
        """Changing the nonce by 1 invalidates both signatures."""
        tx = copy.deepcopy(valid_tx)
        tx["nonce"] += 1
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_nonce_zero_difference_invalidates(self, wallet_a):
        """Two transactions with different nonces produce different sigs."""
        tx1 = wallet_a.sign_transaction("RTCQx", 1.0, nonce=1)
        tx2 = wallet_a.sign_transaction("RTCQx", 1.0, nonce=2)
        assert tx1["signature"] != tx2["signature"]
        assert tx1["pq_signature"] != tx2["pq_signature"]


# ══════════════════════════════════════════════════════════════
# 2. Signature Malleability
# ══════════════════════════════════════════════════════════════


class TestSignatureMalleability:
    """Bit-flip, truncation, extension, and swap attacks on signatures."""

    def test_ed25519_bitflip_every_byte(self, valid_tx):
        """Flip a single bit in every byte position of the Ed25519 sig."""
        sig_bytes = bytearray(bytes.fromhex(valid_tx["signature"]))
        for i in range(len(sig_bytes)):
            tx = copy.deepcopy(valid_tx)
            flipped = bytearray(sig_bytes)
            flipped[i] ^= 0x01
            tx["signature"] = bytes(flipped).hex()
            result = verify_hybrid_transaction(tx)
            assert result["fully_valid"] is False, f"Ed25519 bitflip at byte {i} was not caught"

    def test_mldsa_bitflip_every_100th_byte(self, valid_tx):
        """Flip a bit in every 100th byte of the ML-DSA sig."""
        sig_bytes = bytearray(bytes.fromhex(valid_tx["pq_signature"]))
        positions = range(0, len(sig_bytes), 100)
        for i in positions:
            tx = copy.deepcopy(valid_tx)
            flipped = bytearray(sig_bytes)
            flipped[i] ^= 0x01
            tx["pq_signature"] = bytes(flipped).hex()
            result = verify_hybrid_transaction(tx)
            assert result["fully_valid"] is False, f"ML-DSA bitflip at byte {i} was not caught"

    def test_truncated_ed25519_sig(self, valid_tx):
        """Ed25519 sig missing last byte."""
        tx = copy.deepcopy(valid_tx)
        tx["signature"] = valid_tx["signature"][:-2]  # Remove 1 byte (2 hex chars)
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_truncated_mldsa_sig(self, valid_tx):
        """ML-DSA sig missing last byte."""
        tx = copy.deepcopy(valid_tx)
        tx["pq_signature"] = valid_tx["pq_signature"][:-2]
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_extended_ed25519_sig(self, valid_tx):
        """Ed25519 sig with extra byte appended."""
        tx = copy.deepcopy(valid_tx)
        tx["signature"] = valid_tx["signature"] + "ff"
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_extended_mldsa_sig(self, valid_tx):
        """ML-DSA sig with extra byte appended."""
        tx = copy.deepcopy(valid_tx)
        tx["pq_signature"] = valid_tx["pq_signature"] + "ff"
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_swapped_signatures(self, valid_tx):
        """Ed25519 sig in ML-DSA field and vice versa -- must fail."""
        tx = copy.deepcopy(valid_tx)
        tx["signature"], tx["pq_signature"] = tx["pq_signature"], tx["signature"]
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_all_zero_ed25519_sig(self, valid_tx):
        """Null signature (all zeros)."""
        tx = copy.deepcopy(valid_tx)
        tx["signature"] = "00" * ED25519_SIGNATURE_SIZE
        result = verify_hybrid_transaction(tx)
        assert result["ed25519_valid"] is False
        assert result["fully_valid"] is False

    def test_all_zero_mldsa_sig(self, valid_tx):
        """Null ML-DSA signature (all zeros)."""
        tx = copy.deepcopy(valid_tx)
        tx["pq_signature"] = "00" * MLDSA44_SIGNATURE_SIZE
        result = verify_hybrid_transaction(tx)
        assert result["ml_dsa_44_valid"] is False
        assert result["fully_valid"] is False

    def test_all_ff_ed25519_sig(self, valid_tx):
        """All-0xFF Ed25519 signature."""
        tx = copy.deepcopy(valid_tx)
        tx["signature"] = "ff" * ED25519_SIGNATURE_SIZE
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_all_ff_mldsa_sig(self, valid_tx):
        """All-0xFF ML-DSA signature."""
        tx = copy.deepcopy(valid_tx)
        tx["pq_signature"] = "ff" * MLDSA44_SIGNATURE_SIZE
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False


# ══════════════════════════════════════════════════════════════
# 3. Key Substitution Attacks
# ══════════════════════════════════════════════════════════════


class TestKeySubstitution:
    """Replace public keys to hijack address binding or verification."""

    def test_replace_both_pubkeys_with_wallet_b(self, wallet_a, wallet_b, valid_tx):
        """Wallet A signs, replace both pubkeys with B's -- must fail."""
        tx = copy.deepcopy(valid_tx)
        tx["public_key"] = wallet_b.ed_public_key
        tx["pq_public_key"] = wallet_b.pq_public_key
        result = verify_hybrid_transaction(tx)
        assert result["ed25519_valid"] is False
        assert result["fully_valid"] is False

    def test_replace_only_pq_pubkey(self, wallet_a, wallet_b, valid_tx):
        """Replace only PQ pubkey -- address binding must catch it."""
        tx = copy.deepcopy(valid_tx)
        tx["pq_public_key"] = wallet_b.pq_public_key
        result = verify_hybrid_transaction(tx)
        assert result["address_valid"] is False
        assert result["fully_valid"] is False

    def test_replace_only_ed_pubkey(self, wallet_a, wallet_b, valid_tx):
        """Replace only Ed25519 pubkey -- sig verification must fail."""
        tx = copy.deepcopy(valid_tx)
        tx["public_key"] = wallet_b.ed_public_key
        result = verify_hybrid_transaction(tx)
        assert result["ed25519_valid"] is False
        assert result["fully_valid"] is False

    def test_recomputed_address_from_wrong_keys(self, wallet_a, wallet_b, valid_tx):
        """Replace keys AND recompute address -- sigs still fail."""
        tx = copy.deepcopy(valid_tx)
        tx["public_key"] = wallet_b.ed_public_key
        tx["pq_public_key"] = wallet_b.pq_public_key
        # Recompute address to match wallet_b's keys
        tx["from_address"] = _pq_address_from_public_keys(
            bytes.fromhex(wallet_b.ed_public_key),
            wallet_b.pq_public_key_bytes,
        )
        result = verify_hybrid_transaction(tx)
        # Address matches now, but signatures don't
        assert result["address_valid"] is True
        assert result["ed25519_valid"] is False
        assert result["ml_dsa_44_valid"] is False
        assert result["fully_valid"] is False


# ══════════════════════════════════════════════════════════════
# 4. Transaction Mutation
# ══════════════════════════════════════════════════════════════


class TestTransactionMutation:
    """Modify any transaction field -- sigs must break."""

    def test_change_amount_by_epsilon(self, valid_tx):
        """Change amount by 0.001."""
        tx = copy.deepcopy(valid_tx)
        tx["amount_rtc"] += 0.001
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_change_memo(self, valid_tx):
        """Change the memo text."""
        tx = copy.deepcopy(valid_tx)
        tx["memo"] = "hacked"
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_change_from_address(self, valid_tx, wallet_b):
        """Change from_address to a different wallet."""
        tx = copy.deepcopy(valid_tx)
        tx["from_address"] = wallet_b.address
        result = verify_hybrid_transaction(tx)
        # Address binding fails (doesn't match pubkeys)
        assert result["address_valid"] is False
        assert result["fully_valid"] is False

    def test_change_to_address(self, valid_tx):
        """Change to_address."""
        tx = copy.deepcopy(valid_tx)
        tx["to_address"] = "RTCQattacker"
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_change_nonce_by_one(self, valid_tx):
        """Change nonce by 1."""
        tx = copy.deepcopy(valid_tx)
        tx["nonce"] += 1
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_extra_field_ignored_in_canonical_form(self, wallet_a):
        """Extra fields should not affect canonical message or verification."""
        tx = wallet_a.sign_transaction("RTCQx", 1.0, nonce=42)
        tx["evil_field"] = "should be ignored"
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is True

    def test_remove_memo_field(self, valid_tx):
        """Remove memo entirely -- should produce different canonical form."""
        tx = copy.deepcopy(valid_tx)
        del tx["memo"]
        # verify_hybrid_transaction uses tx.get("memo", "") -- so missing memo
        # becomes "" which differs from "adversarial"
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_empty_memo_vs_missing_memo(self, wallet_a):
        """A TX signed with memo="" should verify when memo is missing (defaults to "")."""
        tx = wallet_a.sign_transaction("RTCQx", 1.0, memo="", nonce=42)
        del tx["memo"]
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is True


# ══════════════════════════════════════════════════════════════
# 5. Encoding Attacks
# ══════════════════════════════════════════════════════════════


class TestEncodingAttacks:
    """Malformed hex, unicode injection, and length violations."""

    def test_non_hex_in_ed_signature(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["signature"] = "zz" + valid_tx["signature"][2:]
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_non_hex_in_pq_signature(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["pq_signature"] = "gg" + valid_tx["pq_signature"][2:]
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_odd_length_hex_ed_sig(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["signature"] = valid_tx["signature"][:-1]  # odd length
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_odd_length_hex_pq_sig(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["pq_signature"] = valid_tx["pq_signature"][:-1]
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_empty_string_ed_signature(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["signature"] = ""
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_empty_string_pq_signature(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["pq_signature"] = ""
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_unicode_in_ed_sig(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["signature"] = "\u00ff" * ED25519_SIGNATURE_SIZE
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_unicode_in_pq_sig(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["pq_signature"] = "\u00e9" * 10
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_very_long_ed_sig(self, valid_tx):
        """Valid hex but wrong length (much too long)."""
        tx = copy.deepcopy(valid_tx)
        tx["signature"] = "aa" * 1000
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_very_long_pq_sig(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["pq_signature"] = "bb" * 5000
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_non_hex_in_ed_pubkey(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["public_key"] = "xyz" + valid_tx["public_key"][3:]
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_non_hex_in_pq_pubkey(self, valid_tx):
        tx = copy.deepcopy(valid_tx)
        tx["pq_public_key"] = "!!invalid!!"
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_decode_hex_field_rejects_non_string(self):
        with pytest.raises(TypeError, match="must be a hex string"):
            _decode_hex_field("test", 12345)

    def test_decode_hex_field_rejects_wrong_length(self):
        with pytest.raises(ValueError, match="must be exactly"):
            _decode_hex_field("test", "aabbccdd", expected_len=2)

    def test_decode_hex_field_rejects_invalid_hex(self):
        with pytest.raises(ValueError):
            _decode_hex_field("test", "zzzz")

    def test_decode_hex_field_rejects_odd_hex(self):
        with pytest.raises(ValueError):
            _decode_hex_field("test", "abc")  # odd-length


# ══════════════════════════════════════════════════════════════
# 6. Edge Case Amounts
# ══════════════════════════════════════════════════════════════


class TestEdgeCaseAmounts:
    """Boundary values for transaction amounts."""

    def test_amount_zero_is_valid(self, wallet_a):
        """Zero-value transactions should be signable and verifiable."""
        tx = wallet_a.sign_transaction("RTCQx", 0.0, nonce=1)
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is True

    def test_amount_negative_rejected(self, wallet_a):
        """Negative amounts must be rejected by validation."""
        with pytest.raises(ValueError, match="non-negative"):
            wallet_a.sign_transaction("RTCQx", -1.0, nonce=1)

    def test_amount_negative_one(self, wallet_a):
        with pytest.raises(ValueError, match="non-negative"):
            wallet_a.sign_transaction("RTCQx", -0.001, nonce=1)

    def test_amount_inf_rejected(self, wallet_a):
        with pytest.raises(ValueError, match="finite"):
            wallet_a.sign_transaction("RTCQx", float("inf"), nonce=1)

    def test_amount_neg_inf_rejected(self, wallet_a):
        with pytest.raises(ValueError, match="finite|non-negative"):
            wallet_a.sign_transaction("RTCQx", float("-inf"), nonce=1)

    def test_amount_nan_rejected(self, wallet_a):
        """NaN must be rejected. _canonical_transaction_message uses allow_nan=False."""
        with pytest.raises((ValueError, TypeError)):
            wallet_a.sign_transaction("RTCQx", float("nan"), nonce=1)

    def test_amount_beyond_float_precision(self, wallet_a):
        """2**53 + 1 is beyond float64 exact integer range.
        The canonical form should still be consistent (whatever float() rounds to)."""
        big = 2**53 + 1
        tx = wallet_a.sign_transaction("RTCQx", float(big), nonce=1)
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is True

    def test_amount_float_imprecision(self, wallet_a):
        """0.1 + 0.2 != 0.3 in IEEE 754. Canonical form must be stable."""
        amount = 0.1 + 0.2  # 0.30000000000000004
        tx = wallet_a.sign_transaction("RTCQx", amount, nonce=1)
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is True

    def test_amount_bool_rejected(self, wallet_a):
        """bool is a subclass of int; must be rejected."""
        with pytest.raises(TypeError, match="finite number"):
            wallet_a.sign_transaction("RTCQx", True, nonce=1)

    def test_amount_string_rejected(self, wallet_a):
        with pytest.raises(TypeError):
            wallet_a.sign_transaction("RTCQx", "42.0", nonce=1)

    def test_nonce_negative_rejected(self, wallet_a):
        with pytest.raises(ValueError, match="non-negative"):
            wallet_a.sign_transaction("RTCQx", 1.0, nonce=-1)

    def test_nonce_bool_rejected(self, wallet_a):
        with pytest.raises(TypeError, match="must be an integer"):
            wallet_a.sign_transaction("RTCQx", 1.0, nonce=True)

    def test_nonce_float_rejected(self, wallet_a):
        with pytest.raises(TypeError, match="must be an integer"):
            wallet_a.sign_transaction("RTCQx", 1.0, nonce=1.5)


# ══════════════════════════════════════════════════════════════
# 7. Address Format Attacks
# ══════════════════════════════════════════════════════════════


class TestAddressFormatAttacks:
    """Malformed, mismatched, and empty addresses."""

    def test_rtcq_address_wrong_length(self, valid_tx):
        """RTCQ address with wrong hash length."""
        tx = copy.deepcopy(valid_tx)
        tx["from_address"] = "RTCQshort"
        result = verify_hybrid_transaction(tx)
        assert result["address_valid"] is False
        assert result["fully_valid"] is False

    def test_rtc_address_submitted_as_rtcq(self, valid_tx, wallet_a):
        """Legacy RTC address in a hybrid transaction."""
        tx = copy.deepcopy(valid_tx)
        tx["from_address"] = wallet_a.legacy_address  # RTC instead of RTCQ
        result = verify_hybrid_transaction(tx)
        assert result["address_valid"] is False
        assert result["fully_valid"] is False

    def test_rtcq_valid_hash_wrong_prefix(self, valid_tx):
        """Address with correct hash but RTCX prefix."""
        tx = copy.deepcopy(valid_tx)
        tx["from_address"] = "RTCX" + valid_tx["from_address"][4:]
        result = verify_hybrid_transaction(tx)
        assert result["address_valid"] is False

    def test_empty_from_address_rejected(self, wallet_a):
        with pytest.raises(ValueError, match="non-empty"):
            _validate_transaction_fields(
                from_address="",
                to_address="RTCQx",
                amount=1.0,
                memo="",
                nonce=1,
            )

    def test_empty_to_address_rejected(self, wallet_a):
        with pytest.raises(ValueError, match="non-empty"):
            _validate_transaction_fields(
                from_address="RTCQx",
                to_address="",
                amount=1.0,
                memo="",
                nonce=1,
            )

    def test_whitespace_only_from_address_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            _validate_transaction_fields(
                from_address="   ",
                to_address="RTCQx",
                amount=1.0,
                memo="",
                nonce=1,
            )


# ══════════════════════════════════════════════════════════════
# 8. Keystore Security
# ══════════════════════════════════════════════════════════════


class TestKeystoreSecurity:
    """Attacks against the encrypted keystore v2."""

    def test_corrupted_ciphertext(self, wallet_a):
        """Tampered ciphertext must fail AES-GCM authentication."""
        ks = wallet_a.export_encrypted("password123")
        ct_bytes = bytearray(base64.b64decode(ks["ciphertext"]))
        ct_bytes[0] ^= 0xFF
        ks["ciphertext"] = base64.b64encode(bytes(ct_bytes)).decode()
        with pytest.raises(ValueError, match="Invalid password"):
            RustChainPQWallet.from_encrypted(ks, "password123")

    def test_modified_salt(self, wallet_a):
        """Wrong salt derives wrong key -- decryption fails."""
        ks = wallet_a.export_encrypted("password123")
        salt_bytes = bytearray(base64.b64decode(ks["salt"]))
        salt_bytes[0] ^= 0xFF
        ks["salt"] = base64.b64encode(bytes(salt_bytes)).decode()
        with pytest.raises(ValueError, match="Invalid password"):
            RustChainPQWallet.from_encrypted(ks, "password123")

    def test_modified_nonce(self, wallet_a):
        """Wrong nonce breaks AES-GCM."""
        ks = wallet_a.export_encrypted("password123")
        nonce_bytes = bytearray(base64.b64decode(ks["nonce"]))
        nonce_bytes[0] ^= 0xFF
        ks["nonce"] = base64.b64encode(bytes(nonce_bytes)).decode()
        with pytest.raises(ValueError, match="Invalid password"):
            RustChainPQWallet.from_encrypted(ks, "password123")

    def test_version_downgrade_v1(self, wallet_a):
        """Version downgrade to v1 must be rejected."""
        ks = wallet_a.export_encrypted("password123")
        ks["version"] = 1
        with pytest.raises(ValueError, match="Legacy keystore v1"):
            RustChainPQWallet.from_encrypted(ks, "password123")

    def test_version_downgrade_v0(self, wallet_a):
        """Version 0 must also be rejected."""
        ks = wallet_a.export_encrypted("password123")
        ks["version"] = 0
        with pytest.raises(ValueError, match="Legacy keystore v1"):
            RustChainPQWallet.from_encrypted(ks, "password123")

    def test_extra_fields_in_keystore_ignored(self, wallet_a):
        """Injected fields should not affect decryption."""
        ks = wallet_a.export_encrypted("password123")
        ks["evil_field"] = "injected"
        ks["admin"] = True
        restored = RustChainPQWallet.from_encrypted(ks, "password123")
        assert restored.address == wallet_a.address

    def test_missing_ciphertext_field(self, wallet_a):
        ks = wallet_a.export_encrypted("password123")
        del ks["ciphertext"]
        with pytest.raises((ValueError, KeyError)):
            RustChainPQWallet.from_encrypted(ks, "password123")

    def test_missing_salt_field(self, wallet_a):
        ks = wallet_a.export_encrypted("password123")
        del ks["salt"]
        with pytest.raises((ValueError, KeyError)):
            RustChainPQWallet.from_encrypted(ks, "password123")

    def test_invalid_base64_ciphertext(self, wallet_a):
        ks = wallet_a.export_encrypted("password123")
        ks["ciphertext"] = "!!!not-base64!!!"
        with pytest.raises(ValueError):
            RustChainPQWallet.from_encrypted(ks, "password123")

    def test_wrong_salt_length(self, wallet_a):
        """Salt with wrong length must be rejected."""
        ks = wallet_a.export_encrypted("password123")
        ks["salt"] = base64.b64encode(b"\x00" * 8).decode()  # 8 bytes instead of 16
        with pytest.raises(ValueError, match="Malformed keystore parameters"):
            RustChainPQWallet.from_encrypted(ks, "password123")

    def test_wrong_nonce_length(self, wallet_a):
        """Nonce with wrong length must be rejected."""
        ks = wallet_a.export_encrypted("password123")
        ks["nonce"] = base64.b64encode(b"\x00" * 8).decode()  # 8 bytes instead of 12
        with pytest.raises(ValueError, match="Malformed keystore parameters"):
            RustChainPQWallet.from_encrypted(ks, "password123")


# ══════════════════════════════════════════════════════════════
# 9. Deterministic Restore Guard
# ══════════════════════════════════════════════════════════════


class TestDeterministicRestoreGuard:
    """from_mnemonic without allow_nondeterministic_pq must refuse."""

    def test_from_mnemonic_without_flag_raises(self, wallet_a):
        with pytest.raises(RuntimeError, match="Deterministic ML-DSA-44"):
            RustChainPQWallet.from_mnemonic(wallet_a.mnemonic)

    def test_from_mnemonic_with_flag_false_raises(self, wallet_a):
        with pytest.raises(RuntimeError, match="Deterministic ML-DSA-44"):
            RustChainPQWallet.from_mnemonic(
                wallet_a.mnemonic, allow_nondeterministic_pq=False
            )

    def test_from_mnemonic_nondeterministic_produces_different_pq_keys(self, wallet_a):
        """Two restorations with allow_nondeterministic_pq=True get different PQ keys."""
        r1 = RustChainPQWallet.from_mnemonic(
            wallet_a.mnemonic, allow_nondeterministic_pq=True
        )
        r2 = RustChainPQWallet.from_mnemonic(
            wallet_a.mnemonic, allow_nondeterministic_pq=True
        )
        # PQ keys are non-deterministic
        assert r1.pq_public_key != r2.pq_public_key
        # But RTCQ addresses differ because they incorporate the PQ pubkey
        assert r1.address != r2.address

    def test_ed25519_keys_are_deterministic(self, wallet_a):
        """Ed25519 keys are deterministic from the same mnemonic."""
        r1 = RustChainPQWallet.from_mnemonic(
            wallet_a.mnemonic, allow_nondeterministic_pq=True
        )
        r2 = RustChainPQWallet.from_mnemonic(
            wallet_a.mnemonic, allow_nondeterministic_pq=True
        )
        assert r1.ed_public_key == r2.ed_public_key
        assert r1.ed_private_key == r2.ed_private_key
        assert r1.legacy_address == r2.legacy_address


# ══════════════════════════════════════════════════════════════
# 10. Cross-Scheme Attacks
# ══════════════════════════════════════════════════════════════


class TestCrossSchemeAttacks:
    """Interactions between legacy and hybrid verification paths."""

    def test_hybrid_tx_passes_legacy_verifier(self, valid_tx):
        """verify_legacy_or_hybrid should accept valid hybrid transactions."""
        assert verify_legacy_or_hybrid(valid_tx) is True

    def test_legacy_tx_with_fake_pq_sig_added(self, valid_legacy_tx):
        """Legacy TX with a fake pq_signature added -- should fail hybrid,
        and verify_legacy_or_hybrid routes to hybrid path (both present)."""
        tx = copy.deepcopy(valid_legacy_tx)
        tx["pq_signature"] = "aa" * MLDSA44_SIGNATURE_SIZE
        tx["pq_public_key"] = "bb" * MLDSA44_PUBLIC_KEY_SIZE
        # With both pq fields present, it goes through hybrid path and fails
        assert verify_legacy_or_hybrid(tx) is False

    def test_empty_pq_fields_falls_to_legacy(self, valid_legacy_tx):
        """Empty pq_signature + empty pq_public_key should use legacy path."""
        tx = copy.deepcopy(valid_legacy_tx)
        tx["pq_signature"] = ""
        tx["pq_public_key"] = ""
        assert verify_legacy_or_hybrid(tx) is True

    def test_none_pq_fields_falls_to_legacy(self, valid_legacy_tx):
        """None pq fields should use legacy path."""
        tx = copy.deepcopy(valid_legacy_tx)
        tx["pq_signature"] = None
        tx["pq_public_key"] = None
        assert verify_legacy_or_hybrid(tx) is True

    def test_pq_sig_present_but_pq_pubkey_missing(self, valid_legacy_tx):
        """pq_signature present but pq_public_key missing -- must fail."""
        tx = copy.deepcopy(valid_legacy_tx)
        tx["pq_signature"] = "aa" * MLDSA44_SIGNATURE_SIZE
        # pq_public_key not present -> has_pq_signature != has_pq_public_key
        assert verify_legacy_or_hybrid(tx) is False

    def test_pq_pubkey_present_but_pq_sig_missing(self, valid_legacy_tx):
        """pq_public_key present but pq_signature missing -- must fail."""
        tx = copy.deepcopy(valid_legacy_tx)
        tx["pq_public_key"] = "bb" * MLDSA44_PUBLIC_KEY_SIZE
        # pq_signature not present
        assert verify_legacy_or_hybrid(tx) is False

    def test_hybrid_scheme_without_pq_fields_rejected(self, valid_legacy_tx):
        """signature_scheme says hybrid but no PQ fields -- must fail."""
        tx = copy.deepcopy(valid_legacy_tx)
        tx["signature_scheme"] = "hybrid-ed25519-mldsa44"
        assert verify_legacy_or_hybrid(tx) is False

    def test_wrong_scheme_string_rejected(self, valid_tx):
        """Unknown signature_scheme must fail verify_hybrid_transaction."""
        tx = copy.deepcopy(valid_tx)
        tx["signature_scheme"] = "invalid-scheme"
        result = verify_hybrid_transaction(tx)
        assert result.get("fully_valid") is False

    def test_legacy_tx_missing_public_key(self):
        """Legacy TX without public_key field must fail."""
        tx = {
            "from_address": "RTCabc123",
            "to_address": "RTCdef456",
            "amount_rtc": 1.0,
            "memo": "",
            "nonce": 1,
            "signature": "aa" * 64,
        }
        assert verify_legacy_or_hybrid(tx) is False

    def test_hybrid_tx_missing_required_field(self, wallet_a):
        """Hybrid TX missing nonce must fail gracefully."""
        tx = wallet_a.sign_transaction("RTCQx", 1.0, nonce=1)
        del tx["nonce"]
        result = verify_hybrid_transaction(tx)
        assert result.get("fully_valid") is False


# ══════════════════════════════════════════════════════════════
# 11. Canonical Message Stability
# ══════════════════════════════════════════════════════════════


class TestCanonicalMessageStability:
    """Ensure canonical transaction message is deterministic and order-independent."""

    def test_canonical_message_is_deterministic(self):
        msg1 = _canonical_transaction_message("RTCQfrom", "RTCQto", 1.0, "m", 1)
        msg2 = _canonical_transaction_message("RTCQfrom", "RTCQto", 1.0, "m", 1)
        assert msg1 == msg2

    def test_canonical_message_sorted_keys(self):
        msg = _canonical_transaction_message("RTCQfrom", "RTCQto", 1.0, "memo", 42)
        parsed = json.loads(msg)
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_canonical_message_no_spaces(self):
        msg = _canonical_transaction_message("RTCQfrom", "RTCQto", 1.0, "memo", 42)
        assert b" " not in msg

    def test_canonical_message_nan_raises(self):
        """allow_nan=False in json.dumps should reject NaN."""
        with pytest.raises(ValueError):
            _canonical_transaction_message("RTCQfrom", "RTCQto", float("nan"), "", 1)

    def test_canonical_message_inf_raises(self):
        with pytest.raises(ValueError):
            _canonical_transaction_message("RTCQfrom", "RTCQto", float("inf"), "", 1)


# ══════════════════════════════════════════════════════════════
# 12. Type Confusion Attacks on sign_message
# ══════════════════════════════════════════════════════════════


class TestTypeConfusion:
    """Ensure type checks prevent misuse."""

    def test_sign_message_rejects_string(self, wallet_a):
        with pytest.raises(TypeError, match="must be bytes"):
            wallet_a.sign_message("not bytes")

    def test_sign_message_rejects_int(self, wallet_a):
        with pytest.raises(TypeError, match="must be bytes"):
            wallet_a.sign_message(42)

    def test_sign_ed25519_only_rejects_string(self, wallet_a):
        with pytest.raises(TypeError, match="must be bytes"):
            wallet_a.sign_ed25519_only("not bytes")

    def test_validate_fields_rejects_none_address(self):
        with pytest.raises((ValueError, AttributeError)):
            _validate_transaction_fields(
                from_address=None,
                to_address="RTCQx",
                amount=1.0,
                memo="",
                nonce=1,
            )

    def test_validate_fields_rejects_none_memo(self):
        with pytest.raises(TypeError, match="memo must be a string"):
            _validate_transaction_fields(
                from_address="RTCQx",
                to_address="RTCQy",
                amount=1.0,
                memo=None,
                nonce=1,
            )
