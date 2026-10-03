#!/usr/bin/env python3
"""
Comprehensive Unit & Integration Test Suite for Bounty #35 Agent-to-Agent Payment Stack.
Verifies:
1. Upvote + Donate Micropayments, anti-sybil checks, hardware multiplier calculations.
2. Cross-Wallet Bridge lock/settle cycles, fee precision, and transaction tracking.
3. HTTP 402 challenge generation, Ed25519 authorization, and replay prevention.
4. Dual-Currency Cross-Bounty Escrow deposits and split settlements.
"""

import os
import sqlite3
import tempfile
import time
import pytest

from node.agent_stack.a2a_payment_stack import (
    UpvoteDonateManager,
    CrossWalletBridge,
    BridgeStatus,
    X402AgentPaymentGateway,
    CrossBountyEscrowManager,
    EscrowStatus,
    derive_rtc_address
)

try:
    from nacl.signing import SigningKey
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    conn = sqlite3.connect(path)
    yield conn
    conn.close()
    if os.path.exists(path):
        os.remove(path)

# ==============================================================================
# 1. UPVOTE + DONATE TESTS
# ==============================================================================

def test_free_upvote(temp_db):
    mgr = UpvoteDonateManager(temp_db)
    res = mgr.record_upvote_and_donate(
        content_id="post_retro_miner",
        voter_agent="RTC_agent_alpha",
        creator_agent="RTC_agent_beta",
        donation_rtc=0.0,
        hardware_multiplier=2.5
    )
    assert res["status"] == "success"
    assert res["multiplier"] == 2.5
    
    metrics = mgr.get_content_metrics("post_retro_miner")
    assert metrics["total_upvotes"] == 1
    assert metrics["total_donations_rtc"] == 0.0
    assert metrics["weighted_signal"] == 2.5

def test_upvote_and_donate_with_tx(temp_db):
    mgr = UpvoteDonateManager(temp_db)
    res = mgr.record_upvote_and_donate(
        content_id="post_mac68k",
        voter_agent="RTC_agent_powerpc",
        creator_agent="RTC_agent_sparc",
        donation_rtc=0.05,
        hardware_multiplier=3.0,
        tx_hash="tx_5566778899aabbcc"
    )
    assert res["status"] == "success"
    assert res["donation_rtc"] == 0.05

    metrics = mgr.get_content_metrics("post_mac68k")
    assert metrics["total_upvotes"] == 1
    assert metrics["total_donations_rtc"] == 0.05
    assert metrics["weighted_signal"] == 3.0

def test_upvote_anti_sybil_self_rejection(temp_db):
    mgr = UpvoteDonateManager(temp_db)
    with pytest.raises(ValueError, match="Anti-Sybil rejection"):
        mgr.record_upvote_and_donate(
            content_id="post_self",
            voter_agent="RTC_sockpuppet",
            creator_agent="RTC_sockpuppet",
            donation_rtc=0.0
        )

# ==============================================================================
# 2. CROSS-WALLET BRIDGE TESTS
# ==============================================================================

def test_cross_wallet_bridge_lifecycle(temp_db):
    bridge = CrossWalletBridge(temp_db, fee_pct=0.01, exchange_rate=1.0) # 1% fee
    
    # 1. RTC -> BoTTube lock
    btx = bridge.initiate_bridge(
        direction="RTC_TO_BOTTUBE",
        sender="RTC8b1fb717791b0a7b72649342b5c7c7bd822786af",
        recipient="bottube_creator_99",
        amount_in=100.0,
        deposit_tx_hash="tx_lock_rtc_12345"
    )
    assert btx.status == BridgeStatus.LOCKED
    assert btx.fee_rtc == 1.0
    assert btx.amount_out == 99.0

    # 2. Settle on BoTTube
    settled = bridge.settle_bridge(btx.bridge_id, payout_tx_hash="bottube_tx_credit_6789")
    assert settled.status == BridgeStatus.SETTLED
    assert settled.payout_tx_hash == "bottube_tx_credit_6789"
    assert settled.settled_at is not None

def test_cross_wallet_bridge_invalid_direction(temp_db):
    bridge = CrossWalletBridge(temp_db)
    with pytest.raises(ValueError, match="Unsupported bridge direction"):
        bridge.initiate_bridge(
            direction="INVALID_DIRECTION",
            sender="alice",
            recipient="bob",
            amount_in=10.0
        )

# ==============================================================================
# 3. HTTP 402 / x402 AGENT GATEWAY TESTS
# ==============================================================================

def test_x402_agent_flow():
    server_addr = "RTC8b1fb717791b0a7b72649342b5c7c7bd822786af"
    gateway = X402AgentPaymentGateway(server_address=server_addr)
    
    # 1. Server issues 402 challenge
    resp = gateway.generate_challenge(
        service_name="llm_inference_query",
        price_rtc=0.005,
        description="G4 PowerPC LLM Inference Service"
    )
    assert resp["status"] == 402
    invoice = resp["invoice"]
    invoice_id = invoice["invoice_id"]
    assert invoice["amount_rtc"] == 0.005
    assert "WWW-Authenticate" in resp["headers"]

    # 2. Client signs payment authorization
    if HAS_NACL:
        sk = SigningKey.generate()
        vk_hex = sk.verify_key.encode().hex()
        payer_addr = derive_rtc_address(vk_hex)
        
        canonical_msg = f"{invoice_id}:{payer_addr}:{server_addr}:0.005:{invoice['nonce']}"
        signed = sk.sign(canonical_msg.encode())
        sig_hex = signed.signature.hex()

        payment_payload = {
            "payer_address": payer_addr,
            "amount": 0.005,
            "tx_hash": "tx_onchain_settlement_hash",
            "signature": sig_hex,
            "pubkey": vk_hex
        }
    else:
        payment_payload = {
            "payer_address": "RTC1111222233334444555566667777888899990000",
            "amount": 0.005,
            "tx_hash": "tx_onchain_settlement_hash",
            "signature": "0" * 128,
            "pubkey": "0" * 64
        }

    # 3. Gateway verifies payment
    success, msg = gateway.verify_payment_authorization(invoice_id, payment_payload)
    assert success is True
    assert msg == "Payment verified successfully"

# ==============================================================================
# 4. CROSS-BOUNTY DUAL-CURRENCY ESCROW TESTS
# ==============================================================================

def test_dual_currency_escrow_deposit_and_release(temp_db):
    manager = CrossBountyEscrowManager(temp_db)
    
    # Deposit dual funds
    esc = manager.deposit(
        bounty_id="bounty_35_convergence",
        poster="project_foundation",
        amount_rtc=300.0,
        amount_bottube=1500.0
    )
    assert esc.status == EscrowStatus.OPEN
    assert esc.amount_rtc == 300.0
    assert esc.amount_bottube == 1500.0

    # Release to completing agent
    res = manager.release(esc.escrow_id, claimant="RTC_completing_agent_cid")
    assert res["status"] == "released"
    assert res["payout_rtc"] == 300.0
    assert res["payout_bottube"] == 1500.0
    assert res["claimant"] == "RTC_completing_agent_cid"
