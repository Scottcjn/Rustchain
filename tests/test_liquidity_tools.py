#!/usr/bin/env python3
"""
Tests for Micro Liquidity Workflow Tools (Bounty #692)

Run with: python test_liquidity_tools.py
Or: pytest tests/test_liquidity_tools.py
"""

import unittest
import json
import sys
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add tools directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))


class TestVerifyLiquidity(unittest.TestCase):
    """Tests for verify_liquidity.py"""
    
    def setUp(self):
        """Set up test fixtures"""
        from verify_liquidity import LiquidityVerifier, PoolInfo, PositionInfo
        
        self.verifier = LiquidityVerifier()
        self.PoolInfo = PoolInfo
        self.PositionInfo = PositionInfo
        
        # Sample pool data
        self.sample_pool = PoolInfo(
            address="8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
            pair="wRTC/SOL",
            base_token="12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X",
            quote_token="So111D1r32v1NvGaTQeXj5Xh9VxNf6",
            tvl_usd=12500.00,
            volume_24h_usd=3200.00,
            fees_24h_usd=8.00,
            price_usd=0.08,
            price_change_24h=5.2,
            liquidity_locked=True,
            pool_age_days=45
        )
    
    def test_pool_info_creation(self):
        """Test PoolInfo dataclass creation"""
        pool = self.sample_pool
        
        self.assertEqual(pool.address, "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb")
        self.assertEqual(pool.pair, "wRTC/SOL")
        self.assertEqual(pool.tvl_usd, 12500.00)
        self.assertTrue(pool.liquidity_locked)
    
    def test_safety_check_token_authenticity(self):
        """Test token authenticity safety check"""
        score = self.verifier._check_token_authenticity(self.sample_pool)
        
        # Should pass because wRTC and SOL are in the pair
        self.assertGreater(score, 0.8)
    
    def test_safety_check_pool_health(self):
        """Test pool health safety check"""
        score = self.verifier._check_pool_health(self.sample_pool)
        
        # Should be moderate score (TVL > 10k, age > 30 days)
        self.assertGreater(score, 0.5)
    
    def test_safety_check_liquidity_lock(self):
        """Test liquidity lock check"""
        score = self.verifier._check_liquidity_lock_status(self.sample_pool)
        
        # Should be 1.0 because liquidity_locked is True
        self.assertEqual(score, 1.0)
    
    def test_rug_pull_risk_assessment(self):
        """Test rug pull risk assessment"""
        score = self.verifier._assess_rug_pull_risk(self.sample_pool)
        
        # Should be moderate-high safety (pool age 45 days, TVL > 10k)
        self.assertGreater(score, 0.5)
    
    def test_run_safety_checks(self):
        """Test running all safety checks"""
        safety_checks = self.verifier.run_safety_checks(self.sample_pool)
        
        self.assertIn("overall_score", safety_checks)
        self.assertIn("passed", safety_checks)
        self.assertIn("checks", safety_checks)
        
        # Overall score should be between 0 and 1
        self.assertGreaterEqual(safety_checks["overall_score"], 0)
        self.assertLessEqual(safety_checks["overall_score"], 1)
    
    @patch('verify_liquidity.requests.Session.get')
    def test_fetch_pool_data_mock(self, mock_get):
        """Test fetching pool data with mocked API"""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "pairs": [{
                "baseToken": {"symbol": "wRTC", "address": "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"},
                "quoteToken": {"symbol": "SOL", "address": "So111D1r32v1NvGaTQeXj5Xh9VxNf6"},
                "liquidity": {"usd": 12500},
                "volume": {"h24": 3200},
                "priceUsd": "0.08",
                "priceChange": {"h24": 5.2},
                "pairCreatedAt": int(datetime.now(timezone.utc).timestamp() * 1000 - 45 * 24 * 60 * 60 * 1000)
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        pool_info = self.verifier.fetch_pool_data("8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb")
        
        self.assertIsNotNone(pool_info)
        self.assertEqual(pool_info.pair, "wRTC/SOL")
        self.assertEqual(pool_info.tvl_usd, 12500)


class TestClaimProofGenerator(unittest.TestCase):
    """Tests for claim_proof_generator.py"""
    
    def setUp(self):
        """Set up test fixtures"""
        from claim_proof_generator import ClaimProofGenerator, ClaimProof, ClaimEvidence
        
        self.generator = ClaimProofGenerator()
        self.ClaimProof = ClaimProof
        self.ClaimEvidence = ClaimEvidence
        
        self.test_wallet = "7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN"
    
    def test_generate_claim_id(self):
        """Test claim ID generation"""
        claim_id = self.generator.generate_claim_id(
            self.test_wallet,
            "692",
            "2026-03-07T10:30:00Z"
        )
        
        self.assertTrue(claim_id.startswith("claim_692_"))
        self.assertEqual(len(claim_id), 26)  # claim_692_ + 16 hex chars
    
    def test_create_attestation(self):
        """Test attestation creation"""
        evidence = {
            "verification_id": "liq_692_test123",
            "pool_address": "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
            "position_value_usd": 10.00
        }
        
        attestation = self.generator.create_attestation(self.test_wallet, evidence)
        
        self.assertIn("method", attestation)
        self.assertIn("verifier", attestation)
        self.assertIn("verification_timestamp", attestation)
        self.assertIn("solscan_url", attestation)
        self.assertEqual(attestation["method"], "solana_transaction_signature")
        self.assertIn(self.test_wallet, attestation["solscan_url"])
    
    def test_create_reproducibility_info(self):
        """Test reproducibility info creation"""
        repro = self.generator.create_reproducibility_info(
            self.test_wallet,
            "692",
            "python claim_proof_generator.py --wallet " + self.test_wallet
        )
        
        self.assertEqual(repro["tool_version"], "1.0.0")
        self.assertEqual(repro["tool_name"], "rustchain_claim_proof_generator")
        self.assertIn("verification_url", repro)
    
    def test_validate_claim_proof_structure(self):
        """Test claim proof validation"""
        from dataclasses import asdict
        from claim_proof_generator import ClaimProof
        
        # Create minimal valid claim proof
        claim_proof = ClaimProof(
            claim_type="micro_liquidity_bounty_692",
            claim_id="claim_692_test123",
            claimant=self.test_wallet,
            claim_date="2026-03-07T10:30:00Z",
            bounty_id="bounty_692",
            evidence={
                "verification_id": "liq_692_test",
                "pool_address": "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
                "pool_pair": "wRTC/SOL",
                "position_value_usd": 10.00,
                "lp_tokens_held": 100.0,
                "pool_share_percent": 0.08,
                "duration_days": 7,
                "fees_earned_usd": 0.50,
                "first_liquidity_date": "2026-03-01T00:00:00Z",
                "last_activity_date": "2026-03-07T00:00:00Z"
            },
            attestation={
                "method": "solana_transaction_signature",
                "signature": "test_signature",
                "verifier": "rustchain_claim_proof_generator_v1.0.0",
                "verification_timestamp": "2026-03-07T10:30:00Z",
                "solscan_url": f"https://solscan.io/account/{self.test_wallet}"
            },
            reproducibility={
                "tool_version": "1.0.0",
                "tool_name": "rustchain_claim_proof_generator",
                "command": f"python claim_proof_generator.py --wallet {self.test_wallet}",
                "verification_url": f"https://solscan.io/account/{self.test_wallet}",
                "github_issue_url": "https://github.com/Scottcjn/Rustchain/issues?q=bounty+692"
            },
            metadata={},
            proof_hash=""  # Will be calculated
        )
        
        # Calculate correct proof hash
        proof_data = {
            "claim_type": claim_proof.claim_type,
            "claimant": claim_proof.claimant,
            "claim_date": claim_proof.claim_date,
            "evidence": claim_proof.evidence,
            "attestation": claim_proof.attestation
        }
        import hashlib
        claim_proof.proof_hash = hashlib.sha256(
            json.dumps(proof_data, sort_keys=True).encode()
        ).hexdigest()
        
        validation = self.generator.validate_claim_proof(claim_proof)
        
        # Debug: print errors if any
        if not validation["valid"]:
            print(f"Validation errors: {validation['errors']}")
        
        # Should be valid
        self.assertTrue(validation["valid"])
        self.assertEqual(len(validation["errors"]), 0)
    
    def test_validate_invalid_claim_proof(self):
        """Test validation catches invalid claim proof"""
        # Create invalid claim proof (missing required fields)
        invalid_proof = {
            "claim_type": "",  # Empty required field
            "claim_id": "",  # Empty required field
            "claimant": self.test_wallet,
            "claim_date": "2026-03-07T10:30:00Z",
            "bounty_id": "bounty_692",
            "evidence": {},
            "attestation": {},
            "reproducibility": {},
            "metadata": {},
            "proof_hash": ""
        }
        
        # Convert to ClaimProof object
        claim_proof = self.ClaimProof(**invalid_proof)
        
        validation = self.generator.validate_claim_proof(claim_proof)
        
        # Should be invalid
        self.assertFalse(validation["valid"])
        self.assertGreater(len(validation["errors"]), 0)


class TestLiquiditySafetyChecks(unittest.TestCase):
    """Tests for liquidity_safety_checks.py"""
    
    def setUp(self):
        """Set up test fixtures"""
        from liquidity_safety_checks import LiquiditySafetyChecker, SafetyCheckResult
        
        self.checker = LiquiditySafetyChecker()
        self.SafetyCheckResult = SafetyCheckResult
        
        # Sample pool data
        self.sample_pool_data = {
            "baseToken": {
                "symbol": "wRTC",
                "address": "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
            },
            "quoteToken": {
                "symbol": "SOL",
                "address": "So111D1r32v1NvGaTQeXj5Xh9VxNf6"
            },
            "liquidity": {
                "usd": 12500
            },
            "volume": {
                "h24": 3200
            },
            "priceChange": {
                "h24": 5.2,
                "d7": 12.5,
                "d30": 25.0
            },
            "pairCreatedAt": int(datetime.now(timezone.utc).timestamp() * 1000 - 45 * 24 * 60 * 60 * 1000)
        }
    
    def test_token_authenticity_check(self):
        """Test token authenticity check"""
        result = self.checker.check_token_authenticity(self.sample_pool_data)
        
        self.assertIsInstance(result, self.SafetyCheckResult)
        self.assertEqual(result.name, "Token Authenticity")
        # Should pass because wRTC and SOL are verified
        self.assertTrue(result.passed)
        self.assertGreater(result.score, 0.8)
    
    def test_pool_health_check(self):
        """Test pool health check"""
        result = self.checker.check_pool_health(self.sample_pool_data)
        
        self.assertIsInstance(result, self.SafetyCheckResult)
        self.assertEqual(result.name, "Pool Health")
        # Should be moderate score
        self.assertGreater(result.score, 0.5)
    
    def test_liquidity_lock_check(self):
        """Test liquidity lock check"""
        result = self.checker.check_liquidity_lock(self.sample_pool_data)
        
        self.assertIsInstance(result, self.SafetyCheckResult)
        self.assertEqual(result.name, "Liquidity Lock")
        # Should have moderate score (unknown but old pool)
        self.assertGreater(result.score, 0.5)
    
    def test_rug_pull_risk_check(self):
        """Test rug pull risk assessment"""
        result = self.checker.assess_rug_pull_risk(self.sample_pool_data)
        
        self.assertIsInstance(result, self.SafetyCheckResult)
        self.assertEqual(result.name, "Rug Pull Risk")
        # Should be low risk (old pool, decent TVL)
        self.assertGreater(result.score, 0.6)
    
    def test_impermanent_loss_risk_check(self):
        """Test impermanent loss risk calculation"""
        result = self.checker.calculate_impermanent_loss_risk(self.sample_pool_data)
        
        self.assertIsInstance(result, self.SafetyCheckResult)
        self.assertEqual(result.name, "Impermanent Loss Risk")
        # Should have moderate IL risk
        self.assertIn("IL Risk", result.details)
    
    def test_contract_risk_check(self):
        """Test contract risk check"""
        result = self.checker.check_contract_risk(self.sample_pool_data)
        
        self.assertIsInstance(result, self.SafetyCheckResult)
        self.assertEqual(result.name, "Contract Risk")
        # Should be low risk for official Raydium pool
        self.assertGreater(result.score, 0.6)
    
    def test_wallet_security_check(self):
        """Test wallet security check"""
        test_wallet = "7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN"
        result = self.checker.check_wallet_security(test_wallet)
        
        self.assertIsInstance(result, self.SafetyCheckResult)
        self.assertEqual(result.name, "Wallet Security")
        # Should pass (valid address format)
        self.assertTrue(result.passed)
    
    def test_invalid_wallet_security_check(self):
        """Test wallet security check with invalid address"""
        invalid_wallet = "invalid_wallet"
        result = self.checker.check_wallet_security(invalid_wallet)
        
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)
        self.assertIn("Invalid wallet address", result.details)
    
    def test_run_all_checks(self):
        """Test running all safety checks"""
        with patch.object(self.checker, 'fetch_pool_data', return_value=self.sample_pool_data):
            report = self.checker.run_all_checks(
                "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
                "7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN"
            )
        
        self.assertGreater(report.overall_score, 0)
        self.assertLessEqual(report.overall_score, 1)
        self.assertIn(report.risk_level, ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        self.assertIsInstance(report.checks, list)
        self.assertGreater(len(report.checks), 0)


class TestIntegration(unittest.TestCase):
    """Integration tests for liquidity workflow"""
    
    def test_end_to_end_workflow(self):
        """Test complete workflow: verify -> safety check -> claim proof"""
        from verify_liquidity import LiquidityVerifier, PoolInfo
        from claim_proof_generator import ClaimProofGenerator
        from liquidity_safety_checks import LiquiditySafetyChecker
        
        # Step 1: Create verifier and sample pool
        verifier = LiquidityVerifier()
        pool_info = PoolInfo(
            address="8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
            pair="wRTC/SOL",
            base_token="12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X",
            quote_token="So111D1r32v1NvGaTQeXj5Xh9VxNf6",
            tvl_usd=12500.00,
            volume_24h_usd=3200.00,
            fees_24h_usd=8.00,
            price_usd=0.08,
            price_change_24h=5.2,
            liquidity_locked=True,
            pool_age_days=45
        )
        
        # Step 2: Run safety checks
        safety_checks = verifier.run_safety_checks(pool_info)
        self.assertGreater(safety_checks["overall_score"], 0.5)
        
        # Step 3: Generate claim proof
        generator = ClaimProofGenerator()
        test_wallet = "7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN"
        
        # Mock evidence fetching
        evidence_data = {
            "verification_id": "liq_692_test",
            "pool_address": pool_info.address,
            "pool_pair": pool_info.pair,
            "position_value_usd": 10.00,
            "lp_tokens_held": 100.0,
            "pool_share_percent": 0.08,
            "duration_days": 7,
            "fees_earned_usd": 0.50,
            "first_liquidity_date": "2026-03-01T00:00:00Z",
            "last_activity_date": "2026-03-07T00:00:00Z"
        }
        
        # Create attestation
        attestation_data = generator.create_attestation(test_wallet, evidence_data)
        
        # Verify attestation structure
        self.assertIn("method", attestation_data)
        self.assertIn("verifier", attestation_data)
        self.assertIn("solscan_url", attestation_data)
        
        print("✅ End-to-end workflow test passed")


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestVerifyLiquidity))
    suite.addTests(loader.loadTestsFromTestCase(TestClaimProofGenerator))
    suite.addTests(loader.loadTestsFromTestCase(TestLiquiditySafetyChecks))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
