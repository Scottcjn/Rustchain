#!/usr/bin/env python3
"""
Minimal test script for XP/Badge automation functionality.
Directly executable without pytest dependency.
"""

import json
import tempfile
from pathlib import Path
import sys

def test_basic_json_generation():
    """Test basic JSON file generation."""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test proof_of_antiquity.json structure
            proof_data = {
                "cpu_model": "PowerPC G4",
                "bios_date": "2003-05-15", 
                "entropy_score": 3.2,
                "hardware_fingerprint": "test_fingerprint",
                "antiquity_multiplier": 2.5,
                "timestamp": "2026-02-20T00:45:00Z"
            }
            
            proof_file = Path(temp_dir) / "proof_of_antiquity.json"
            with open(proof_file, 'w') as f:
                json.dump(proof_data, f)
                
            assert proof_file.exists()
            with open(proof_file, 'r') as f:
                loaded = json.load(f)
            assert loaded["entropy_score"] == 3.2
        print("✓ Basic JSON generation test passed")
        return True
    except Exception as e:
        print(f"✗ Basic JSON generation test failed: {e}")
        return False

def test_badge_unlocking_logic():
    """Test basic badge unlocking logic."""
    try:
        def unlock_badges(entropy_score):
            badges = []
            if entropy_score >= 3.0:
                badges.append({"nft_id": "high_entropy_veteran", "rarity": "rare"})
            if entropy_score >= 2.5:
                badges.append({"nft_id": "entropy_enthusiast", "rarity": "common"})
            return badges
        
        # Test high entropy
        badges = unlock_badges(3.5)
        assert len(badges) == 2
        assert badges[0]["nft_id"] == "high_entropy_veteran"
        
        # Test medium entropy  
        badges = unlock_badges(2.7)
        assert len(badges) == 1
        assert badges[0]["nft_id"] == "entropy_enthusiast"
        
        # Test low entropy
        badges = unlock_badges(2.0)
        assert len(badges) == 0
        
        print("✓ Badge unlocking logic test passed")
        return True
    except Exception as e:
        print(f"✗ Badge unlocking logic test failed: {e}")
        return False

def main():
    """Run all tests and exit with appropriate code."""
    print("Running XP/Badge automation tests...")
    
    test1_passed = test_basic_json_generation()
    test2_passed = test_badge_unlocking_logic()
    
    if test1_passed and test2_passed:
        print("All tests passed! ✅")
        sys.exit(0)
    else:
        print("Some tests failed! ❌")
        sys.exit(1)

if __name__ == "__main__":
    main()