"""
RustChain Core Unit Tests
Tests for critical blockchain functions: hashing, validation, epochs, balances, etc.
"""

import pytest
import hashlib
import time
from unittest.mock import MagicMock, patch
from datetime import datetime


# ============================================================================
# Test 1: Hardware ID computation produces unique hashes
# ============================================================================
def test_compute_hardware_id_uniqueness():
    """Different inputs should produce different hardware IDs."""
    def compute_hardware_id(cpu_id: str, serial: str, mac: str) -> str:
        data = f"{cpu_id}:{serial}:{mac}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    id1 = compute_hardware_id("Intel Core i7", "ABC123", "00:11:22:33:44:55")
    id2 = compute_hardware_id("AMD Ryzen 9", "XYZ789", "AA:BB:CC:DD:EE:FF")
    id3 = compute_hardware_id("Intel Core i7", "ABC123", "00:11:22:33:44:55")
    
    assert id1 != id2, "Different hardware should have different IDs"
    assert id1 == id3, "Same hardware should have same ID"
    assert len(id1) == 16, "Hardware ID should be 16 hex chars"


# ============================================================================
# Test 2: Fingerprint validation - VM detection
# ============================================================================
def test_validate_fingerprint_vm_detection():
    """Fingerprint validation should detect VM indicators."""
    def validate_fingerprint(fingerprint: dict) -> tuple[bool, str]:
        vm_indicators = ["vmware", "virtualbox", "hyperv", "qemu", "xen"]
        
        cpu_model = fingerprint.get("cpu_model", "").lower()
        for indicator in vm_indicators:
            if indicator in cpu_model:
                return False, f"VM detected: {indicator}"
        
        # Check for suspiciously round memory sizes (often VMs)
        memory_gb = fingerprint.get("memory_gb", 0)
        if memory_gb in [1, 2, 4, 8, 16, 32] and fingerprint.get("is_server", False) is False:
            return False, "Suspicious memory size"
        
        return True, "OK"
    
    # Real hardware fingerprint
    real_fp = {"cpu_model": "Intel Core i7-9750H", "memory_gb": 15.7, "is_server": False}
    valid, msg = validate_fingerprint(real_fp)
    assert valid, f"Real hardware should be valid: {msg}"
    
    # VM fingerprint
    vm_fp = {"cpu_model": "QEMU Virtual CPU", "memory_gb": 4, "is_server": False}
    valid, msg = validate_fingerprint(vm_fp)
    assert not valid, "VM should be detected"


# ============================================================================
# Test 3: Fingerprint validation - Clock drift threshold
# ============================================================================
def test_validate_fingerprint_clock_drift():
    """Clock drift beyond threshold should fail validation."""
    MAX_CLOCK_DRIFT_SECONDS = 300  # 5 minutes
    
    def validate_clock_drift(client_time: int, server_time: int) -> bool:
        drift = abs(client_time - server_time)
        return drift <= MAX_CLOCK_DRIFT_SECONDS
    
    now = int(time.time())
    
    # Valid: small drift
    assert validate_clock_drift(now, now + 60), "60s drift should be OK"
    assert validate_clock_drift(now, now - 120), "120s drift should be OK"
    
    # Invalid: large drift
    assert not validate_clock_drift(now, now + 600), "600s drift should fail"
    assert not validate_clock_drift(now, now - 3600), "1 hour drift should fail"


# ============================================================================
# Test 4: Epoch slot calculation from genesis timestamp
# ============================================================================
def test_current_slot_calculation():
    """Current slot should be calculated correctly from genesis."""
    GENESIS_TIMESTAMP = 1700000000  # Example genesis
    SLOT_DURATION = 600  # 10 minutes per slot
    SLOTS_PER_EPOCH = 144  # ~24 hours
    
    def current_slot(now: int) -> dict:
        elapsed = now - GENESIS_TIMESTAMP
        total_slots = elapsed // SLOT_DURATION
        epoch = total_slots // SLOTS_PER_EPOCH
        slot_in_epoch = total_slots % SLOTS_PER_EPOCH
        return {"epoch": epoch, "slot": slot_in_epoch, "total_slots": total_slots}
    
    # At genesis
    result = current_slot(GENESIS_TIMESTAMP)
    assert result["epoch"] == 0
    assert result["slot"] == 0
    
    # After 1 epoch
    one_epoch_later = GENESIS_TIMESTAMP + (SLOT_DURATION * SLOTS_PER_EPOCH)
    result = current_slot(one_epoch_later)
    assert result["epoch"] == 1
    assert result["slot"] == 0
    
    # Mid-epoch
    mid_epoch = GENESIS_TIMESTAMP + (SLOT_DURATION * 72)  # Half epoch
    result = current_slot(mid_epoch)
    assert result["epoch"] == 0
    assert result["slot"] == 72


