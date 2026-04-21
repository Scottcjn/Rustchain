#!/usr/bin/env python3
"""
Regression test for Issue #2273 Item C — Non-root key path fallback

Test: Run with HOME pointing at a tmpdir and /etc/rustchain being unwritable.
Assert the user path is chosen and the keypair loads.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add node directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "node"))

def test_non_root_key_path():
    """Test that LocalKeypair falls back to user path when /etc/rustchain is unwritable."""
    
    # Create a temporary directory to act as HOME
    tmpdir = tempfile.mkdtemp(prefix="rustchain_test_")
    print(f"Using temp directory: {tmpdir}")
    
    try:
        # Set up environment
        original_home = os.environ.get("HOME")
        original_privkey = os.environ.get("RC_P2P_PRIVKEY_PATH")
        original_signing_mode = os.environ.get("RC_P2P_SIGNING_MODE")
        
        # Point HOME at tmpdir
        os.environ["HOME"] = tmpdir
        
        # Make sure RC_P2P_PRIVKEY_PATH is not set (to test fallback)
        if "RC_P2P_PRIVKEY_PATH" in os.environ:
            del os.environ["RC_P2P_PRIVKEY_PATH"]
        
        # Set signing mode to dual (required for Ed25519)
        os.environ["RC_P2P_SIGNING_MODE"] = "dual"
        
        # Import after setting environment
        from p2p_identity import LocalKeypair
        
        # Create keypair (should fall back to $HOME/.rustchain/p2p_identity.pem)
        keypair = LocalKeypair()
        
        # Assert the path is in the user's home directory
        expected_path = Path(tmpdir) / ".rustchain" / "p2p_identity.pem"
        assert keypair.path == expected_path, f"Expected {expected_path}, got {keypair.path}"
        print(f"✓ Keypair path is correct: {keypair.path}")
        
        # Trigger keypair generation by accessing pubkey_hex (lazy loading)
        pubkey = keypair.pubkey_hex
        
        # Assert the keypair file was created
        assert keypair.path.exists(), f"Keypair file was not created at {keypair.path}"
        print(f"✓ Keypair file exists: {keypair.path}")
        
        # Assert we can load the keypair
        assert pubkey is not None and len(pubkey) == 64, f"Invalid pubkey: {pubkey}"
        print(f"✓ Keypair pubkey_hex: {pubkey}")
        
        # Assert we can sign data
        test_data = b"test message"
        signature = keypair.sign(test_data)
        assert signature is not None and len(signature) > 0, "Signature failed"
        print(f"✓ Keypair can sign data: {signature[:32]}...")
        
        # Test loading existing keypair
        keypair2 = LocalKeypair()
        assert keypair2.pubkey_hex == pubkey, "Reloaded keypair has different pubkey"
        print(f"✓ Keypair can be reloaded with same pubkey")
        
        # Test with RC_P2P_PRIVKEY_PATH env var
        custom_path = Path(tmpdir) / "custom" / "my_key.pem"
        os.environ["RC_P2P_PRIVKEY_PATH"] = str(custom_path)
        
        # Clear the module cache to force reimport
        if "p2p_identity" in sys.modules:
            del sys.modules["p2p_identity"]
        
        from p2p_identity import LocalKeypair as LocalKeypair2
        keypair3 = LocalKeypair2()
        
        assert keypair3.path == custom_path, f"Expected {custom_path}, got {keypair3.path}"
        print(f"✓ RC_P2P_PRIVKEY_PATH env var is respected: {keypair3.path}")
        
        print("\n✅ All Item C tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Restore environment
        if original_home:
            os.environ["HOME"] = original_home
        if original_privkey:
            os.environ["RC_P2P_PRIVKEY_PATH"] = original_privkey
        if original_signing_mode:
            os.environ["RC_P2P_SIGNING_MODE"] = original_signing_mode
        
        # Cleanup
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"Cleaned up temp directory")

if __name__ == "__main__":
    success = test_non_root_key_path()
    sys.exit(0 if success else 1)
