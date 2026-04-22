#!/usr/bin/env python3
"""
Item B Regression Test: Registry Expiry / not_before / not_after
=================================================================
Tests for RustChain #2273 Item B — Peer registry time window validation.

Acceptance Criteria:
1. PeerRegistry entries gain not_before / not_after fields (ISO-8601)
2. get_pubkey() returns None if current time is outside the window
3. Clock skew tolerance of ±5 minutes (300s) is applied
4. Expired entries are logged and rejected
5. Not-yet-valid entries are logged and rejected
"""
import os
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add node directory to path
sys.path.insert(0, str(Path(__file__).parent / "node"))

from p2p_identity import PeerRegistry, PeerEntry


def test_registry_entry_with_time_window():
    """Test 1: PeerEntry accepts not_before/not_after fields."""
    print("\n=== Test 1: PeerEntry time window fields ===")
    
    entry = PeerEntry(
        node_id="peer_alpha",
        pubkey_hex="abcd1234" * 8,
        key_version=1,
        not_before="2026-04-01T00:00:00Z",
        not_after="2027-04-01T00:00:00Z"
    )
    
    assert entry.not_before == "2026-04-01T00:00:00Z"
    assert entry.not_after == "2027-04-01T00:00:00Z"
    print(f"  ✅ PeerEntry created with time window")
    print(f"     not_before: {entry.not_before}")
    print(f"     not_after:  {entry.not_after}")


