#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Tests for BCOS v2 Badge Generator.

Run with:
    python -m pytest tests/test_bcos_badge_generator.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the badge generator module
from tools.bcos_badge_generator import (
    BADGE_CONFIG,
    init_db,
    generate_badge_svg,
    generate_static_badge_svg,
    verify_certificate,
    get_badge_stats,
    record_badge_generation,
    increment_download_count,
)


class TestBadgeConfig(unittest.TestCase):
    """Test badge configuration."""

    def test_tier_config_exists(self):
        """Test that all tier configs are defined."""
        self.assertIn('L0', BADGE_CONFIG['tiers'])
        self.assertIn('L1', BADGE_CONFIG['tiers'])
        self.assertIn('L2', BADGE_CONFIG['tiers'])

    def test_tier_has_required_fields(self):
        """Test that each tier has required configuration fields."""
        required_fields = ['label', 'color_start', 'color_end', 'bg_color', 'text_color', 'min_score']
        for tier, config in BADGE_CONFIG['tiers'].items():
            for field in required_fields:
                self.assertIn(field, config, f"Tier {tier} missing field: {field}")

    def test_tier_min_scores(self):
        """Test tier minimum scores are correct."""
        self.assertEqual(BADGE_CONFIG['tiers']['L0']['min_score'], 40)
        self.assertEqual(BADGE_CONFIG['tiers']['L1']['min_score'], 60)
        self.assertEqual(BADGE_CONFIG['tiers']['L2']['min_score'], 80)


class TestBadgeSVGGeneration(unittest.TestCase):
    """Test SVG badge generation."""

    def test_generate_badge_svg_basic(self):
        """Test basic SVG generation."""
        svg = generate_badge_svg(
            repo_name='test/repo',
            tier='L1',
            trust_score=75,
        )

        self.assertIn('<svg', svg)
        self.assertIn('</svg>', svg)
        self.assertIn('BCOS', svg)
        self.assertIn('L1', svg)
        self.assertIn('test/repo', svg)

    def test_generate_badge_svg_all_tiers(self):
        """Test SVG generation for all tiers."""
        for tier in ['L0', 'L1', 'L2']:
            svg = generate_badge_svg(
                repo_name='test/repo',
                tier=tier,
                trust_score=75,
            )
            self.assertIn(tier, svg, f"Tier {tier} not found in SVG")

    def test_generate_badge_svg_with_cert_id(self):
        """Test SVG generation with certificate ID."""
        svg = generate_badge_svg(
            repo_name='test/repo',
            tier='L1',
            cert_id='BCOS-12345678',
        )

        # Cert ID is used in aria-label for accessibility
        self.assertIn('BCOS L1 Certified', svg)
        # The cert_id is stored in metadata, not directly in SVG
        self.assertIn('<svg', svg)

    def test_generate_badge_svg_with_qr(self):
        """Test SVG generation with QR code."""
        svg = generate_badge_svg(
            repo_name='test/repo',
            tier='L1',
            include_qr=True,
            verification_url='https://example.com/verify',
        )

        self.assertIn('SCAN', svg)
        self.assertIn('rect', svg)

    def test_generate_badge_svg_truncates_long_name(self):
        """Test that long repo names are truncated."""
        long_name = 'very-long-organization-name/very-long-repository-name'
        svg = generate_badge_svg(
            repo_name=long_name,
            tier='L1',
        )

        # Should be truncated to 25 chars with ...
        self.assertIn('...', svg)

    def test_generate_badge_svg_trust_score_colors(self):
        """Test trust score color coding."""
        # High score (green)
        svg_high = generate_badge_svg(repo_name='test/repo', tier='L1', trust_score=90)
        self.assertIn('#4c1', svg_high)

        # Medium score (yellow/orange)
        svg_med = generate_badge_svg(repo_name='test/repo', tier='L1', trust_score=65)
        self.assertIn('#f59e0b', svg_med)

        # Low score (red)
        svg_low = generate_badge_svg(repo_name='test/repo', tier='L1', trust_score=30)
        self.assertIn('#ef4444', svg_low)

    def test_generate_static_badge_svg(self):
        """Test static badge generation."""
        for tier in ['L0', 'L1', 'L2']:
            svg = generate_static_badge_svg(tier=tier)
            self.assertIn('<svg', svg)
            self.assertIn('BCOS', svg)