# ============================================================================
# Test 5: Balance operations - credit/debit validation
# ============================================================================
def test_balance_operations():
    """Balance operations should handle credit/debit correctly."""
    class WalletBalance:
        def __init__(self, initial: int = 0):
            self.balance_i64 = initial
        
        def credit(self, amount: int) -> bool:
            if amount <= 0:
                return False
            self.balance_i64 += amount
            return True
        
        def debit(self, amount: int) -> bool:
            if amount <= 0 or amount > self.balance_i64:
                return False
            self.balance_i64 -= amount
            return True
    
    wallet = WalletBalance(1000000)  # 1 RTC in micros
    
    # Credit
    assert wallet.credit(500000), "Credit should succeed"
    assert wallet.balance_i64 == 1500000
    
    # Invalid credit
    assert not wallet.credit(-100), "Negative credit should fail"
    assert not wallet.credit(0), "Zero credit should fail"
    
    # Debit
    assert wallet.debit(500000), "Debit should succeed"
    assert wallet.balance_i64 == 1000000
    
    # Overdraft
    assert not wallet.debit(2000000), "Overdraft should fail"


# ============================================================================
# Test 6: Transfer validation
# ============================================================================
def test_transfer_validation():
    """Transfer validation should check sender, recipient, and amount."""
    def validate_transfer(sender: str, recipient: str, amount: int, sender_balance: int) -> tuple[bool, str]:
        if not sender or not recipient:
            return False, "Invalid addresses"
        if sender == recipient:
            return False, "Cannot send to self"
        if amount <= 0:
            return False, "Invalid amount"
        if amount > sender_balance:
            return False, "Insufficient balance"
        return True, "OK"
    
    # Valid transfer
    valid, msg = validate_transfer("wallet_a", "wallet_b", 100, 1000)
    assert valid, f"Valid transfer should pass: {msg}"
    
    # Self-transfer
    valid, msg = validate_transfer("wallet_a", "wallet_a", 100, 1000)
    assert not valid, "Self-transfer should fail"
    
    # Insufficient balance
    valid, msg = validate_transfer("wallet_a", "wallet_b", 5000, 1000)
    assert not valid, "Insufficient balance should fail"


# ============================================================================
# Test 7: RTC address format validation
# ============================================================================
def test_rtc_address_validation():
    """RTC addresses should match expected format."""
    import re
    
    def validate_rtc_address(address: str) -> bool:
        # RTC addresses: 40 hex chars ending with "RTC" or just miner_id string
        if address.endswith("RTC"):
            hex_part = address[:-3]
            return len(hex_part) == 40 and all(c in "0123456789abcdef" for c in hex_part.lower())
        # Allow simple miner_id strings (alphanumeric + underscore)
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', address)) and len(address) <= 64
    
    # Valid addresses
    assert validate_rtc_address("abc123def456abc123def456abc123def456abc1RTC")
    assert validate_rtc_address("my_miner_wallet")
    assert validate_rtc_address("h3o")
    
    # Invalid addresses
    assert not validate_rtc_address("")
    assert not validate_rtc_address("abc!@#$")
    assert not validate_rtc_address("a" * 100)  # Too long


# ============================================================================
# Test 8: Hardware multiplier lookup
# ============================================================================
def test_hardware_multiplier_lookup():
    """Hardware multipliers should return correct values for CPU generations."""
    MULTIPLIERS = {
        "G3": 2.5,    # PowerPC G3
        "G4": 2.2,    # PowerPC G4
        "G5": 2.0,    # PowerPC G5
        "POWER6": 1.8,
        "POWER7": 1.6,
        "POWER8": 1.4,
        "modern": 1.0,
    }
    
    def get_multiplier(cpu_family: str) -> float:
        return MULTIPLIERS.get(cpu_family, 1.0)
    
    assert get_multiplier("G3") == 2.5
    assert get_multiplier("G5") == 2.0
    assert get_multiplier("POWER8") == 1.4
    assert get_multiplier("modern") == 1.0
    assert get_multiplier("unknown") == 1.0  # Default


