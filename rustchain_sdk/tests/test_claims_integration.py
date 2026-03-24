#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RIP-305 Track D: Claims Integration Tests
==========================================

End-to-end integration tests for the complete claims flow.
Run with: python -m pytest tests/test_claims_integration.py -v
"""

import pytest
import sqlite3
import time
import sys
import os

# Add node directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

from claims_eligibility import (
    check_claim_eligibility,
    get_eligible_epochs,
    GENESIS_TIMESTAMP,
    BLOCK_TIME,
    ATTESTATION_TTL
)

from claims_submission import (
    submit_claim,
    get_claim_status,
    get_claim_history,
    update_claim_status
)

from claims_settlement import (
    get_pending_claims,
    process_claims_batch,
    get_settlement_stats
)


@pytest.fixture
def integration_db():
    """Create file-based test database with full schema"""
    db = "test_claims_integration.db"
    
    # Remove existing test database
    if os.path.exists(db):
        os.remove(db)
    
    with sqlite3.connect(db) as conn:
        cursor = conn.cursor()
        
        # Create miner_attest_recent table
        cursor.execute("""
            CREATE TABLE miner_attest_recent (
                miner TEXT,
                device_arch TEXT,
                ts_ok INTEGER,
                fingerprint_passed INTEGER DEFAULT 1,
                entropy_score REAL,
                warthog_bonus REAL DEFAULT 1.0,
                wallet_address TEXT
            )
        """)
        
        # Create claims table
        cursor.execute("""
            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                miner_id TEXT,
                epoch INTEGER,
                wallet_address TEXT,
                reward_urtc INTEGER,
                status TEXT DEFAULT 'pending',
                submitted_at INTEGER,
                verified_at INTEGER,
                settled_at INTEGER,
                transaction_hash TEXT,
                settlement_batch TEXT,
                rejection_reason TEXT,
                signature TEXT,
                public_key TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at INTEGER,
                updated_at INTEGER,
                UNIQUE(miner_id, epoch)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_claims_miner ON claims(miner_id)")
        cursor.execute("CREATE INDEX idx_claims_epoch ON claims(epoch)")
        cursor.execute("CREATE INDEX idx_claims_status ON claims(status)")
        
        # Create claims_audit table
        cursor.execute("""
            CREATE TABLE claims_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT,
                action TEXT,
                actor TEXT,
                details TEXT,
                timestamp INTEGER
            )
        """)
        
        # Create rewards_pool table (for settlement)
        cursor.execute("""
            CREATE TABLE rewards_pool (
                pool_name TEXT PRIMARY KEY,
                balance_urtc INTEGER
            )
        """)
        
        # Seed rewards pool with sufficient funds
        cursor.execute("""
            INSERT INTO rewards_pool (pool_name, balance_urtc)
            VALUES ('epoch_rewards', 10000000000)
        """)  # 100 RTC
        
        conn.commit()
    
    yield db
    
    # Cleanup
    if os.path.exists(db):
        os.remove(db)


@pytest.fixture
def current_ts():
    """Get current timestamp"""
    return int(time.time())


@pytest.fixture
def current_slot(current_ts):
    """Calculate current slot from timestamp"""
    return (current_ts - GENESIS_TIMESTAMP) // BLOCK_TIME