class TestDatabaseOperations(unittest.TestCase):
    """Test database operations."""

    def setUp(self):
        """Set up test database."""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        # Patch DATABASE path
        import tools.bcos_badge_generator as bg
        self.original_db = bg.DATABASE
        bg.DATABASE = self.test_db.name

    def tearDown(self):
        """Clean up test database."""
        import tools.bcos_badge_generator as bg
        bg.DATABASE = self.original_db
        os.unlink(self.test_db.name)

    def test_init_db(self):
        """Test database initialization."""
        init_db()
        # Should create tables without error
        self.assertTrue(os.path.exists(self.test_db.name))

    def test_record_badge_generation(self):
        """Test recording badge generation."""
        init_db()
        record_badge_generation(
            cert_id='BCOS-12345678',
            repo_name='test/repo',
            tier='L1',
            metadata={'trust_score': 75},
        )

        # Verify by getting stats
        stats = get_badge_stats()
        self.assertEqual(stats['total_badges'], 1)

    def test_increment_download_count(self):
        """Test incrementing download count."""
        init_db()
        record_badge_generation(
            cert_id='BCOS-12345678',
            repo_name='test/repo',
            tier='L1',
        )
        increment_download_count('BCOS-12345678')
        increment_download_count('BCOS-12345678')

        # Check download count (would need direct DB access to verify)
        # For now, just ensure it doesn't error

    def test_get_badge_stats(self):
        """Test getting badge statistics."""
        init_db()

        # Record some badges
        record_badge_generation('BCOS-11111111', 'repo/a', 'L0', {'trust_score': 45})
        record_badge_generation('BCOS-22222222', 'repo/b', 'L1', {'trust_score': 65})
        record_badge_generation('BCOS-33333333', 'repo/c', 'L1', {'trust_score': 70})
        record_badge_generation('BCOS-44444444', 'repo/d', 'L2', {'trust_score': 85})

        stats = get_badge_stats()

        self.assertEqual(stats['total_badges'], 4)
        self.assertEqual(stats['by_tier'].get('L0', 0), 1)
        self.assertEqual(stats['by_tier'].get('L1', 0), 2)
        self.assertEqual(stats['by_tier'].get('L2', 0), 1)
        self.assertIn('recent_7_days', stats)
        self.assertIn('top_repos', stats)

    def test_verify_certificate_valid(self):
        """Test verifying a valid certificate."""
        init_db()
        record_badge_generation(
            cert_id='BCOS-TESTTEST',
            repo_name='test/repo',
            tier='L1',
            metadata={'trust_score': 75, 'reviewer': 'Test Reviewer'},
        )

        result = verify_certificate('BCOS-TESTTEST')

        self.assertTrue(result['valid'])
        self.assertFalse(result['cached'])
        self.assertEqual(result['data']['repo_name'], 'test/repo')
        self.assertEqual(result['data']['tier'], 'L1')
        self.assertEqual(result['data']['trust_score'], 75)

    def test_verify_certificate_cache_returns_response_data(self):
        """Cached certificate verification should return the cached response data."""
        init_db()
        record_badge_generation(
            cert_id='BCOS-CACHED',
            repo_name='cache/repo',
            tier='L2',
            metadata={'trust_score': 90},
        )

        first = verify_certificate('BCOS-CACHED')
        second = verify_certificate('BCOS-CACHED')

        self.assertTrue(first['valid'])
        self.assertFalse(first['cached'])
        self.assertTrue(second['valid'])
        self.assertTrue(second['cached'])
        self.assertEqual(second['data']['repo_name'], 'cache/repo')
        self.assertEqual(second['data']['tier'], 'L2')
        self.assertEqual(second['data']['trust_score'], 90)

    def test_verify_certificate_invalid(self):
        """Test verifying an invalid certificate."""
        init_db()

        result = verify_certificate('BCOS-NOTFOUND')

        self.assertFalse(result['valid'])
        self.assertEqual(result['data'], {})


class TestBadgeValidation(unittest.TestCase):
    """Test badge validation logic."""

    def test_valid_repo_name_format(self):
        """Test valid repository name formats."""
        import re
        pattern = r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$'

        valid_names = [
            'owner/repo',
            'test-user/test_repo',
            'org/project.name',
            'user/repo-123',
        ]

        for name in valid_names:
            self.assertTrue(re.match(pattern, name), f"{name} should be valid")

    def test_invalid_repo_name_format(self):
        """Test invalid repository name formats."""
        import re
        pattern = r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$'

        invalid_names = [
            'repo',  # Missing owner
            '/repo',  # Missing owner
            'owner/',  # Missing repo
            'owner/repo/extra',  # Too many parts
            'owner@repo',  # Invalid separator
        ]

        for name in invalid_names:
            self.assertFalse(re.match(pattern, name), f"{name} should be invalid")


