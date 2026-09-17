import pytest
from bridges.ergo.bridge_daemon import ErgoRTCBridge

def test_eip4_metadata():
    bridge = ErgoRTCBridge()
    meta = bridge.format_eip4_token_metadata()
    assert meta["symbol"] == "RTC"
    assert meta["decimals"] == 6
    assert "token_id" in meta

def test_rustchain_lock_and_threshold_mint():
    bridge = ErgoRTCBridge()
    lock = bridge.process_rustchain_lock(
        tx_hash="tx_lock_01",
        sender_rtc="RTC8b1fb717791b0a7b72649342b5c7c7bd822786af",
        ergo_recipient_p2pk="9f4QF8AD1nQ3nEAQVkcmdtPdKFCWPDnHGnzt4kJvCJWuLMtRNhk",
        amount_rtc=50.0
    )
    assert lock["amount_micro_rtc"] == 50_000_000
    assert lock["status"] == "pending_mint"

    # 1 sig should fail quorum
    with pytest.raises(ValueError, match="Quorum failed"):
        bridge.generate_ergo_mint_tx("tx_lock_01", ["sig1"])

    # 2 sigs should succeed
    mint_tx = bridge.generate_ergo_mint_tx("tx_lock_01", ["sig1", "sig2"])
    assert mint_tx["outputs"][0]["assets"][0]["amount"] == 50_000_000
    assert mint_tx["outputs"][0]["address"] == "9f4QF8AD1nQ3nEAQVkcmdtPdKFCWPDnHGnzt4kJvCJWuLMtRNhk"
    assert bridge.locks["tx_lock_01"]["status"] == "minted"

def test_ergo_burn_to_unlock():
    bridge = ErgoRTCBridge()
    burn = bridge.process_ergo_burn(
        ergo_tx_id="ergo_burn_01",
        ergo_sender="9f4QF8AD1nQ3nEAQVkcmdtPdKFCWPDnHGnzt4kJvCJWuLMtRNhk",
        rustchain_recipient="RTC8b1fb717791b0a7b72649342b5c7c7bd822786af",
        burned_e_rtc=25.0
    )
    assert burn["amount_rtc"] == 25.0
    assert burn["status"] == "unlocked"

def test_invalid_recipient_formats():
    bridge = ErgoRTCBridge()
    with pytest.raises(ValueError, match="Invalid Ergo P2PK"):
        bridge.process_rustchain_lock("tx1", "RTC1", "0xInvalid", 10.0)

    with pytest.raises(ValueError, match="Invalid native RTC"):
        bridge.process_ergo_burn("tx2", "9f4Q", "0xInvalid", 10.0)