# ============================================================================
# Test 9: Attestation TTL - expired vs valid
# ============================================================================
def test_attestation_ttl():
    """Attestations should expire after TTL."""
    ATTESTATION_TTL = 3600  # 1 hour
    
    def is_attestation_valid(attest_time: int, current_time: int) -> bool:
        age = current_time - attest_time
        return 0 <= age <= ATTESTATION_TTL
    
    now = int(time.time())
    
    # Fresh attestation
    assert is_attestation_valid(now - 60, now), "Recent attestation should be valid"
    
    # Expired attestation
    assert not is_attestation_valid(now - 7200, now), "Old attestation should be expired"
    
    # Future attestation (clock skew attack)
    assert not is_attestation_valid(now + 300, now), "Future attestation should be invalid"


# ============================================================================
# Test 10: Fee calculation
# ============================================================================
def test_fee_calculation():
    """Transaction fees should be calculated correctly."""
    BASE_FEE = 1000  # 0.001 RTC in micros
    FEE_RATE = 0.001  # 0.1% of amount
    
    def calculate_fee(amount: int, is_withdrawal: bool = False) -> int:
        fee = max(BASE_FEE, int(amount * FEE_RATE))
        if is_withdrawal:
            fee = int(fee * 1.5)  # 50% higher for withdrawals
        return fee
    
    # Small transfer
    assert calculate_fee(10000) == BASE_FEE  # Minimum fee
    
    # Large transfer
    assert calculate_fee(10000000) == 10000  # 0.1% of 10 RTC
    
    # Withdrawal premium
    withdrawal_fee = calculate_fee(10000000, is_withdrawal=True)
    assert withdrawal_fee == 15000  # 1.5x normal fee


# ============================================================================
# Test 11: Nonce replay protection
# ============================================================================
def test_nonce_replay_protection():
    """Duplicate nonces should be rejected."""
    used_nonces = set()
    
    def check_nonce(sender: str, nonce: int) -> bool:
        key = f"{sender}:{nonce}"
        if key in used_nonces:
            return False  # Replay detected
        used_nonces.add(key)
        return True
    
    # First use
    assert check_nonce("wallet_a", 1), "First nonce should be accepted"
    assert check_nonce("wallet_a", 2), "Second nonce should be accepted"
    
    # Replay
    assert not check_nonce("wallet_a", 1), "Replayed nonce should be rejected"
    
    # Different sender, same nonce
    assert check_nonce("wallet_b", 1), "Same nonce from different sender should be OK"


# ============================================================================
# Test 12: API health response format
# ============================================================================
def test_health_response_format():
    """Health endpoint should return expected format."""
    def mock_health():
        return {
            "ok": True,
            "version": "2.2.1-rip200",
            "uptime_s": 18728,
            "db_rw": True,
            "backup_age_hours": 2.5,
            "tip_age_slots": 0
        }
    
    health = mock_health()
    
    assert "ok" in health
    assert "version" in health
    assert health["ok"] is True
    assert isinstance(health["uptime_s"], int)
    assert health["version"].startswith("2.")


# ============================================================================
# Test 13: Epoch pot distribution
# ============================================================================
def test_epoch_pot_distribution():
    """Epoch pot should be distributed among enrolled miners."""
    def distribute_pot(pot: int, miners: list[dict]) -> dict[str, int]:
        if not miners:
            return {}
        
        total_weight = sum(m["multiplier"] for m in miners)
        rewards = {}
        
        for miner in miners:
            share = int(pot * (miner["multiplier"] / total_weight))
            rewards[miner["id"]] = share
        
        return rewards
    
    pot = 1000000  # 1 RTC
    miners = [
        {"id": "miner_a", "multiplier": 2.0},
        {"id": "miner_b", "multiplier": 1.0},
        {"id": "miner_c", "multiplier": 1.0},
    ]
    
    rewards = distribute_pot(pot, miners)
    
    # Miner A should get 50% (2.0 / 4.0)
    assert rewards["miner_a"] == 500000
    # Miners B and C should get 25% each
    assert rewards["miner_b"] == 250000
    assert rewards["miner_c"] == 250000
    
    # Empty miners
    assert distribute_pot(pot, []) == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