class TestFlaskIntegration(unittest.TestCase):
    """Test Flask API endpoints."""

    def setUp(self):
        """Set up Flask test client."""
        from tools.bcos_badge_generator import app
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()

        import tools.bcos_badge_generator as bg
        self.original_db = bg.DATABASE
        bg.DATABASE = self.test_db.name

        app.config['TESTING'] = True
        self.client = app.test_client()

        # Initialize DB
        init_db()

    def tearDown(self):
        """Clean up."""
        import tools.bcos_badge_generator as bg
        bg.DATABASE = self.original_db
        os.unlink(self.test_db.name)

    def test_index_page(self):
        """Test index page loads."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'BCOS', response.data)
        self.assertIn(b'Badge Generator', response.data)

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['service'], 'bcos-badge-generator')

    def test_generate_badge_success(self):
        """Test badge generation success."""
        response = self.client.post(
            '/api/badge/generate',
            json={
                'repo_name': 'test/repo',
                'tier': 'L1',
                'trust_score': 75,
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('cert_id', data)
        self.assertIn('svg', data)
        self.assertIn('markdown', data)
        self.assertIn('html', data)

    def test_generate_badge_missing_repo(self):
        """Test badge generation with missing repo name."""
        response = self.client.post(
            '/api/badge/generate',
            json={
                'tier': 'L1',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('error', data)

    def test_generate_badge_invalid_tier(self):
        """Test badge generation with invalid tier."""
        response = self.client.post(
            '/api/badge/generate',
            json={
                'repo_name': 'test/repo',
                'tier': 'INVALID',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('error', data)

    def test_generate_badge_invalid_score(self):
        """Test badge generation with invalid trust score."""
        response = self.client.post(
            '/api/badge/generate',
            json={
                'repo_name': 'test/repo',
                'tier': 'L1',
                'trust_score': 150,
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('error', data)

    def test_stats_endpoint(self):
        """Test stats endpoint."""
        # Generate a badge first
        self.client.post(
            '/api/badge/generate',
            json={
                'repo_name': 'test/repo',
                'tier': 'L1',
            },
        )

        response = self.client.get('/api/badge/stats')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('total_badges', data)
        self.assertIn('by_tier', data)

    def test_verify_endpoint(self):
        """Test verify endpoint."""
        # Generate a badge first
        gen_response = self.client.post(
            '/api/badge/generate',
            json={
                'repo_name': 'test/repo',
                'tier': 'L1',
            },
        )
        cert_id = json.loads(gen_response.data)['cert_id']

        # Verify it
        response = self.client.get(f'/api/badge/verify/{cert_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['valid'])

    def test_verify_not_found(self):
        """Test verify endpoint with non-existent cert."""
        response = self.client.get('/api/badge/verify/BCOS-NOTFOUND')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['valid'])

    def test_serve_badge_svg(self):
        """Test serving badge SVG."""
        # Generate a badge first
        gen_response = self.client.post(
            '/api/badge/generate',
            json={
                'repo_name': 'test/repo',
                'tier': 'L1',
            },
        )
        cert_id = json.loads(gen_response.data)['cert_id']

        # Serve the SVG
        response = self.client.get(f'/badge/{cert_id}.svg')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'image/svg+xml')
        self.assertIn(b'<svg', response.data)

    def test_serve_badge_svg_not_found(self):
        """Test serving non-existent badge."""
        response = self.client.get('/badge/BCOS-NOTFOUND.svg')
        self.assertEqual(response.status_code, 404)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_repo_name(self):
        """Test handling of empty repo name."""
        svg = generate_badge_svg(repo_name='', tier='L1')
        self.assertIn('<svg', svg)

    def test_special_characters_in_repo(self):
        """Test handling of special characters in repo name."""
        svg = generate_badge_svg(repo_name='test-user/test_repo.name', tier='L1')
        self.assertIn('test-user/test_repo.name', svg)

    def test_unicode_in_repo(self):
        """Test handling of unicode characters."""
        svg = generate_badge_svg(repo_name='test/リポジトリ', tier='L1')
        self.assertIn('<svg', svg)

    def test_boundary_trust_scores(self):
        """Test boundary trust scores."""
        for score in [0, 50, 100]:
            svg = generate_badge_svg(repo_name='test/repo', tier='L1', trust_score=score)
            self.assertIn('<svg', svg)

    def test_invalid_tier_defaults_to_l1(self):
        """Test that invalid tier defaults to L1 config."""
        svg = generate_badge_svg(repo_name='test/repo', tier='INVALID', trust_score=75)
        # Should still generate, using L1 config
        self.assertIn('<svg', svg)


if __name__ == '__main__':
    unittest.main()