def test_valid_time_window():
    """Test 2: Entry within time window is accepted."""
    print("\n=== Test 2: Valid time window ===")
    
    now = datetime.now(timezone.utc)
    not_before = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    not_after = (now + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "peer_registry.json"
        
        registry_data = {
            "version": 1,
            "peers": [{
                "node_id": "peer_valid",
                "pubkey_hex": "abcd1234" * 8,
                "key_version": 1,
                "not_before": not_before,
                "not_after": not_after
            }]
        }
        with open(registry_path, "w") as f:
            json.dump(registry_data, f)
        
        registry = PeerRegistry(str(registry_path))
        registry.load()
        
        pubkey = registry.get_pubkey("peer_valid")
        assert pubkey is not None, "Valid entry should return pubkey"
        assert pubkey == "abcd1234" * 8
        print(f"  ✅ Entry within time window accepted")


def test_expired_entry():
    """Test 3: Entry past not_after is rejected."""
    print("\n=== Test 3: Expired entry (not_after) ===")
    
    now = datetime.now(timezone.utc)
    not_before = (now - timedelta(days=60)).isoformat().replace("+00:00", "Z")
    not_after = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")  # Expired 1 hour ago
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "peer_registry.json"
        
        registry_data = {
            "version": 1,
            "peers": [{
                "node_id": "peer_expired",
                "pubkey_hex": "deadbeef" * 8,
                "key_version": 1,
                "not_before": not_before,
                "not_after": not_after
            }]
        }
        with open(registry_path, "w") as f:
            json.dump(registry_data, f)
        
        registry = PeerRegistry(str(registry_path))
        registry.load()
        
        pubkey = registry.get_pubkey("peer_expired")
        assert pubkey is None, "Expired entry should return None"
        print(f"  ✅ Expired entry rejected")


def test_not_yet_valid_entry():
    """Test 4: Entry before not_before is rejected."""
    print("\n=== Test 4: Not-yet-valid entry (not_before) ===")
    
    now = datetime.now(timezone.utc)
    not_before = (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")  # Starts in 1 hour
    not_after = (now + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "peer_registry.json"
        
        registry_data = {
            "version": 1,
            "peers": [{
                "node_id": "peer_future",
                "pubkey_hex": "cafe1234" * 8,
                "key_version": 1,
                "not_before": not_before,
                "not_after": not_after
            }]
        }
        with open(registry_path, "w") as f:
            json.dump(registry_data, f)
        
        registry = PeerRegistry(str(registry_path))
        registry.load()
        
        pubkey = registry.get_pubkey("peer_future")
        assert pubkey is None, "Not-yet-valid entry should return None"
        print(f"  ✅ Not-yet-valid entry rejected")


def test_clock_skew_tolerance():
    """Test 5: Clock skew tolerance of ±5 minutes."""
    print("\n=== Test 5: Clock skew tolerance (±300s) ===")
    
    now = datetime.now(timezone.utc)
    
    # Entry starts 4 minutes in the future (within 5 min skew tolerance)
    not_before = (now + timedelta(minutes=4)).isoformat().replace("+00:00", "Z")
    not_after = (now + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "peer_registry.json"
        
        registry_data = {
            "version": 1,
            "peers": [{
                "node_id": "peer_skew_ok",
                "pubkey_hex": "skew1234" * 8,
                "key_version": 1,
                "not_before": not_before,
                "not_after": not_after
            }]
        }
        with open(registry_path, "w") as f:
            json.dump(registry_data, f)
        
        registry = PeerRegistry(str(registry_path))
        registry.load()
        
        # Should be accepted due to clock skew tolerance
        pubkey = registry.get_pubkey("peer_skew_ok")
        assert pubkey is not None, "Entry within skew tolerance should be accepted"
        print(f"  ✅ 4-minute future start accepted (within ±5 min skew)")
    
    # Entry starts 6 minutes in the future (outside skew tolerance)
    not_before = (now + timedelta(minutes=6)).isoformat().replace("+00:00", "Z")
    not_after = (now + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "peer_registry.json"
        
        registry_data = {
            "version": 1,
            "peers": [{
                "node_id": "peer_skew_reject",
                "pubkey_hex": "skew5678" * 8,
                "key_version": 1,
                "not_before": not_before,
                "not_after": not_after
            }]
        }
        with open(registry_path, "w") as f:
            json.dump(registry_data, f)
        
        registry = PeerRegistry(str(registry_path))
        registry.load()
        
        # Should be rejected (outside skew tolerance)
        pubkey = registry.get_pubkey("peer_skew_reject")
        assert pubkey is None, "Entry outside skew tolerance should be rejected"
        print(f"  ✅ 6-minute future start rejected (outside ±5 min skew)")


def test_get_entry_with_version_and_expiry():
    """Test 6: get_entry_with_version checks both version AND expiry."""
    print("\n=== Test 6: Version + expiry combined check ===")
    
    now = datetime.now(timezone.utc)
    
    # Expired entry with matching version — should be rejected
    not_after = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "peer_registry.json"
        
        registry_data = {
            "version": 1,
            "peers": [{
                "node_id": "peer_combo",
                "pubkey_hex": "combo1234" * 8,
                "key_version": 2,
                "not_before": None,
                "not_after": not_after
            }]
        }
        with open(registry_path, "w") as f:
            json.dump(registry_data, f)
        
        registry = PeerRegistry(str(registry_path))
        registry.load()
        
        # Matching version but expired — should fail
        entry = registry.get_entry_with_version("peer_combo", sig_version=2)
        assert entry is None, "Expired entry should be rejected even with matching version"
        print(f"  ✅ Expired entry rejected (version match doesn't override expiry)")
        
        # Non-matching version and expired — should fail
        entry = registry.get_entry_with_version("peer_combo", sig_version=1)
        assert entry is None, "Expired entry with wrong version should be rejected"
        print(f"  ✅ Expired + version mismatch rejected")


def test_null_time_fields():
    """Test 7: null not_before/not_after means no restriction."""
    print("\n=== Test 7: Null time fields (no restriction) ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "peer_registry.json"
        
        registry_data = {
            "version": 1,
            "peers": [{
                "node_id": "peer_no_expiry",
                "pubkey_hex": "noexpiry12" * 8,
                "key_version": 1,
                "not_before": None,
                "not_after": None
            }]
        }
        with open(registry_path, "w") as f:
            json.dump(registry_data, f)
        
        registry = PeerRegistry(str(registry_path))
        registry.load()
        
        pubkey = registry.get_pubkey("peer_no_expiry")
        assert pubkey is not None, "Entry with null time fields should be accepted"
        print(f"  ✅ Null not_before/not_after means no time restriction")


def main():
    print("=" * 70)
    print("RustChain #2273 Item B: Registry Expiry Regression Tests")
    print("=" * 70)
    
    tests = [
        test_registry_entry_with_time_window,
        test_valid_time_window,
        test_expired_entry,
        test_not_yet_valid_entry,
        test_clock_skew_tolerance,
        test_get_entry_with_version_and_expiry,
        test_null_time_fields,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ ERROR: {type(e).__name__}: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
