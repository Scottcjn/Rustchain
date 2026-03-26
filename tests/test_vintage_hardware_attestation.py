#!/usr/bin/env python3
"""
Test Suite for Vintage Hardware Attestation
============================================

Comprehensive tests for issue #2314 "Ghost in the Machine" implementation.
Validates vintage hardware profiles, fingerprint generation, attestation proofs,
and bounty calculations.

Run:
    python3 tests/test_vintage_hardware_attestation.py -v
"""

import json
import sys
import unittest
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, 'vintage_miner')

from hardware_profiles import (
    get_profile,
    get_multiplier,
    get_era,
    get_bounty,
    list_profiles,
    VINTAGE_PROFILES,
    VintageProfile
)
from vintage_miner_client import (
    VintageMinerClient,
    Fingerprint,
    TimingProof,
    AttestationRequest
)


class TestVintageHardwareProfiles(unittest.TestCase):
    """Test vintage hardware profile definitions"""
    
    def test_pentium_ii_profile_exists(self):
        """Verify Pentium II profile is defined"""
        profile = get_profile("pentium_ii")
        self.assertEqual(profile.name, "Intel Pentium II")
        self.assertEqual(profile.manufacturer, "Intel")
        self.assertEqual(profile.years, (1997, 1999))
    
    def test_pentium_ii_multiplier_correct(self):
        """Verify Pentium II multiplier matches spec"""
        multiplier = get_multiplier("pentium_ii")
        self.assertEqual(multiplier, 2.2)
    
    def test_386_profile_ultra_vintage(self):
        """Verify Intel 386 has maximum bonus"""
        profile = get_profile("intel_386")
        self.assertEqual(profile.base_multiplier, 3.0)
        self.assertEqual(profile.years, (1985, 1994))
    
    def test_386_multiplier_correct(self):
        """Verify 386 multiplier"""
        multiplier = get_multiplier("intel_386")
        self.assertEqual(multiplier, 3.0)
    
    def test_motorola_68000_profile(self):
        """Verify Motorola 68000 profile (Amiga/Mac)"""
        profile = get_profile("motorola_68000")
        self.assertEqual(profile.name, "Motorola 68000")
        self.assertEqual(profile.base_multiplier, 3.0)
        self.assertIn("AmigaOS", profile.os_support)
    
    def test_game_console_profiles_exist(self):
        """Verify game console CPU profiles"""
        console_cpus = [
            "nes_6502",
            "snes_65c816",
            "genesis_68000",
            "gameboy_z80",
            "ps1_mips",
            "dreamcast_sh4"
        ]
        for cpu in console_cpus:
            with self.subTest(cpu=cpu):
                profile = get_profile(cpu)
                self.assertIsNotNone(profile)
                self.assertGreaterEqual(profile.base_multiplier, 2.3)
    
    def test_exotic_architectures_exist(self):
        """Verify exotic/dead architecture profiles"""
        exotic = [
            "dec_vax",
            "transputer",
            "intel_i860",
            "clipper"
        ]
        for arch in exotic:
            with self.subTest(arch=arch):
                profile = get_profile(arch)
                self.assertIsNotNone(profile)
                self.assertGreaterEqual(profile.base_multiplier, 3.0)
    
    def test_all_profiles_have_required_fields(self):
        """Verify all profiles have required fields"""
        for arch_name, profile in VINTAGE_PROFILES.items():
            with self.subTest(arch=arch_name):
                self.assertIsInstance(profile, VintageProfile)
                self.assertIsNotNone(profile.name)
                self.assertIsNotNone(profile.manufacturer)
                self.assertIsNotNone(profile.years)
                self.assertIsInstance(profile.years, tuple)
                self.assertEqual(len(profile.years), 2)
                self.assertLess(profile.years[0], profile.years[1])
                self.assertGreater(profile.base_multiplier, 0)
                self.assertIsNotNone(profile.timing_variance)
                self.assertIsNotNone(profile.stability_window)
                self.assertIsInstance(profile.fingerprint_patterns, list)
                self.assertGreater(len(profile.fingerprint_patterns), 0)
    
    def test_all_profiles_pre_2000(self):
        """Verify all profiles are for pre-2000 hardware"""
        for arch_name, profile in VINTAGE_PROFILES.items():
            with self.subTest(arch=arch_name):
                # Latest year must be < 2000
                self.assertLess(profile.years[1], 2000,
                    f"{arch_name} has year {profile.years[1]} >= 2000")
    
    def test_profile_count(self):
        """Verify minimum number of profiles"""
        # Should have 50+ profiles
        self.assertGreaterEqual(len(VINTAGE_PROFILES), 30,
            "Should have at least 30 vintage profiles")


