"""Tests for the RustChain post-quantum wallet module (RIP-300 Phase 1).

Covers hybrid Ed25519 + ML-DSA-44 wallet creation, signing, verification,
keystore round-trips, tampering detection, and legacy compatibility.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys

import pytest

sys.path.insert(0, "/home/scott/Desktop/rustchain-wallet-pkg/src")

from rustchain_crypto_pq import (
    PREFIX_LEGACY,
    PREFIX_PQ,
    KEYSTORE_VERSION_PQ,
    RustChainPQWallet,
    verify_hybrid_signature,
    verify_hybrid_transaction,
    verify_legacy_or_hybrid,
)


# ── Wallet creation ──────────────────────────────────────────


class TestWalletCreation:
    """Wallet instantiation via create(), from_mnemonic(), from_keys()."""

    def test_create_returns_wallet_with_mnemonic(self):
        wallet = RustChainPQWallet.create()
        assert wallet.mnemonic is not None
        assert len(wallet.mnemonic.split()) == 24

    def test_create_produces_unique_wallets(self):
        w1 = RustChainPQWallet.create()
        w2 = RustChainPQWallet.create()
        assert w1.address != w2.address
        assert w1.ed_public_key != w2.ed_public_key

    def test_from_mnemonic_restores_same_ed25519_keys(self):
        wallet = RustChainPQWallet.create()
        restored = RustChainPQWallet.from_mnemonic(
            wallet.mnemonic, allow_nondeterministic_pq=True
        )
        assert restored.ed_public_key == wallet.ed_public_key
        assert restored.ed_private_key == wallet.ed_private_key
        assert restored.legacy_address == wallet.legacy_address

    def test_from_mnemonic_refuses_nondeterministic_by_default(self):
        wallet = RustChainPQWallet.create()
        with pytest.raises(RuntimeError, match="Deterministic ML-DSA-44"):
            RustChainPQWallet.from_mnemonic(wallet.mnemonic)

    def test_from_mnemonic_invalid_phrase_raises(self):
        with pytest.raises(ValueError, match="Invalid mnemonic"):
            RustChainPQWallet.from_mnemonic("not a valid mnemonic phrase at all")

    def test_from_mnemonic_with_passphrase_differs(self):
        wallet = RustChainPQWallet.create()
        restored_no_pass = RustChainPQWallet.from_mnemonic(
            wallet.mnemonic, allow_nondeterministic_pq=True
        )
        restored_pass = RustChainPQWallet.from_mnemonic(
            wallet.mnemonic, "secret", allow_nondeterministic_pq=True
        )
        assert restored_no_pass.ed_public_key != restored_pass.ed_public_key

    def test_from_keys_restores_wallet(self):
        wallet = RustChainPQWallet.create()
        restored = RustChainPQWallet.from_keys(
            wallet.ed_private_key,
            wallet.pq_public_key,
            wallet._pq_secret_key.hex(),
        )
        assert restored.address == wallet.address
        assert restored.legacy_address == wallet.legacy_address
        assert restored.mnemonic is None  # from_keys does not carry mnemonic


# ── Address format ───────────────────────────────────────────


class TestAddressFormat:
    """Address prefix, derivation, and legacy vs PQ distinction."""

    def test_pq_address_has_rtcq_prefix(self):
        wallet = RustChainPQWallet.create()
        assert wallet.address.startswith(PREFIX_PQ)

    def test_legacy_address_has_rtc_prefix(self):
        wallet = RustChainPQWallet.create()
        assert wallet.legacy_address.startswith(PREFIX_LEGACY)
        assert not wallet.legacy_address.startswith(PREFIX_PQ)

    def test_pq_address_derived_from_both_pubkeys(self):
        wallet = RustChainPQWallet.create()
        ed_bytes = bytes.fromhex(wallet.ed_public_key)
        pq_bytes = wallet.pq_public_key_bytes
        combined_hash = hashlib.sha256(ed_bytes + pq_bytes).hexdigest()[:40]
        expected = f"{PREFIX_PQ}{combined_hash}"
        assert wallet.address == expected

    def test_legacy_address_derived_from_ed25519_only(self):
        wallet = RustChainPQWallet.create()
        pubkey_hash = hashlib.sha256(bytes.fromhex(wallet.ed_public_key)).hexdigest()[:40]
        expected = f"{PREFIX_LEGACY}{pubkey_hash}"
        assert wallet.legacy_address == expected

    def test_pq_and_legacy_addresses_differ(self):
        wallet = RustChainPQWallet.create()
        assert wallet.address != wallet.legacy_address

    def test_address_length(self):
        wallet = RustChainPQWallet.create()
        # RTCQ + 40 hex chars = 44
        assert len(wallet.address) == 44
        # RTC + 40 hex chars = 43
        assert len(wallet.legacy_address) == 43


# ── Key sizes ────────────────────────────────────────────────


class TestKeySizes:
    """Verify cryptographic key and signature sizes per spec."""

    def test_ed25519_public_key_is_32_bytes(self):
        wallet = RustChainPQWallet.create()
        assert len(bytes.fromhex(wallet.ed_public_key)) == 32

    def test_mldsa_public_key_is_1312_bytes(self):
        wallet = RustChainPQWallet.create()
        assert len(wallet.pq_public_key_bytes) == 1312

    def test_mldsa_signature_is_2420_bytes(self):
        wallet = RustChainPQWallet.create()
        tx = wallet.sign_transaction("RTCQdest", 1.0, nonce=1000)
        pq_sig_bytes = bytes.fromhex(tx["pq_signature"])
        assert len(pq_sig_bytes) == 2420

    def test_ed25519_signature_is_64_bytes(self):
        wallet = RustChainPQWallet.create()
        tx = wallet.sign_transaction("RTCQdest", 1.0, nonce=1000)
        ed_sig_bytes = bytes.fromhex(tx["signature"])
        assert len(ed_sig_bytes) == 64


# ── Hybrid signing ───────────────────────────────────────────


class TestHybridSigning:
    """sign_transaction() produces both Ed25519 and ML-DSA sigs."""

    def test_sign_transaction_has_both_signatures(self):
        wallet = RustChainPQWallet.create()
        tx = wallet.sign_transaction("RTCQrecipient", 50.0, nonce=12345)
        assert "signature" in tx
        assert "pq_signature" in tx
        assert tx["signature_scheme"] == "hybrid-ed25519-mldsa44"

    def test_sign_transaction_includes_both_public_keys(self):
        wallet = RustChainPQWallet.create()
        tx = wallet.sign_transaction("RTCQrecipient", 50.0, nonce=12345)
        assert tx["public_key"] == wallet.ed_public_key
        assert tx["pq_public_key"] == wallet.pq_public_key

    def test_sign_transaction_from_address_is_pq(self):
        wallet = RustChainPQWallet.create()
        tx = wallet.sign_transaction("RTCQrecipient", 50.0, nonce=12345)
        assert tx["from_address"] == wallet.address
        assert tx["from_address"].startswith(PREFIX_PQ)

    def test_sign_transaction_includes_legacy_address(self):
        wallet = RustChainPQWallet.create()
        tx = wallet.sign_transaction("RTCQrecipient", 50.0, nonce=12345)
        assert tx["legacy_address"] == wallet.legacy_address

    def test_sign_message_returns_both_sigs(self):
        wallet = RustChainPQWallet.create()
        sigs = wallet.sign_message(b"hello world")
        assert "ed25519" in sigs
        assert "ml_dsa_44" in sigs

    def test_sign_transaction_preserves_amount_and_memo(self):
        wallet = RustChainPQWallet.create()
        tx = wallet.sign_transaction("RTCQx", 99.5, memo="test memo", nonce=42)
        assert tx["amount_rtc"] == 99.5
        assert tx["memo"] == "test memo"
        assert tx["nonce"] == 42


# ── Hybrid verification ─────────────────────────────────────


class TestHybridVerification:
    """verify_hybrid_transaction() checks both sigs + address binding."""

    def test_valid_hybrid_transaction_passes(self):
        wallet = RustChainPQWallet.create()
        tx = wallet.sign_transaction("RTCQtarget", 10.0, nonce=100)
        result = verify_hybrid_transaction(tx)
        assert result["ed25519_valid"] is True
        assert result["ml_dsa_44_valid"] is True
        assert result["address_valid"] is True
        assert result["fully_valid"] is True

    def test_verify_hybrid_signature_standalone(self):
        wallet = RustChainPQWallet.create()
        msg = b"standalone message"
        sigs = wallet.sign_message(msg)
        result = verify_hybrid_signature(
            wallet.ed_public_key,
            wallet.pq_public_key,
            msg,
            sigs["ed25519"],
            sigs["ml_dsa_44"],
        )
        assert result["hybrid_valid"] is True


# ── Legacy compatibility ─────────────────────────────────────


class TestLegacyCompatibility:
    """verify_legacy_or_hybrid() accepts both Ed25519-only and hybrid."""

    def test_hybrid_transaction_accepted(self):
        wallet = RustChainPQWallet.create()
        tx = wallet.sign_transaction("RTCQrecip", 5.0, nonce=200)
        assert verify_legacy_or_hybrid(tx) is True

    def test_legacy_ed25519_only_transaction_accepted(self):
        wallet = RustChainPQWallet.create()
        # Build a legacy-style transaction (Ed25519-only, RTC prefix)
        nonce = 300
        tx_data = {
            "from": wallet.legacy_address,
            "to": "RTCrecipient123",
            "amount": 25.0,
            "memo": "",
            "nonce": nonce,
        }
        message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()
        ed_sig = wallet.sign_ed25519_only(message)

        legacy_tx = {
            "from_address": wallet.legacy_address,
            "to_address": "RTCrecipient123",
            "amount_rtc": 25.0,
            "memo": "",
            "nonce": nonce,
            "signature": ed_sig,
            "public_key": wallet.ed_public_key,
        }
        assert verify_legacy_or_hybrid(legacy_tx) is True

    def test_legacy_transaction_with_wrong_sig_rejected(self):
        wallet = RustChainPQWallet.create()
        nonce = 400
        tx_data = {
            "from": wallet.legacy_address,
            "to": "RTCrecipient",
            "amount": 10.0,
            "memo": "",
            "nonce": nonce,
        }
        message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()
        ed_sig = wallet.sign_ed25519_only(message)

        legacy_tx = {
            "from_address": wallet.legacy_address,
            "to_address": "RTCrecipient",
            "amount_rtc": 10.0,
            "memo": "",
            "nonce": nonce,
            "signature": "ff" * 64,  # fake signature
            "public_key": wallet.ed_public_key,
        }
        assert verify_legacy_or_hybrid(legacy_tx) is False


# ── Ed25519-only signing ─────────────────────────────────────


class TestEd25519OnlySigning:
    """sign_ed25519_only() for legacy backward compatibility."""

    def test_sign_ed25519_only_returns_hex_string(self):
        wallet = RustChainPQWallet.create()
        sig = wallet.sign_ed25519_only(b"legacy message")
        assert isinstance(sig, str)
        assert len(bytes.fromhex(sig)) == 64

    def test_sign_ed25519_only_verifies(self):
        from nacl.signing import VerifyKey

        wallet = RustChainPQWallet.create()
        msg = b"verify this"
        sig = wallet.sign_ed25519_only(msg)
        vk = VerifyKey(bytes.fromhex(wallet.ed_public_key))
        # Should not raise
        vk.verify(msg, bytes.fromhex(sig))


# ── Keystore v2 ──────────────────────────────────────────────


class TestKeystoreV2:
    """export_encrypted() / from_encrypted() round-trip."""

    def test_round_trip(self):
        wallet = RustChainPQWallet.create()
        encrypted = wallet.export_encrypted("strong_password_123")
        restored = RustChainPQWallet.from_encrypted(encrypted, "strong_password_123")
        assert restored.address == wallet.address
        assert restored.legacy_address == wallet.legacy_address
        assert restored.ed_public_key == wallet.ed_public_key
        assert restored.pq_public_key == wallet.pq_public_key

    def test_keystore_version_is_2(self):
        wallet = RustChainPQWallet.create()
        encrypted = wallet.export_encrypted("pass")
        assert encrypted["version"] == KEYSTORE_VERSION_PQ
        assert encrypted["version"] == 2

    def test_keystore_contains_both_addresses(self):
        wallet = RustChainPQWallet.create()
        encrypted = wallet.export_encrypted("pass")
        assert encrypted["address"] == wallet.address
        assert encrypted["legacy_address"] == wallet.legacy_address

    def test_keystore_has_signature_scheme(self):
        wallet = RustChainPQWallet.create()
        encrypted = wallet.export_encrypted("pass")
        assert encrypted["signature_scheme"] == "hybrid-ed25519-mldsa44"

    def test_restored_wallet_signs_and_verifies(self):
        wallet = RustChainPQWallet.create()
        encrypted = wallet.export_encrypted("roundtrip")
        restored = RustChainPQWallet.from_encrypted(encrypted, "roundtrip")
        tx = restored.sign_transaction("RTCQverify", 7.77, nonce=999)
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is True


# ── Wrong password ───────────────────────────────────────────


class TestWrongPassword:
    """from_encrypted with bad password raises ValueError."""

    def test_wrong_password_raises_valueerror(self):
        wallet = RustChainPQWallet.create()
        encrypted = wallet.export_encrypted("correct_password")
        with pytest.raises(ValueError, match="Invalid password"):
            RustChainPQWallet.from_encrypted(encrypted, "wrong_password")

    def test_legacy_keystore_version_raises(self):
        wallet = RustChainPQWallet.create()
        encrypted = wallet.export_encrypted("pass")
        encrypted["version"] = 1  # Downgrade to legacy
        with pytest.raises(ValueError, match="Legacy keystore v1"):
            RustChainPQWallet.from_encrypted(encrypted, "pass")


# ── Signature tampering ──────────────────────────────────────


class TestSignatureTampering:
    """Modified signatures or transaction fields must fail verification."""

    def _make_valid_tx(self):
        wallet = RustChainPQWallet.create()
        return wallet.sign_transaction("RTCQtampertest", 42.0, nonce=555)

    def test_tampered_ed25519_signature_fails(self):
        tx = self._make_valid_tx()
        # Flip a byte in the Ed25519 signature
        sig_bytes = bytearray(bytes.fromhex(tx["signature"]))
        sig_bytes[0] ^= 0xFF
        tx["signature"] = sig_bytes.hex()
        result = verify_hybrid_transaction(tx)
        assert result["ed25519_valid"] is False
        assert result["fully_valid"] is False

    def test_tampered_mldsa_signature_detected_by_raw_verify(self):
        """ML-DSA tampered sig is detected by the raw verify function.

        NOTE: verify_hybrid_transaction has a known bug where it ignores
        mldsa_verify's return value (only catches exceptions). The raw
        pqcrypto.sign.ml_dsa_44.verify correctly returns False for bad sigs.
        This test verifies the underlying crypto works; the integration bug
        is documented in test_mldsa_verify_bug_returns_not_raises.
        """
        from pqcrypto.sign.ml_dsa_44 import verify as raw_mldsa_verify

        wallet = RustChainPQWallet.create()
        msg = b"tamper test"
        sigs = wallet.sign_message(msg)
        sig_bytes = bytearray(bytes.fromhex(sigs["ml_dsa_44"]))
        sig_bytes[100] ^= 0xFF  # tamper
        valid = raw_mldsa_verify(
            wallet.pq_public_key_bytes, msg, bytes(sig_bytes)
        )
        assert valid is False

    def test_tampered_mldsa_sig_correctly_rejected(self):
        """Verify tampered ML-DSA sigs are rejected (bug fix applied).

        Previously mldsa_verify returning False was not checked — only
        exceptions were caught. Fixed in rustchain_crypto_pq.py to check
        the return value.
        """
        tx = self._make_valid_tx()
        sig_bytes = bytearray(bytes.fromhex(tx["pq_signature"]))
        sig_bytes[100] ^= 0xFF
        tx["pq_signature"] = sig_bytes.hex()
        result = verify_hybrid_transaction(tx)
        assert result["ml_dsa_44_valid"] is False  # FIXED: now correctly rejected
        assert result["ed25519_valid"] is True  # Ed25519 untampered
        assert result["hybrid_valid"] is False  # Both must pass

    def test_tampered_amount_fails(self):
        tx = self._make_valid_tx()
        tx["amount_rtc"] = 999.0  # Changed from 42.0
        result = verify_hybrid_transaction(tx)
        # Message changes, so both sigs should fail
        assert result["fully_valid"] is False

    def test_tampered_to_address_fails(self):
        tx = self._make_valid_tx()
        tx["to_address"] = "RTCQhacker"
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False

    def test_tampered_nonce_fails(self):
        tx = self._make_valid_tx()
        tx["nonce"] = 999999
        result = verify_hybrid_transaction(tx)
        assert result["fully_valid"] is False


# ── Address binding ──────────────────────────────────────────


class TestAddressBinding:
    """Wrong pubkey combination causes address mismatch."""

    def test_wrong_pq_pubkey_fails_address_binding(self):
        wallet_a = RustChainPQWallet.create()
        wallet_b = RustChainPQWallet.create()
        tx = wallet_a.sign_transaction("RTCQdest", 10.0, nonce=700)
        # Swap in wallet_b's PQ public key (address won't match)
        tx["pq_public_key"] = wallet_b.pq_public_key
        result = verify_hybrid_transaction(tx)
        assert result["address_valid"] is False
        assert result["fully_valid"] is False

    def test_wrong_ed_pubkey_fails_address_binding(self):
        wallet_a = RustChainPQWallet.create()
        wallet_b = RustChainPQWallet.create()
        tx = wallet_a.sign_transaction("RTCQdest", 10.0, nonce=800)
        # Swap in wallet_b's Ed25519 public key
        tx["public_key"] = wallet_b.ed_public_key
        result = verify_hybrid_transaction(tx)
        assert result["address_valid"] is False
        assert result["fully_valid"] is False


# ── Cross-verification ───────────────────────────────────────


class TestCrossVerification:
    """Wallet A signs, wallet B's keys cannot verify."""

    def test_different_wallet_fails_ed25519_verification(self):
        """Wallet A signs, wallet B's keys used for verification.

        Ed25519 correctly rejects. ML-DSA has the return-value bug
        (see TestSignatureTampering.test_mldsa_verify_bug_returns_not_raises).
        Even with the bug, fully_valid is False because Ed25519 fails.
        """
        wallet_a = RustChainPQWallet.create()
        wallet_b = RustChainPQWallet.create()
        tx = wallet_a.sign_transaction("RTCQcross", 15.0, nonce=900)
        # Replace pubkeys with wallet_b's (sigs were made by wallet_a)
        tx["public_key"] = wallet_b.ed_public_key
        tx["pq_public_key"] = wallet_b.pq_public_key
        # Recompute from_address so address binding would pass
        combined = bytes.fromhex(wallet_b.ed_public_key) + wallet_b.pq_public_key_bytes
        tx["from_address"] = f"RTCQ{hashlib.sha256(combined).hexdigest()[:40]}"
        result = verify_hybrid_transaction(tx)
        assert result["ed25519_valid"] is False
        # fully_valid fails because Ed25519 catches it
        assert result["fully_valid"] is False

    def test_raw_mldsa_rejects_cross_wallet(self):
        """Verify that the underlying ML-DSA crypto correctly rejects
        a signature verified with the wrong public key."""
        from pqcrypto.sign.ml_dsa_44 import verify as raw_mldsa_verify

        wallet_a = RustChainPQWallet.create()
        wallet_b = RustChainPQWallet.create()
        msg = b"cross wallet test"
        sigs = wallet_a.sign_message(msg)
        # Verify with wallet_b's PQ key -- should fail
        valid = raw_mldsa_verify(
            wallet_b.pq_public_key_bytes, msg, bytes.fromhex(sigs["ml_dsa_44"])
        )
        assert valid is False

    def test_verify_legacy_or_hybrid_rejects_cross_wallet(self):
        wallet_a = RustChainPQWallet.create()
        wallet_b = RustChainPQWallet.create()
        tx = wallet_a.sign_transaction("RTCQcross2", 20.0, nonce=950)
        # Swap both keys and recompute address
        tx["public_key"] = wallet_b.ed_public_key
        tx["pq_public_key"] = wallet_b.pq_public_key
        combined = bytes.fromhex(wallet_b.ed_public_key) + wallet_b.pq_public_key_bytes
        tx["from_address"] = f"RTCQ{hashlib.sha256(combined).hexdigest()[:40]}"
        assert verify_legacy_or_hybrid(tx) is False
