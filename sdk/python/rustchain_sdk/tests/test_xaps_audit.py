"""
Tests for XAPS - Cross-protocol Audit System.
"""

import json
import time

import pytest

from rustchain_sdk.wallet import RustChainWallet
from rustchain_sdk.xaps_audit import (
    XAPSInspector,
    XAPSResult,
    XAPSAuditError,
    XAPSPolicy,
    audit_transfer,
    audit_governance_vote,
    audit_attestation,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def wallet() -> RustChainWallet:
    return RustChainWallet.create(strength=128)


@pytest.fixture()
def valid_transfer(wallet: RustChainWallet) -> dict:
    return wallet.sign_transfer(
        to_address="RTC1234567890abcdef1234567890abcdef12345678",
        amount=100.0,
        fee=1.0,
        nonce=1700000000,
    )


@pytest.fixture()
def valid_vote_payload(wallet: RustChainWallet) -> dict:
    payload = {
        "voter": wallet.address,
        "proposal_id": 1,
        "vote": "yes",
        "signature": wallet.sign(b"vote").hex(),
        "public_key": wallet.public_key_hex,
    }
    return payload


@pytest.fixture()
def valid_attestation_payload(wallet: RustChainWallet) -> dict:
    payload = {
        "miner_public_key": wallet.public_key_hex,
        "challenge_response": "valid-response",
        "signature": wallet.sign(b"challenge").hex(),
        "public_key": wallet.public_key_hex,
    }
    return payload


# ── XAPSResult tests ────────────────────────────────────────────────────────


class TestXAPSResult:
    def test_approved(self):
        r = XAPSResult.approved(reason="ok")
        assert r.approved is True
        assert r.reason == "ok"

    def test_rejected(self):
        r = XAPSResult.rejected(reason="fail", details={"code": 42})
        assert r.approved is False
        assert r.reason == "fail"
        assert r.details["code"] == 42

    def test_repr_approved(self):
        r = XAPSResult.approved()
        assert "PASS" in repr(r)

    def test_repr_rejected(self):
        r = XAPSResult.rejected(reason="boom")
        assert "FAIL(boom)" in repr(r)


# ── _SlidingWindowRateLimiter tests ─────────────────────────────────────────


class TestSlidingWindowRateLimiter:
    def test_allows_within_limit(self):
        from rustchain_sdk.xaps_audit import _SlidingWindowRateLimiter

        rl = _SlidingWindowRateLimiter(max_actions=3, window_seconds=60)
        assert rl.allow("src") is True
        assert rl.allow("src") is True
        assert rl.allow("src") is True
        assert rl.allow("src") is False  # 4th should fail

    def test_separate_sources(self):
        from rustchain_sdk.xaps_audit import _SlidingWindowRateLimiter

        rl = _SlidingWindowRateLimiter(max_actions=2, window_seconds=60)
        assert rl.allow("A") is True
        assert rl.allow("A") is True
        assert rl.allow("A") is False

        assert rl.allow("B") is True  # different source
        assert rl.allow("B") is True

    def test_cleanup_after_window(self):
        from rustchain_sdk.xaps_audit import _SlidingWindowRateLimiter

        rl = _SlidingWindowRateLimiter(max_actions=2, window_seconds=0.1)
        assert rl.allow("src") is True
        assert rl.allow("src") is True
        assert rl.allow("src") is False

        time.sleep(0.15)  # wait for window to expire
        assert rl.allow("src") is True  # should be allowed again


# ── Inspector: signature checks ─────────────────────────────────────────────


class TestInspectorSignature:
    def test_valid_signature(self, valid_transfer: dict):
        ins = XAPSInspector()
        result = ins.inspect_transfer(valid_transfer)
        assert result.approved

    def test_missing_signature(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "amount": 10,
            "fee": 1,
        }
        with pytest.raises(XAPSAuditError, match="xaps_signature_check_failed"):
            ins.inspect_transfer(payload)

    def test_bad_signature_length(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "signature": "short",
            "public_key": "a" * 64,
            "amount": 10,
            "fee": 1,
        }
        with pytest.raises(XAPSAuditError, match="xaps_signature_check_failed"):
            ins.inspect_transfer(payload)

    def test_non_hex_signature(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "signature": "g" * 128,  # 'g' is not valid hex
            "public_key": "a" * 64,
            "amount": 10,
            "fee": 1,
        }
        with pytest.raises(XAPSAuditError, match="xaps_signature_check_failed"):
            ins.inspect_transfer(payload)

    def test_invalid_public_key(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "signature": "f" * 128,
            "public_key": "badkey",
            "amount": 10,
            "fee": 1,
        }
        with pytest.raises(XAPSAuditError, match="xaps_signature_check_failed"):
            ins.inspect_transfer(payload)


# ── Inspector: target validation ────────────────────────────────────────────


class TestInspectorTarget:
    def test_valid_target(self, valid_transfer: dict):
        ins = XAPSInspector()
        result = ins.inspect_transfer(valid_transfer)
        assert result.approved

    def test_missing_target(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "amount": 10,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        with pytest.raises(XAPSAuditError, match="xaps_target_check_failed"):
            ins.inspect_transfer(payload)

    def test_bad_prefix(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "BTC1234567890abcdef1234567890abcdef12345678",
            "amount": 10,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        with pytest.raises(XAPSAuditError, match="xaps_target_check_failed"):
            ins.inspect_transfer(payload)

    def test_bad_length(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC123",  # too short
            "amount": 10,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        with pytest.raises(XAPSAuditError, match="xaps_target_check_failed"):
            ins.inspect_transfer(payload)

    def test_non_hex_body(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTCZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ",
            "amount": 10,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        with pytest.raises(XAPSAuditError, match="xaps_target_check_failed"):
            ins.inspect_transfer(payload)


# ── Inspector: side-effect audit ────────────────────────────────────────────


class TestInspectorSideEffects:
    def test_valid_side_effects(self, valid_transfer: dict):
        ins = XAPSInspector()
        result = ins.inspect_transfer(valid_transfer)
        assert result.approved

    def test_memo_too_long(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "amount": 10,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
            "memo": "x" * 2000,  # exceeds 1024 bytes
        }
        with pytest.raises(XAPSAuditError, match="xaps_side_effects_check_failed"):
            ins.inspect_transfer(payload)

    def test_memo_unexpected_chars(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "amount": 10,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
            "memo": "hello\x00world",  # null byte
        }
        with pytest.raises(XAPSAuditError, match="xaps_side_effects_check_failed"):
            ins.inspect_transfer(payload)

    def test_negative_amount(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "amount": -5,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        with pytest.raises(XAPSAuditError, match="xaps_side_effects_check_failed"):
            ins.inspect_transfer(payload)

    def test_negative_fee(self):
        ins = XAPSInspector()
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "amount": 10,
            "fee": -1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        with pytest.raises(XAPSAuditError, match="xaps_side_effects_check_failed"):
            ins.inspect_transfer(payload)


# ── Inspector: rate limiting ────────────────────────────────────────────────


class TestInspectorRateLimit:
    def test_rate_limit_exceeded(self):
        ins = XAPSInspector(
            max_actions=2,
            window_seconds=60,
        )
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "amount": 10,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        ins.inspect_transfer(payload)  # 1st OK
        ins.inspect_transfer(payload)  # 2nd OK
        with pytest.raises(XAPSAuditError, match="xaps_rate_limit_exceeded"):
            ins.inspect_transfer(payload)  # 3rd blocked


# ── Custom policies ─────────────────────────────────────────────────────────


class _BlockAllPolicy(XAPSPolicy):
    name = "block_all"

    def check(self, action_type, payload, inspector):
        return XAPSResult.rejected("always blocked")


class TestInspectorCustomPolicy:
    def test_custom_policy_blocks(self):
        ins = XAPSInspector()
        ins.add_policy(_BlockAllPolicy())
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "amount": 10,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        with pytest.raises(XAPSAuditError, match="xaps_policy_block_all_rejected"):
            ins.inspect_transfer(payload)

    def test_custom_policy_allows(self):
        class AllowAllPolicy(XAPSPolicy):
            name = "allow_all"
            def check(self, action_type, payload, inspector):
                return XAPSResult.approved()

        ins = XAPSInspector()
        ins.add_policy(AllowAllPolicy())
        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "amount": 10,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        result = ins.inspect_transfer(payload)
        assert result.approved

    def test_policy_removal(self):
        ins = XAPSInspector()
        blocker = _BlockAllPolicy()
        ins.add_policy(blocker)
        ins.remove_policy(blocker)

        payload = {
            "from_address": "RTC1234567890abcdef1234567890abcdef12345678",
            "to_address": "RTC0000000000000000000000000000000000000000",
            "amount": 10,
            "fee": 1,
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        # Should succeed after policy removed
        result = ins.inspect_transfer(payload)
        assert result.approved


# ── Governance vote audit ───────────────────────────────────────────────────


class TestGovernanceVoteAudit:
    def test_valid_vote(self, valid_vote_payload: dict):
        ins = XAPSInspector()
        result = ins.inspect_governance_vote(valid_vote_payload)
        assert result.approved

    def test_invalid_vote_value(self, valid_vote_payload: dict):
        valid_vote_payload["vote"] = "maybe"
        ins = XAPSInspector()
        with pytest.raises(XAPSAuditError, match="xaps_invalid_vote_value"):
            ins.inspect_governance_vote(valid_vote_payload)

    def test_invalid_proposal_id(self, valid_vote_payload: dict):
        valid_vote_payload["proposal_id"] = -1
        ins = XAPSInspector()
        with pytest.raises(XAPSAuditError, match="xaps_invalid_proposal_id"):
            ins.inspect_governance_vote(valid_vote_payload)

    def test_missing_vote_value(self, valid_vote_payload: dict):
        del valid_vote_payload["vote"]
        ins = XAPSInspector()
        with pytest.raises(XAPSAuditError, match="xaps_invalid_vote_value"):
            ins.inspect_governance_vote(valid_vote_payload)


# ── Attestation audit ───────────────────────────────────────────────────────


class TestAttestationAudit:
    def test_valid_attestation(self, valid_attestation_payload: dict):
        ins = XAPSInspector()
        result = ins.inspect_attestation(valid_attestation_payload)
        assert result.approved

    def test_missing_miner_id(self):
        ins = XAPSInspector()
        payload = {
            "challenge_response": "resp",
            "signature": "f" * 128,
            "public_key": "a" * 64,
        }
        with pytest.raises(XAPSAuditError, match="xaps_missing_miner_id"):
            ins.inspect_attestation(payload)


# ── Convenience functions ───────────────────────────────────────────────────


class TestConvenienceFunctions:
    def test_audit_transfer_success(self, valid_transfer: dict):
        result = audit_transfer(valid_transfer)
        assert result.approved

    def test_audit_transfer_failure(self):
        with pytest.raises(XAPSAuditError):
            audit_transfer({})

    def test_audit_governance_vote_success(self, valid_vote_payload: dict):
        result = audit_governance_vote(valid_vote_payload)
        assert result.approved

    def test_audit_attestation_success(self, valid_attestation_payload: dict):
        result = audit_attestation(valid_attestation_payload)
        assert result.approved


# ── Integration: real wallet round-trip ─────────────────────────────────────


class TestIntegrationRoundTrip:
    """End-to-end: sign with wallet → audit with XAPS → verify result."""

    def test_signed_transfer_passes_xaps(self, wallet: RustChainWallet):
        transfer = wallet.sign_transfer(
            to_address="RTC1234567890abcdef1234567890abcdef12345678",
            amount=50.0,
            fee=0.5,
        )
        ins = XAPSInspector()
        result = ins.inspect_transfer(transfer)
        assert result.approved

    def test_signed_transfer_with_memo_passes_xaps(self, wallet: RustChainWallet):
        transfer = wallet.sign_transfer(
            to_address="RTC1234567890abcdef1234567890abcdef12345678",
            amount=50.0,
            fee=0.5,
            memo="test audit integration",
        )
        ins = XAPSInspector()
        result = ins.inspect_transfer(transfer)
        assert result.approved

    def test_two_wallets_transfer_passes_xaps(self):
        sender = RustChainWallet.create(strength=128)
        receiver = RustChainWallet.create(strength=128)

        transfer = sender.sign_transfer(
            to_address=receiver.address,
            amount=100.0,
            fee=2.0,
            nonce=1700000000,
        )
        ins = XAPSInspector()
        result = ins.inspect_transfer(transfer)
        assert result.approved

    def test_vote_with_signed_signature_passes_xaps(self, wallet: RustChainWallet):
        payload = {
            "voter": wallet.address,
            "proposal_id": 42,
            "vote": "no",
            "signature": wallet.sign(b"vote_payload").hex(),
            "public_key": wallet.public_key_hex,
        }
        ins = XAPSInspector()
        result = ins.inspect_governance_vote(payload)
        assert result.approved
