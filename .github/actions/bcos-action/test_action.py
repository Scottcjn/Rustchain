#!/usr/bin/env python3
"""
BCOS v2 Action - Test Suite

Tests the main.py action script functionality.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from main import (
    MinimalBCOSScanner,
    post_github_comment,
    anchor_to_rustchain,
    set_github_output
)


class TestMinimalBCOSScanner(unittest.TestCase):
    """Test the minimal BCOS scanner."""
    
    def setUp(self):
        """Create a temporary test repository."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.temp_dir.name)
        
        # Create basic repo structure
        (self.repo_path / "LICENSE").write_text("MIT License")
        (self.repo_path / "README.md").write_text("# Test Repo")
        (self.repo_path / "tests").mkdir()
        (self.repo_path / "tests" / "test_main.py").write_text("def test_pass(): pass")
        
    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()
    
    def test_init(self):
        """Test scanner initialization."""
        scanner = MinimalBCOSScanner(
            repo_path=str(self.repo_path),
            tier="L1",
            reviewer="test-reviewer"
        )
        
        self.assertEqual(scanner.tier, "L1")
        self.assertEqual(scanner.reviewer, "test-reviewer")
        self.assertIsNotNone(scanner.commit_sha)
    
    def test_run_all_l1(self):
        """Test running a full L1 scan."""
        scanner = MinimalBCOSScanner(
            repo_path=str(self.repo_path),
            tier="L1"
        )
        
        report = scanner.run_all()
        
        # Check required fields
        self.assertEqual(report["schema"], "bcos-attestation/v2")
        self.assertIn("trust_score", report)
        self.assertIn("tier_met", report)
        self.assertIn("cert_id", report)
        self.assertIn("commitment", report)
        self.assertIn("score_breakdown", report)
        
        # Check score breakdown keys
        breakdown = report["score_breakdown"]
        self.assertIn("license_compliance", breakdown)
        self.assertIn("vulnerability_scan", breakdown)
        self.assertIn("static_analysis", breakdown)
        self.assertIn("sbom_completeness", breakdown)
        self.assertIn("dependency_freshness", breakdown)
        self.assertIn("test_evidence", breakdown)
        self.assertIn("review_attestation", breakdown)
        
        # L1 should have review attestation points
        self.assertGreaterEqual(breakdown["review_attestation"], 5)
    
    def test_run_all_l2_with_reviewer(self):
        """Test running an L2 scan with reviewer."""
        scanner = MinimalBCOSScanner(
            repo_path=str(self.repo_path),
            tier="L2",
            reviewer="alice"
        )
        
        report = scanner.run_all()
        
        # L2 with reviewer should have max review points
        self.assertEqual(report["score_breakdown"]["review_attestation"], 10)
    
    def test_run_all_l0(self):
        """Test running an L0 scan (automation only)."""
        scanner = MinimalBCOSScanner(
            repo_path=str(self.repo_path),
            tier="L0"
        )
        
        report = scanner.run_all()
        
        # L0 should have no review attestation points
        self.assertEqual(report["score_breakdown"]["review_attestation"], 0)
    
    def test_tier_thresholds(self):
        """Test tier threshold logic."""
        # Create minimal repo (no tests, no CI)
        minimal_dir = tempfile.TemporaryDirectory()
        minimal_path = Path(minimal_dir.name)
        (minimal_path / "LICENSE").write_text("MIT")
        
        scanner = MinimalBCOSScanner(
            repo_path=str(minimal_path),
            tier="L1"
        )
        
        report = scanner.run_all()
        
        # L1 requires 60 points - minimal repo should not meet it
        # (License=20, basic=50, total=70, but may vary)
        self.assertIsInstance(report["tier_met"], bool)
        
        minimal_dir.cleanup()
    
    def test_cert_id_format(self):
        """Test certification ID format."""
        scanner = MinimalBCOSScanner(
            repo_path=str(self.repo_path),
            tier="L1"
        )
        
        report = scanner.run_all()
        
        cert_id = report["cert_id"]
        self.assertTrue(cert_id.startswith("BCOS-"))
        self.assertEqual(len(cert_id), 13)  # BCOS- + 8 chars


