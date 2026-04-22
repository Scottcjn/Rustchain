#!/usr/bin/env python3
"""
Item A Regression Test: Key Rotation Mechanism
==============================================
Tests for RustChain #2273 Item A — Ed25519 key rotation with key_version.

Acceptance Criteria:
1. LocalKeypair gains a key_version field, written alongside the PEM on generation
2. PeerRegistry entries gain a key_version field; verify path checks version match
3. RC_P2P_KEYGEN env var forces fresh keypair with incremented version
4. Old version rejected after rotation completes, new version accepted
"""
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

# Add node directory to path
sys.path.insert(0, str(Path(__file__).parent / "node"))

from p2p_identity import LocalKeypair, PeerRegistry, PeerEntry, pack_signature, unpack_signature


def test_keypair_version_persisted():
    """Test 1: key_version is persisted alongside PEM file."""
    print("\n=== Test 1: Key version persistence ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = Path(tmpdir) / "p2p_identity.pem"
        
        # Generate new keypair
        keypair = LocalKeypair(key_path)
        _ = keypair.pubkey_hex  # Trigger generation
        
        version_path = key_path.with_suffix(".version")
        assert version_path.exists(), "Version file should be created"
        
        version = int(version_path.read_text().strip())
        assert version == 1, f"Initial version should be 1, got {version}"
        assert keypair.key_version == 1, f"LocalKeypair.key_version should be 1"
        
        print(f"  ✅ Generated keypair v{version}")
        print(f"  ✅ PEM: {key_path}")
        print(f"  ✅ Version file: {version_path}")


def test_key_rotation_with_env_var():
    """Test 2: RC_P2P_KEYGEN=1 forces rotation with version increment."""
    print("\n=== Test 2: Key rotation via RC_P2P_KEYGEN ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = Path(tmpdir) / "p2p_identity.pem"
        
        # Generate initial keypair
        keypair1 = LocalKeypair(key_path)
        pubkey1 = keypair1.pubkey_hex
        version1 = keypair1.key_version
        print(f"  Initial: v{version1}, pubkey={pubkey1[:16]}...")
        
        # Force rotation
        os.environ["RC_P2P_KEYGEN"] = "1"
        keypair2 = LocalKeypair(key_path)
        pubkey2 = keypair2.pubkey_hex
        version2 = keypair2.key_version
        del os.environ["RC_P2P_KEYGEN"]
        
        print(f"  After rotation: v{version2}, pubkey={pubkey2[:16]}...")
        
        # Verify version incremented
        assert version2 == version1 + 1, f"Version should increment from {version1} to {version2}"
        
        # Verify old key archived
        old_key_path = key_path.parent / f"{key_path.stem}.v{version1}.pem"
        assert old_key_path.exists(), f"Old key should be archived at {old_key_path}"
        print(f"  ✅ Old key archived: {old_key_path}")
        
        # Verify new key is different
        assert pubkey1 != pubkey2, "New keypair should have different pubkey"
        print(f"  ✅ New keypair generated")


def test_peer_registry_version_check():
    """Test 3: PeerRegistry rejects signatures with mismatched key_version."""
    print("\n=== Test 3: PeerRegistry version verification ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "peer_registry.json"
        
        # Create registry with peer at version 2
        registry_data = {
            "version": 1,
            "peers": [
                {
                    "node_id": "peer_alpha",
                    "pubkey_hex": "abcd1234" * 8,  # 64 hex chars
                    "key_version": 2,
                    "not_before": None,
                    "not_after": None
                }
            ]
        }
        with open(registry_path, "w") as f:
            json.dump(registry_data, f)
        
        registry = PeerRegistry(str(registry_path))
        registry.load()
        
        # Test: signature with matching version (v2) — should succeed
        entry_v2 = registry.get_entry_with_version("peer_alpha", sig_version=2)
        assert entry_v2 is not None, "Entry with matching version should be returned"
        assert entry_v2.key_version == 2, "Entry version should be 2"
        print(f"  ✅ Matching version (v2) accepted")
        
        # Test: signature with old version (v1) — should be rejected
        entry_v1 = registry.get_entry_with_version("peer_alpha", sig_version=1)
        assert entry_v1 is None, "Entry with old version should be rejected"
        print(f"  ✅ Old version (v1) rejected")
        
        # Test: signature with future version (v3) — should be rejected
        entry_v3 = registry.get_entry_with_version("peer_alpha", sig_version=3)
        assert entry_v3 is None, "Entry with future version should be rejected"
        print(f"  ✅ Future version (v3) rejected")


def test_signature_pack_unpack_with_version():
    """Test 4: pack_signature/unpack_signature includes key_version."""
    print("\n=== Test 4: Signature version encoding ===")
    
    # Test: Ed25519 signature with version
    ed_sig = "deadbeef" * 16  # 64 bytes = 128 hex chars
    packed = pack_signature(None, ed_sig, key_version=3)
    
    assert packed.startswith("{"), "Ed25519 signature should be JSON-encoded"
    
    unpacked = json.loads(packed)
    assert unpacked["e"] == ed_sig, "Ed25519 signature should be preserved"
    assert unpacked["v"] == 3, "Key version should be 3"
    print(f"  ✅ Packed: {packed[:60]}...")
    
    # Test: unpack_signature
    hmac, ed, version = unpack_signature(packed)
    assert hmac is None, "HMAC should be None"
    assert ed == ed_sig, "Ed25519 signature should match"
    assert version == 3, "Version should be 3"
    print(f"  ✅ Unpacked: version={version}")


def test_full_rotation_workflow():
    """Test 5: Full rotation workflow — old key rejected, new key accepted."""
    print("\n=== Test 5: Full rotation workflow ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = Path(tmpdir) / "p2p_identity.pem"
        registry_path = Path(tmpdir) / "peer_registry.json"
        
        # Step 1: Generate initial keypair (v1)
        keypair_v1 = LocalKeypair(key_path)
        pubkey_v1 = keypair_v1.pubkey_hex
        assert keypair_v1.key_version == 1
        
        # Step 2: Create registry with v1
        registry_data = {
            "version": 1,
            "peers": [{"node_id": "self", "pubkey_hex": pubkey_v1, "key_version": 1}]
        }
        with open(registry_path, "w") as f:
            json.dump(registry_data, f)
        
        registry = PeerRegistry(str(registry_path))
        registry.load()
        
        # Step 3: Sign with v1 — should be accepted
        data = b"test message"
        sig_v1 = keypair_v1.sign(data)
        packed_v1 = pack_signature(None, sig_v1, key_version=1)
        _, sig_hex, ver = unpack_signature(packed_v1)
        entry = registry.get_entry_with_version("self", sig_version=ver)
        assert entry is not None, "v1 signature should be accepted"
        print(f"  ✅ v1 signature accepted")
        
        # Step 4: Rotate key
        os.environ["RC_P2P_KEYGEN"] = "1"
        keypair_v2 = LocalKeypair(key_path)
        pubkey_v2 = keypair_v2.pubkey_hex
        assert keypair_v2.key_version == 2
        del os.environ["RC_P2P_KEYGEN"]
        
        # Step 5: Update registry to v2
        registry_data["peers"][0]["key_version"] = 2
        registry_data["peers"][0]["pubkey_hex"] = pubkey_v2
        with open(registry_path, "w") as f:
            json.dump(registry_data, f)
        registry.load()  # Reload
        
        # Step 6: Sign with v2 — should be accepted
        sig_v2 = keypair_v2.sign(data)
        packed_v2 = pack_signature(None, sig_v2, key_version=2)
        _, sig_hex, ver = unpack_signature(packed_v2)
        entry = registry.get_entry_with_version("self", sig_version=ver)
        assert entry is not None, "v2 signature should be accepted"
        print(f"  ✅ v2 signature accepted")
        
        # Step 7: Try to use old v1 signature — should be rejected
        entry_old = registry.get_entry_with_version("self", sig_version=1)
        assert entry_old is None, "Old v1 signature should be rejected after rotation"
        print(f"  ✅ Old v1 signature rejected after rotation")


def main():
    print("=" * 60)
    print("RustChain #2273 Item A: Key Rotation Regression Tests")
    print("=" * 60)
    
    tests = [
        test_keypair_version_persisted,
        test_key_rotation_with_env_var,
        test_peer_registry_version_check,
        test_signature_pack_unpack_with_version,
        test_full_rotation_workflow,
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
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