class TestEraAndBountyCalculation(unittest.TestCase):
    """Test era classification and bounty calculation"""
    
    def test_era_pre_1985(self):
        """Verify pre-1985 era classification"""
        # DEC VAX (1977-1994) - start year 1977 is pre-1985
        era = get_era("dec_vax")
        self.assertEqual(era, "Pre-1985")
    
    def test_era_1985_1989(self):
        """Verify 1985-1989 era classification"""
        # Intel 386 (1985-1994) - start year 1985 is in 1985-1989
        era = get_era("intel_386")
        self.assertEqual(era, "1985-1989")
    
    def test_era_1990_1994(self):
        """Verify 1990-1994 era classification"""
        # MIPS R3000 (1988-1995) - start year 1988 is in 1985-1989
        # Use Motorola 68000 (1979-1990) - start year 1979 is pre-1985
        # Use PowerPC 601 (1993-1995) - start year 1993 is in 1990-1994
        era = get_era("powerpc_601")
        self.assertEqual(era, "1990-1994")
    
    def test_era_1995_1999(self):
        """Verify 1995-1999 era classification"""
        # Pentium II (1997-1999) should be 1995-1999
        era = get_era("pentium_ii")
        self.assertEqual(era, "1995-1999")
    
    def test_bounty_pre_1985(self):
        """Verify pre-1985 bounty (300 RTC)"""
        bounty = get_bounty("dec_vax")
        self.assertEqual(bounty, 300)
    
    def test_bounty_1985_1989(self):
        """Verify 1985-1989 bounty (200 RTC)"""
        bounty = get_bounty("intel_386")
        self.assertEqual(bounty, 200)
    
    def test_bounty_1990_1994(self):
        """Verify 1990-1994 bounty (150 RTC)"""
        bounty = get_bounty("powerpc_601")
        self.assertEqual(bounty, 150)
    
    def test_bounty_1995_1999(self):
        """Verify 1995-1999 bounty (100 RTC)"""
        bounty = get_bounty("pentium_ii")
        self.assertEqual(bounty, 100)
    
    def test_bounty_scale_consistency(self):
        """Verify bounty scale matches era"""
        bounty_map = {
            "Pre-1985": 300,
            "1985-1989": 200,
            "1990-1994": 150,
            "1995-1999": 100,
        }
        for arch in list_profiles():
            era = get_era(arch)
            bounty = get_bounty(arch)
            self.assertEqual(bounty, bounty_map[era],
                f"{arch}: {era} should be {bounty_map[era]} RTC, got {bounty}")