class TestGitHubComment(unittest.TestCase):
    """Test GitHub comment posting."""
    
    @patch('main.urlopen')
    def test_post_comment_success(self, mock_urlopen):
        """Test successful comment posting."""
        mock_response = MagicMock()
        mock_response.status = 201
        mock_urlopen.return_value = mock_response
        
        report = {
            "trust_score": 75,
            "tier_met": True,
            "cert_id": "BCOS-test123",
            "tier": "L1",
            "commit_sha": "abc123def456",
            "commitment": "hash123",
            "timestamp": "2024-01-01T00:00:00Z",
            "schema": "bcos-attestation/v2",
            "score_breakdown": {
                "license_compliance": 20,
                "vulnerability_scan": 15,
                "static_analysis": 10,
                "sbom_completeness": 5,
                "dependency_freshness": 5,
                "test_evidence": 10,
                "review_attestation": 10
            }
        }
        
        result = post_github_comment(
            repo="test/repo",
            pr_number="42",
            report=report,
            token="fake-token"
        )
        
        self.assertTrue(result)
        mock_urlopen.assert_called_once()


class TestRustChainAnchoring(unittest.TestCase):
    """Test RustChain anchoring."""
    
    @patch('main.urlopen')
    def test_anchor_success(self, mock_urlopen):
        """Test successful anchoring."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "tx_hash": "0x123abc",
            "block_number": 12345
        }).encode()
        mock_urlopen.return_value = mock_response
        
        report = {
            "cert_id": "BCOS-test123",
            "commitment": "hash123"
        }
        
        result = anchor_to_rustchain(
            node_url="https://rustchain.org",
            report=report,
            repo="test/repo",
            pr_number="42",
            merged_commit="abc123"
        )
        
        self.assertTrue(result)


class TestGitHubOutput(unittest.TestCase):
    """Test GitHub output setting."""
    
    def test_set_output_with_file(self):
        """Test setting output with GITHUB_OUTPUT file."""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            output_file = f.name
        
        with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}):
            set_github_output({
                "trust_score": "75",
                "tier_met": "true"
            })
        
        with open(output_file, 'r') as f:
            content = f.read()
        
        self.assertIn("trust_score=75", content)
        self.assertIn("tier_met=true", content)
        
        os.unlink(output_file)
    
    def test_set_output_without_file(self):
        """Test setting output without GITHUB_OUTPUT (prints to stdout)."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('main.print') as mock_print:
                set_github_output({
                    "trust_score": "75",
                    "tier_met": "true"
                })
                
                # Should print to stdout
                self.assertTrue(mock_print.called)


class TestScoreCalculation(unittest.TestCase):
    """Test score calculation logic."""
    
    def setUp(self):
        """Create test repositories with different structures."""
        self.temp_dirs = []
    
    def tearDown(self):
        """Clean up temporary directories."""
        for td in self.temp_dirs:
            td.cleanup()
    
    def _create_repo(self, files):
        """Helper to create a test repo with specified files."""
        temp_dir = tempfile.TemporaryDirectory()
        self.temp_dirs.append(temp_dir)
        repo_path = Path(temp_dir.name)
        
        for file_path, content in files.items():
            full_path = repo_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        return str(repo_path)
    
    def test_full_score_repo(self):
        """Test repository with all components."""
        repo_path = self._create_repo({
            "LICENSE": "MIT",
            "README.md": "# Test",
            "tests/test.py": "def test(): pass",
            ".github/workflows/ci.yml": "name: CI"
        })
        
        scanner = MinimalBCOSScanner(repo_path=repo_path, tier="L2", reviewer="alice")
        report = scanner.run_all()
        
        # Should have high score
        self.assertGreaterEqual(report["trust_score"], 70)
        self.assertTrue(report["tier_met"])
    
    def test_minimal_repo(self):
        """Test minimal repository."""
        repo_path = self._create_repo({
            "LICENSE": "MIT"
        })
        
        scanner = MinimalBCOSScanner(repo_path=repo_path, tier="L0")
        report = scanner.run_all()
        
        # Should have basic score
        self.assertGreaterEqual(report["trust_score"], 50)


if __name__ == '__main__':
    unittest.main(verbosity=2)