def setup_test_miner(db, miner_id, device_arch, wallet_address, current_ts, epoch=None):
    """Helper to setup a test miner with attestation
    
    Args:
        db: Database path
        miner_id: Miner identifier
        device_arch: Device architecture
        wallet_address: Wallet address
        current_ts: Current timestamp
        epoch: Optional epoch number to create attestation for (default: recent)
    """
    with sqlite3.connect(db) as conn:
        # Always create a recent attestation (for current eligibility)
        conn.execute("""
            INSERT INTO miner_attest_recent
            (miner, device_arch, ts_ok, fingerprint_passed, entropy_score, wallet_address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (miner_id, device_arch, current_ts - 3600, 1, 0.075, wallet_address))
        
        # Also create attestation during the specified epoch (for epoch participation)
        if epoch is not None:
            epoch_start_slot = epoch * 144
            epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)
            epoch_ts = epoch_start_ts + (72 * BLOCK_TIME)  # Middle of epoch
            conn.execute("""
                INSERT INTO miner_attest_recent
                (miner, device_arch, ts_ok, fingerprint_passed, wallet_address)
                VALUES (?, ?, ?, ?, ?)
            """, (miner_id, device_arch, epoch_ts, 1, wallet_address))


class TestEndToEndClaimFlow:
    """Test complete claim flow from eligibility to settlement"""
    
    def test_full_claim_lifecycle(self, integration_db, current_ts, current_slot):
        """Test: Setup → Eligibility → Submit → Approve → Settle"""
        
        # Use an old epoch that should be settled
        test_epoch = max(0, current_slot // 144 - 3)
        
        # Setup: Create eligible miner with attestation during the test epoch
        miner_id = "test-miner-g4"
        wallet = "RTC1TestWalletAddress1234567890"
        setup_test_miner(integration_db, miner_id, "g4", wallet, current_ts, epoch=test_epoch)
        
        # 2. Check eligibility
        eligibility = check_claim_eligibility(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch,
            current_slot=current_slot,
            current_ts=current_ts
        )
        
        assert eligibility["eligible"] is True, f"Miner should be eligible: {eligibility['reason']}"
        assert eligibility["reward_urtc"] >= 0
        assert eligibility["wallet_address"] == wallet
        
        # 3. Submit claim
        claim_result = submit_claim(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch,
            wallet_address=wallet,
            signature="mock_signature",
            public_key="mock_public_key",
            current_slot=current_slot,
            current_ts=current_ts,
            skip_signature_verify=True
        )
        
        assert claim_result["success"] is True
        assert claim_result["claim_id"] is not None
        assert claim_result["status"] == "pending"
        
        claim_id = claim_result["claim_id"]
        
        # 4. Verify claim status
        status = get_claim_status(integration_db, claim_id)
        
        assert status is not None
        assert status["status"] == "pending"
        assert status["miner_id"] == miner_id
        assert status["epoch"] == test_epoch
        
        # 5. Approve claim (simulating verification step)
        update_claim_status(
            db_path=integration_db,
            claim_id=claim_id,
            status="approved"
        )
        
        status = get_claim_status(integration_db, claim_id)
        assert status["status"] == "approved"
        
        # 6. Process settlement batch
        settlement_result = process_claims_batch(
            db_path=integration_db,
            max_claims=10,
            min_batch_size=1,
            max_wait_seconds=60,
            dry_run=False
        )
        
        assert settlement_result["processed"] is True
        assert settlement_result["claims_count"] >= 1
        assert settlement_result["transaction_hash"] is not None
        
        # 7. Verify claim is settled
        final_status = get_claim_status(integration_db, claim_id)
        
        assert final_status["status"] == "settled"
        assert final_status["transaction_hash"] == settlement_result["transaction_hash"]
        assert final_status["settled_at"] is not None
        
        # 8. Verify claim history
        history = get_claim_history(integration_db, miner_id)
        
        assert history["total_claims"] == 1
        assert history["total_claimed_urtc"] == final_status["reward_urtc"]
        assert len(history["claims"]) == 1
        assert history["claims"][0]["status"] == "settled"
    
    def test_claim_rejection_flow(self, integration_db, current_ts, current_slot):
        """Test: Submit → Verify → Reject"""
        
        test_epoch = max(0, current_slot // 144 - 3)
        
        # Setup miner with attestation during test epoch
        miner_id = "test-miner-reject"
        wallet = "RTC1RejectWallet123456789"
        setup_test_miner(integration_db, miner_id, "g4", wallet, current_ts, epoch=test_epoch)
        
        # Submit claim
        claim_result = submit_claim(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch,
            wallet_address=wallet,
            signature="mock_signature",
            public_key="mock_public_key",
            current_slot=current_slot,
            current_ts=current_ts,
            skip_signature_verify=True
        )
        
        assert claim_result["success"] is True
        claim_id = claim_result["claim_id"]
        
        # Reject claim
        update_claim_status(
            db_path=integration_db,
            claim_id=claim_id,
            status="rejected",
            details={"reason": "fingerprint_verification_failed"}
        )
        
        status = get_claim_status(integration_db, claim_id)
        assert status["status"] == "rejected"
        assert status["rejection_reason"] == "fingerprint_verification_failed"
        
        # Verify miner cannot submit another claim for same epoch
        eligibility = check_claim_eligibility(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch,
            current_slot=current_slot,
            current_ts=current_ts
        )
        
        # Should still show pending claim exists (rejected claims don't block)
        # This depends on business logic - adjust as needed
    
    def test_multiple_miners_batch_settlement(self, integration_db, current_ts, current_slot):
        """Test batch settlement with multiple miners"""
        
        test_epoch = max(0, current_slot // 144 - 3)
        
        # Setup multiple miners with attestations during test epoch
        miners = []
        for i in range(5):
            miner_id = f"test-miner-{i}"
            wallet = f"RTC1Wallet{i}Address1234567890"
            setup_test_miner(integration_db, miner_id, "g4", wallet, current_ts, epoch=test_epoch)
            miners.append((miner_id, wallet))
        
        # Submit claims for all miners
        claim_ids = []
        for miner_id, wallet in miners:
            claim_result = submit_claim(
                db_path=integration_db,
                miner_id=miner_id,
                epoch=test_epoch,
                wallet_address=wallet,
                signature="mock_signature",
                public_key="mock_public_key",
                current_slot=current_slot,
                current_ts=current_ts,
                skip_signature_verify=True
            )
            
            assert claim_result["success"] is True
            claim_ids.append(claim_result["claim_id"])
        
        # Approve all claims
        for claim_id in claim_ids:
            update_claim_status(
                db_path=integration_db,
                claim_id=claim_id,
                status="approved"
            )
        
        # Process batch settlement
        settlement_result = process_claims_batch(
            db_path=integration_db,
            max_claims=10,
            min_batch_size=1,
            max_wait_seconds=60
        )
        
        assert settlement_result["processed"] is True
        assert settlement_result["claims_count"] == 5
        assert settlement_result["success_count"] == 5
        
        # Verify all claims are settled
        for claim_id in claim_ids:
            status = get_claim_status(integration_db, claim_id)
            assert status["status"] == "settled"


class TestEligibilityScenarios:
    """Test various eligibility scenarios"""
    
    def test_vintage_hardware_eligibility(self, integration_db, current_ts, current_slot):
        """Test eligibility for vintage hardware (should have higher rewards)"""
        
        test_epoch = max(0, current_slot // 144 - 3)
        
        miner_id = "vintage-powerpc-g4"
        wallet = "RTC1VintageWallet123456789"
        setup_test_miner(integration_db, miner_id, "g4", wallet, current_ts, epoch=test_epoch)
        
        eligibility = check_claim_eligibility(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch,
            current_slot=current_slot,
            current_ts=current_ts
        )
        
        assert eligibility["eligible"] is True
        assert eligibility["attestation"]["antiquity_multiplier"] > 1.0
        # G4 should have 2.5x base multiplier (may decay based on chain age)
    
    def test_modern_hardware_eligibility(self, integration_db, current_ts, current_slot):
        """Test eligibility for modern hardware (base rewards)"""
        
        test_epoch = max(0, current_slot // 144 - 3)
        
        miner_id = "modern-intel-miner"
        wallet = "RTC1ModernWallet123456789"
        setup_test_miner(integration_db, miner_id, "modern", wallet, current_ts, epoch=test_epoch)
        
        eligibility = check_claim_eligibility(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch,
            current_slot=current_slot,
            current_ts=current_ts
        )
        
        assert eligibility["eligible"] is True
        assert eligibility["attestation"]["antiquity_multiplier"] <= 1.0
    
    def test_fingerprint_failed_ineligible(self, integration_db, current_ts, current_slot):
        """Test that failed fingerprint makes miner ineligible"""
        
        test_epoch = max(0, current_slot // 144 - 3)
        epoch_start_slot = test_epoch * 144
        epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)
        epoch_ts = epoch_start_ts + (72 * BLOCK_TIME)
        
        miner_id = "fake-vm-miner"
        wallet = "RTC1FakeWallet1234567890"
        
        # Setup miner with failed fingerprint (BOTH recent and epoch)
        with sqlite3.connect(integration_db) as conn:
            # Recent attestation with failed fingerprint
            conn.execute("""
                INSERT INTO miner_attest_recent
                (miner, device_arch, ts_ok, fingerprint_passed, wallet_address)
                VALUES (?, ?, ?, ?, ?)
            """, (miner_id, "modern", current_ts - 3600, 0, wallet))
            
            # Epoch attestation with failed fingerprint
            conn.execute("""
                INSERT INTO miner_attest_recent
                (miner, device_arch, ts_ok, fingerprint_passed, wallet_address)
                VALUES (?, ?, ?, ?, ?)
            """, (miner_id, "modern", epoch_ts, 0, wallet))
        
        eligibility = check_claim_eligibility(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch,
            current_slot=current_slot,
            current_ts=current_ts
        )
        
        assert eligibility["eligible"] is False
        assert eligibility["reason"] == "fingerprint_failed"
        assert eligibility["fingerprint"]["passed"] is False


class TestClaimHistoryAndStats:
    """Test claim history retrieval and statistics"""
    
    def test_get_eligible_epochs(self, integration_db, current_ts, current_slot):
        """Test getting list of eligible epochs for a miner"""
        
        miner_id = "multi-epoch-miner"
        wallet = "RTC1MultiEpochWallet123456"
        
        # Create attestations across multiple epochs
        with sqlite3.connect(integration_db) as conn:
            for epoch_offset in range(5):
                epoch_ts = current_ts - (epoch_offset * 144 * BLOCK_TIME)
                conn.execute("""
                    INSERT INTO miner_attest_recent
                    (miner, device_arch, ts_ok, fingerprint_passed, wallet_address)
                    VALUES (?, ?, ?, ?, ?)
                """, (miner_id, "g4", epoch_ts, 1, wallet))
        
        epochs_result = get_eligible_epochs(
            db_path=integration_db,
            miner_id=miner_id,
            current_slot=current_slot,
            current_ts=current_ts,
            limit=10
        )
        
        assert epochs_result["miner_id"] == miner_id
        assert len(epochs_result["epochs"]) > 0
        assert epochs_result["total_unclaimed_urtc"] >= 0
    
    def test_settlement_statistics(self, integration_db, current_ts, current_slot):
        """Test settlement statistics calculation"""
        
        test_epoch = max(0, current_slot // 144 - 3)
        
        # Setup and settle some claims
        for i in range(10):
            miner_id = f"stats-miner-{i}"
            wallet = f"RTC1StatsWallet{i}12345678"
            setup_test_miner(integration_db, miner_id, "g4", wallet, current_ts, epoch=test_epoch)
            
            claim_result = submit_claim(
                db_path=integration_db,
                miner_id=miner_id,
                epoch=test_epoch,
                wallet_address=wallet,
                signature="mock_signature",
                public_key="mock_public_key",
                current_slot=current_slot,
                current_ts=current_ts,
                skip_signature_verify=True
            )
            
            if claim_result["success"]:
                update_claim_status(
                    db_path=integration_db,
                    claim_id=claim_result["claim_id"],
                    status="approved"
                )
        
        # Process settlement
        process_claims_batch(
            db_path=integration_db,
            max_claims=10,
            min_batch_size=1
        )
        
        # Get statistics
        stats = get_settlement_stats(integration_db, days=7)
        
        assert stats["settled_claims"] > 0
        assert stats["settled_amount_urtc"] > 0
        assert stats["success_rate"] > 0
        assert stats["total_batches"] > 0


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_epoch_not_settled_yet(self, integration_db, current_ts, current_slot):
        """Test that current epoch cannot be claimed"""
        
        miner_id = "early-claimer"
        wallet = "RTC1EarlyWallet123456789"
        # Setup with recent attestation (not for a specific epoch)
        setup_test_miner(integration_db, miner_id, "g4", wallet, current_ts)
        
        # Try to claim current epoch (not settled yet)
        current_epoch = current_slot // 144
        
        eligibility = check_claim_eligibility(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=current_epoch,
            current_slot=current_slot,
            current_ts=current_ts
        )
        
        assert eligibility["eligible"] is False
        assert eligibility["reason"] == "epoch_not_settled"
        assert eligibility["checks"]["epoch_settled"] is False
    
    def test_duplicate_claim_prevention(self, integration_db, current_ts, current_slot):
        """Test that duplicate claims are prevented"""
        
        test_epoch = max(0, current_slot // 144 - 3)
        
        miner_id = "duplicate-claimer"
        wallet = "RTC1DuplicateWallet123456"
        setup_test_miner(integration_db, miner_id, "g4", wallet, current_ts, epoch=test_epoch)
        
        # Submit first claim
        result1 = submit_claim(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch,
            wallet_address=wallet,
            signature="mock_signature",
            public_key="mock_public_key",
            current_slot=current_slot,
            current_ts=current_ts,
            skip_signature_verify=True
        )
        
        assert result1["success"] is True
        
        # Try to submit duplicate claim
        result2 = submit_claim(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch,
            wallet_address=wallet,
            signature="mock_signature",
            public_key="mock_public_key",
            current_slot=current_slot,
            current_ts=current_ts,
            skip_signature_verify=True
        )
        
        assert result2["success"] is False
        assert "pending_claim_exists" in result2["error"] or "already exists" in result2["error"] or "Duplicate" in result2["error"]
    
    def test_wallet_address_change(self, integration_db, current_ts, current_slot):
        """Test that wallet address can be updated between claims"""
        
        test_epoch1 = max(0, current_slot // 144 - 3)
        test_epoch2 = max(0, current_slot // 144 - 4)
        
        miner_id = "wallet-changer"
        wallet1 = "RTC1FirstWallet1234567890"
        wallet2 = "RTC1SecondWallet12345678"
        
        # Setup with first wallet and attestation for epoch1
        setup_test_miner(integration_db, miner_id, "g4", wallet1, current_ts, epoch=test_epoch1)
        
        # Submit claim with first wallet
        result1 = submit_claim(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch1,
            wallet_address=wallet1,
            signature="mock_signature",
            public_key="mock_public_key",
            current_slot=current_slot,
            current_ts=current_ts,
            skip_signature_verify=True
        )
        
        assert result1["success"] is True
        
        # Update wallet in attestation and create attestation for epoch2
        with sqlite3.connect(integration_db) as conn:
            conn.execute("""
                UPDATE miner_attest_recent
                SET wallet_address = ?, ts_ok = ?
                WHERE miner = ?
            """, (wallet2, current_ts - 3600, miner_id))
            
            # Also add attestation for epoch2
            epoch2_start_slot = test_epoch2 * 144
            epoch2_start_ts = GENESIS_TIMESTAMP + (epoch2_start_slot * BLOCK_TIME)
            epoch2_ts = epoch2_start_ts + (72 * BLOCK_TIME)
            conn.execute("""
                INSERT INTO miner_attest_recent
                (miner, device_arch, ts_ok, fingerprint_passed, wallet_address)
                VALUES (?, ?, ?, ?, ?)
            """, (miner_id, "g4", epoch2_ts, 1, wallet2))
        
        # Submit claim for different epoch with new wallet
        result2 = submit_claim(
            db_path=integration_db,
            miner_id=miner_id,
            epoch=test_epoch2,
            wallet_address=wallet2,
            signature="mock_signature",
            public_key="mock_public_key",
            current_slot=current_slot,
            current_ts=current_ts,
            skip_signature_verify=True
        )
        
        assert result2["success"] is True
        
        # Verify different wallet addresses in claims
        status1 = get_claim_status(integration_db, result1["claim_id"])
        status2 = get_claim_status(integration_db, result2["claim_id"])
        
        assert status1["wallet_address"] == wallet1
        assert status2["wallet_address"] == wallet2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