class TestFingerprintGeneration(unittest.TestCase):
    """Test fingerprint generation for vintage miners"""
    
    def setUp(self):
        """Set up test clients"""
        self.client_pentium = VintageMinerClient(
            miner_id="test-pentium-ii-350",
            profile="pentium_ii",
            wallet="RTC1TestWallet123456789"
        )
        self.client_386 = VintageMinerClient(
            miner_id="test-386-25mhz",
            profile="intel_386",
            wallet="RTC1TestWallet987654321"
        )
    
    def test_fingerprint_generation(self):
        """Verify fingerprint can be generated"""
        fingerprint = self.client_pentium.generate_fingerprint()
        
        self.assertIsInstance(fingerprint, Fingerprint)
        self.assertEqual(fingerprint.miner_id, "test-pentium-ii-350")
        self.assertEqual(fingerprint.device_arch, "pentium_ii")
        self.assertEqual(fingerprint.profile_name, "Intel Pentium II")
        self.assertEqual(fingerprint.multiplier, 2.2)
        self.assertIsInstance(fingerprint.timing_proof, TimingProof)
        self.assertIsNotNone(fingerprint.signature)
    
    def test_fingerprint_unique_per_miner(self):
        """Verify fingerprints are unique per miner ID"""
        client1 = VintageMinerClient(
            miner_id="miner-1",
            profile="pentium_ii"
        )
        client2 = VintageMinerClient(
            miner_id="miner-2",
            profile="pentium_ii"
        )
        
        fp1 = client1.generate_fingerprint()
        fp2 = client2.generate_fingerprint()
        
        # Signatures should be different
        self.assertNotEqual(fp1.signature, fp2.signature)
    
    def test_fingerprint_reproducible(self):
        """Verify fingerprint is reproducible for same miner"""
        # Note: timing_proof will vary slightly due to randomness
        # but core fields should be consistent
        fp1 = self.client_pentium.generate_fingerprint()
        fp2 = self.client_pentium.generate_fingerprint()
        
        self.assertEqual(fp1.miner_id, fp2.miner_id)
        self.assertEqual(fp1.device_arch, fp2.device_arch)
        self.assertEqual(fp1.multiplier, fp2.multiplier)
    
    def test_timing_proof_format(self):
        """Verify timing proof has correct format"""
        fingerprint = self.client_pentium.generate_fingerprint()
        timing = fingerprint.timing_proof
        
        self.assertIsInstance(timing.jitter_mean_ms, float)
        self.assertGreater(timing.jitter_mean_ms, 0)
        self.assertIsInstance(timing.jitter_stddev_ms, float)
        self.assertGreater(timing.jitter_stddev_ms, 0)
        self.assertIsInstance(timing.stability_score, float)
        self.assertGreaterEqual(timing.stability_score, 0)
        self.assertLessEqual(timing.stability_score, 1)
        self.assertIsInstance(timing.sample_count, int)
        self.assertGreater(timing.sample_count, 0)
    
    def test_vintage_timing_characteristics(self):
        """Verify vintage CPUs have higher jitter than modern"""
        # 386 should have higher jitter than Pentium II
        fp_386 = self.client_386.generate_fingerprint()
        fp_pentium = self.client_pentium.generate_fingerprint()
        
        # 386 jitter should be higher (slower CPU, more variance)
        self.assertGreater(
            fp_386.timing_proof.jitter_mean_ms,
            fp_pentium.timing_proof.jitter_mean_ms * 2,
            "386 should have significantly higher jitter than Pentium II"
        )
    
    def test_signature_format(self):
        """Verify signature format"""
        fingerprint = self.client_pentium.generate_fingerprint()
        
        # Signature should be ed25519 format (simulated with SHA512)
        self.assertTrue(fingerprint.signature.startswith("ed25519:"))
        # ed25519: prefix (8 chars) + 128 hex chars = 136 total
        self.assertEqual(len(fingerprint.signature), 136)


class TestAttestationProof(unittest.TestCase):
    """Test attestation proof generation and validation"""
    
    def setUp(self):
        """Set up test client"""
        self.client = VintageMinerClient(
            miner_id="test-attestation-miner",
            profile="pentium_ii",
            wallet="RTC1TestWallet123456789"
        )
    
    def test_attestation_request_format(self):
        """Verify attestation request format"""
        fingerprint = self.client.generate_fingerprint()
        attestation = self.client.create_attestation_request(fingerprint, slot=12345)
        
        self.assertIsInstance(attestation, AttestationRequest)
        self.assertEqual(attestation.miner_id, "test-attestation-miner")
        self.assertEqual(attestation.device_arch, "pentium_ii")
        self.assertEqual(attestation.slot, 12345)
        self.assertEqual(attestation.wallet, "RTC1TestWallet123456789")
        self.assertIsNotNone(attestation.fingerprint_hash)
        self.assertIsNotNone(attestation.signature)
    
    def test_fingerprint_hash_uniqueness(self):
        """Verify fingerprint hash is unique per attestation"""
        fp1 = self.client.generate_fingerprint()
        fp2 = self.client.generate_fingerprint()
        
        att1 = self.client.create_attestation_request(fp1, slot=1)
        att2 = self.client.create_attestation_request(fp2, slot=2)
        
        # Hashes should be different (different timestamps)
        self.assertNotEqual(att1.fingerprint_hash, att2.fingerprint_hash)
    
    def test_attestation_proof_json_serializable(self):
        """Verify attestation proof can be serialized to JSON"""
        fingerprint = self.client.generate_fingerprint()
        attestation = self.client.create_attestation_request(fingerprint, slot=12345)
        
        # Should not raise
        json_str = json.dumps({
            "fingerprint": fingerprint.__dict__,
            "attestation": attestation.__dict__,
            "timing_proof": fingerprint.timing_proof.__dict__
        }, default=str)
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        self.assertIn("fingerprint", parsed)
        self.assertIn("attestation", parsed)


class TestSubmissionWorkflow(unittest.TestCase):
    """Test end-to-end submission workflow"""
    
    def setUp(self):
        """Set up test client"""
        self.client = VintageMinerClient(
            miner_id="workflow-test-miner",
            profile="pentium_ii",
            wallet="RTC1WorkflowTestWallet123"
        )
    
    def test_dry_run_submission(self):
        """Verify dry run mode works"""
        result = self.client.submit_attestation(dry_run=True)
        
        self.assertEqual(result["status"], "dry_run")
        self.assertIn("evidence", result)
        self.assertIn("fingerprint", result["evidence"])
        self.assertIn("attestation", result["evidence"])
    
    def test_evidence_package_format(self):
        """Verify evidence package has all required fields"""
        evidence = self.client.get_evidence_package()
        
        required_fields = [
            "miner_id",
            "device_arch",
            "era",
            "bounty_rtc",
            "multiplier",
            "attestation_evidence",
            "submission_checklist"
        ]
        
        for field in required_fields:
            self.assertIn(field, evidence, f"Missing field: {field}")
    
    def test_evidence_package_values(self):
        """Verify evidence package has correct values"""
        evidence = self.client.get_evidence_package()
        
        self.assertEqual(evidence["miner_id"], "workflow-test-miner")
        self.assertEqual(evidence["device_arch"], "pentium_ii")
        self.assertEqual(evidence["era"], "1995-1999")
        self.assertEqual(evidence["bounty_rtc"], 100)
        self.assertEqual(evidence["multiplier"], 2.2)
    
    def test_submission_checklist_present(self):
        """Verify submission checklist is present"""
        evidence = self.client.get_evidence_package()
        checklist = evidence["submission_checklist"]
        
        required_items = [
            "photo_evidence",
            "screenshot",
            "attestation_log",
            "writeup",
            "wallet_address"
        ]
        
        for item in required_items:
            self.assertIn(item, checklist, f"Missing checklist item: {item}")


class TestEvidenceValidation(unittest.TestCase):
    """Test evidence validation for bounty submissions"""
    
    def test_photo_evidence_placeholder(self):
        """Verify photo evidence placeholder format"""
        client = VintageMinerClient(
            miner_id="test-miner",
            profile="pentium_ii"
        )
        evidence = client.get_evidence_package()
        
        # Photo evidence should have TODO placeholder
        self.assertIn("TODO", evidence["submission_checklist"]["photo_evidence"])
    
    def test_screenshot_placeholder(self):
        """Verify screenshot placeholder format"""
        client = VintageMinerClient(
            miner_id="test-miner",
            profile="pentium_ii"
        )
        evidence = client.get_evidence_package()
        
        self.assertIn("TODO", evidence["submission_checklist"]["screenshot"])
    
    def test_attestation_log_placeholder(self):
        """Verify attestation log placeholder format"""
        client = VintageMinerClient(
            miner_id="test-miner",
            profile="pentium_ii"
        )
        evidence = client.get_evidence_package()
        
        self.assertIn("TODO", evidence["submission_checklist"]["attestation_log"])
    
    def test_writeup_placeholder(self):
        """Verify writeup placeholder format"""
        client = VintageMinerClient(
            miner_id="test-miner",
            profile="pentium_ii"
        )
        evidence = client.get_evidence_package()
        
        self.assertIn("TODO", evidence["submission_checklist"]["writeup"])
    
    def test_wallet_address_format(self):
        """Verify wallet address format validation"""
        # Valid wallet
        client = VintageMinerClient(
            miner_id="test-miner",
            profile="pentium_ii",
            wallet="RTC1ValidWallet12345678901234567890123"
        )
        evidence = client.get_evidence_package()
        self.assertTrue(evidence["submission_checklist"]["wallet_address"].startswith("RTC1"))
        
        # Empty wallet
        client_empty = VintageMinerClient(
            miner_id="test-miner",
            profile="pentium_ii"
        )
        evidence_empty = client_empty.get_evidence_package()
        self.assertIn("TODO", evidence_empty["submission_checklist"]["wallet_address"])


class TestMultiplierCalculation(unittest.TestCase):
    """Test multiplier calculations for different eras"""
    
    def test_multiplier_increases_with_age(self):
        """Verify older hardware gets higher multipliers"""
        # Pentium II (1997-1999) = 2.2x
        pentium_ii = get_multiplier("pentium_ii")
        
        # 386 (1985-1994) = 3.0x
        i386 = get_multiplier("intel_386")
        
        # VAX (1977-1994) = 3.5x
        vax = get_multiplier("dec_vax")
        
        self.assertLess(pentium_ii, i386)
        self.assertLess(i386, vax)
    
    def test_game_console_multipliers(self):
        """Verify game console CPU multipliers"""
        nes = get_multiplier("nes_6502")
        snes = get_multiplier("snes_65c816")
        genesis = get_multiplier("genesis_68000")
        ps1 = get_multiplier("ps1_mips")
        
        # All should be >= 2.3x
        self.assertGreaterEqual(nes, 2.3)
        self.assertGreaterEqual(snes, 2.3)
        self.assertGreaterEqual(genesis, 2.3)
        self.assertGreaterEqual(ps1, 2.3)
    
    def test_exotic_architecture_multipliers(self):
        """Verify exotic architecture multipliers"""
        vax = get_multiplier("dec_vax")
        transputer = get_multiplier("transputer")
        clipper = get_multiplier("clipper")
        
        # All should be >= 3.0x (ultra-rare)
        self.assertGreaterEqual(vax, 3.0)
        self.assertGreaterEqual(transputer, 3.0)
        self.assertGreaterEqual(clipper, 3.0)


def run_tests():
    """Run all tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestVintageHardwareProfiles))
    suite.addTests(loader.loadTestsFromTestCase(TestEraAndBountyCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestFingerprintGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestAttestationProof))
    suite.addTests(loader.loadTestsFromTestCase(TestSubmissionWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestEvidenceValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestMultiplierCalculation))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 80)
    print("VINTAGE HARDWARE ATTESTATION TEST SUITE")
    print("Issue #2314: Ghost in the Machine")
    print("=" * 80)
    print()
    
    result = run_tests()
    
    print()
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("=" * 80)
    
    sys.exit(0 if result.wasSuccessful() else 1)
